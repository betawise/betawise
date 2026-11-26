# Preallocated chapter output and native clipboard copy

Research against BibleWise commit `2c57992`, using the same SDK/compiler and
pinned Neo 3.21 firmware as the accepted reader. The combined design is now
the production default; the frozen `reference/` retains the old implementations.
Generated images, records, raw LCD samples, source/font assertions, allocation
traces and timing results live under ignored `build/`. `summarize.py` regenerates
`build/results.json` from the accepted runs; all times below are emulated Neo
milliseconds, not host wall time.

## Compared designs

- **Baseline:** archived 256-byte append writer and buffered/filtering clipboard copy.
- **Fresh file:** same buffered decoder; delete/recreate instead of erasing the allocation.
- **Direct decode:** fresh file with a generated capacity bound; decode straight into RAM.
- **Native copy:** `ClipboardCopy`, reserve citation space, filter/compact clipboard in place.
- **Combined:** direct decode plus native copy.

| Variant | Release ROM saved | A5 bytes |
|---|---:|---:|
| Baseline | 0 | 1,578 |
| Fresh file only | 26 | 1,578 |
| Direct decode | 70 | 1,582 |
| Native copy | 158 | 1,570 |
| Combined | **234** | **1,570** |

The deltas apply equally to KJV and NKJV. Combined release images are 1,311,190
bytes for KJV and 1,457,190 for NKJV. Baseline release images are byte-identical
to the pre-adoption production build. There is no added size table or resource-size increase.

## Chapter loading

### KJV: separate allocation/erase cost from decode cost

| Operation | Baseline | Fresh file, buffered | Direct decode |
|---|---:|---:|---:|
| Load 1 Corinthians 13 | 589 | 287 | **274** |
| Load John 3 | 926 | 624 | **587** |
| Load Psalm 119 | 2,239 | 1,937 | **1,797** |
| Psalm 119 decode/write only | 1,604 | 1,604 | **1,464** |
| Reload Genesis 1 | 912 | 620 | **583** |

`FileEraseCurrent` clears the allocation, not merely the old logical text. The
last file can own the remaining reclaimable RAM tail (417,792 bytes in the initial
fixture). Timing its syscall directly on NKJV gives about 303 ms per load, or
293 ms after clipboard growth. Therefore most short-chapter load savings come
from avoiding that erase. Direct output additionally improves the decode/write
interval by about 8–9%, without decoding twice or changing the Huffman model.

### NKJV: combined result

| Operation | Baseline | Combined |
|---|---:|---:|
| Load 1 Corinthians 13 | 604 | **289** |
| Load John 3 | 952 | **613** |
| Load Psalm 119 | 2,349 | **1,892** |
| Psalm 119 decode/write only | 1,687 | **1,532** |
| Reload Genesis 1 | 950 | **619** |

Total-load intervals include allocation, formatting/decode, native wrapping and
final display. Decode/write intervals do not include preallocation or display.
Initial Genesis load starts before the harness attaches; use Reload Genesis for
complete totals. Exact source/glyph/cursor/LCD checks pass, and logical chapter
bytes match baseline byte-for-byte in all 14 corresponding KJV and NKJV bench
checkpoints, including formatting toggles and focus return.

### Capacity contract and RAM

The bound generator uses source atoms/layout rather than replicating exact writer
output. It budgets source bytes, separators/CRs/indentation, maximum three-byte
face transitions, verse wrappers, heading wrappers and up to 252 alignment spaces
per aligned line. This is safe even for zero-width space glyphs (the writer's
fallback divisor is one), without knowing which font is installed. Body-character
assumptions match the current formatter and are asserted during generation.

Experimental **HUF03** retains the source length in the low 16 bits of chapter
word four and stores the native capacity bound in its formerly zero high 16 bits.
Both ranges are asserted. The magic changes so a HUF02 consumer rejects the new
field contract rather than silently misinterpreting it. No dictionary, grammar,
Huffman payload, search index or sidecar lengths change. The target checks every
write against the bound; overflow fails the chapter load instead of writing past
the allocation. This needs a documented bound contract/version, but not exact
cross-language agreement on the output byte count.

The largest content bounds are 16,551 KJV and 18,677 NKJV bytes, excluding the
512-byte native gap. A host harness exercises the **actual C formatter and writer**
on all 1,189 chapters at four extreme width profiles, rich/plain faces and both
italic preferences: 19,024 chapter profiles per translation. All bounds and guard
bytes pass; the tightest margins are 4 bytes KJV and 3 bytes NKJV.

For the KJV/Century Psalm 119 case, loading reserves 17,063 bytes including the
gap, versus the final 16,576-byte chapter: 487 bytes of temporary extra minimum
reservation. The reservation is reset to actual length after decode. Final
chapter minimum RAM is unchanged. Raw last-file capacity includes reclaimable
free-tail space and must not be counted as permanent reader RAM.

GCC's own `DecodeChapterToFile` frame drops from 1,384 to 1,132 bytes. This is a
252-byte function-frame reduction, not a complete peak-stack measurement;
callees and firmware are outside it. The aligned-line scratch remains.

## Clipboard

| Copy processing | KJV baseline | KJV native copy | NKJV baseline | NKJV combined |
|---|---:|---:|---:|---:|
| Short verse | 6.4 | **5.7** | see raw report | see raw report |
| Entire Psalm 119, visible headings | 934 | **463** | 1,048 | **533** |
| Entire Psalm, headings hidden | 945 | **446** | 1,061 | **511** |

These intervals exclude painting the Copied notice. The native routine copies the
encoded range, including enough preceding context to establish the selection's
style. After reserving all ellipsis/citation space, conversion contracts that
clipboard buffer in place: remove native/verse records, decode private small caps,
skip hidden content, normalize spaces, and append the citation. No pointer is
held across a resize. Final logical length is committed afterward.

The combined allocator fixture observes one chapter relocation on the first long
copy and no relocation on the second, because its raw allocation can be reused.
The old repeated-append fixture observes 25 moves on each long copy. The research
runner changes only the second-copy allocation expectation; exact text, citation,
source/style, selection, cursor and bitmap assertions remain unchanged. It also
asserts the new second copy makes three allocator-facing calls and zero moves.

This costs more temporary clipboard RAM: peak physical capacity is **16,384 bytes
versus 13,312**, a 3,072-byte increase for the tested long copy. Final text lengths
are identical (13,146 with headings; 13,013 without). Some raw-buffer slack remains
reclaimable after shortening the clipboard; it is not permanently reserved.
GCC's own copy frame drops from 608 to 188 bytes, a 420-byte reduction. These are
separate measurements, not an assertion of a 420-byte total peak-stack reduction.

## Validation and reproduction

Accepted: six 14-checkpoint benchmark suites; baseline and combined KJV allocator
cases (17 each); combined NKJV usage (73); combined vendor Small italic tests (14):
**205 MAME checkpoints** plus **38,048 host chapter profiles**. Screen validation
is deterministic and local using the canonical source/font/cursor/LCD oracles.
All guest storage is disposable. No screenshots are sent to a model.

From the workspace root (the scripts use the frozen baseline sources):

```sh
python3 betawise/research/bible-reader/preallocated-output/prepare.py direct-decode --build
python3 betawise/research/bible-reader/preallocated-output/prepare.py combined --build
python3 betawise/research/bible-reader/preallocated-output/check_bounds.py --version KJV
python3 betawise/research/bible-reader/preallocated-output/check_bounds.py --version NKJV
python3 betawise/research/bible-reader/preallocated-output/run.py combined --bench --version NKJV --case formatting --vendor-font schoolbook --output betawise/research/bible-reader/preallocated-output/build/recheck-bench
python3 betawise/research/bible-reader/preallocated-output/run.py combined --version KJV --case copy-relocation --vendor-font schoolbook --output betawise/research/bible-reader/preallocated-output/build/recheck-copy
```

Other variants are `baseline`, `fresh-file`, `direct-decode`, and `native-copy`.
The summary expects the original named accepted suite directories; individual
rechecks produce their own results/manifest/trace files. Bound caches fingerprint
the generator, source and formatting dependencies. Only derived research data
is changed; original production resources remain unmodified.

Recommendation: the combined design is faster and slightly smaller. Its main
tradeoff is roughly 3 KiB more clipboard headroom for the longest tested copy,
plus an explicit new bound-field contract.

## Production adoption

Production uses direct bounded output plus native clipboard copy. HUF03 splits
chapter record word four into a uint16 capacity bound and uint16 source length,
so the resources do not grow. The writer checks each byte against the bound;
failed initialization deletes the incomplete file. The EOF gap is initialized
only after decoding. No chapter pointer survives an allocating OS operation.

The final release sizes are **1,311,244 bytes KJV**, **1,457,244 bytes NKJV**,
and **1,570 bytes A5**: **180 ROM bytes and 8 A5 bytes saved** versus the archived
baseline. The 54-byte difference from the prototype saving covers failed-open
cleanup and byte-safe ellipsis writes. GCC otherwise expands a four-byte memcpy
into a potentially unaligned long store, which faults on the 68000. The maintained
`partial-copy` acceptance case exercises partial selections with both odd and even
lengths, with leading/trailing omission marks and exact citations.

Fresh production acceptance covers **164 MAME checkpoints**, with **38,048 host
chapter profiles**, codec round trips and source-based search checks. Records
are retained under `build/production-*`. The older benchmark numbers above remain
historical measurements of the isolated variants, rather than new timing claims.

```sh
python3 betawise/tests/mame/asneo/check-biblewise.py --version KJV --case partial-copy --output betawise/research/bible-reader/preallocated-output/build/partial-recheck
python3 betawise/research/bible-reader/preallocated-output/check_bounds.py --version KJV --production
python3 betawise/research/bible-reader/preallocated-output/check_bounds.py --version NKJV --production
```
