# Direct drawing, compact backward checkpoints and selective concordance

These supersede the streaming-layout measurements in
[device-comparison.md](device-comparison.md). Scope remains KJV on the original
Neo 3.21 firmware in private MAME sessions. No physical power measurements were
made. The native reader still uses the existing file-backed firmware editor;
this is not a benchmark of a separate standalone vendor viewer application.

## A screen bitmap is optional, and direct drawing wins

The 2,112-byte buffer was a one-bit 264x64 raster, not decoded text. The earlier
prototype composited glyphs into it and submitted one OS DrawBitmap call. The
new preferred prototype computes word wrapping itself and invokes OS DrawBitmap
directly for each glyph using the installed font's original bitmap, width and
offset tables. Superscript digits are also drawn directly. No screen-sized or
chapter-sized buffer is required.

The ordinary string interfaces use their own cursor/font layout. This experiment
keeps explicit pixel positioning and arbitrary font pointers while using OS
bitmap drawing; it does not claim a native pixel-positioned string API was found.
`DIRECT_DRAW=0` retains the old raster compositor for comparison. The default
`READER=Streaming` now selects direct drawing.

## Typical chapters and identical cached pages

Matthew 2 is the median-sized chapter by ASCII byte length: **3,284 bytes,
23 verses**. Genesis1 is 4,088 bytes; John3 is 4,005. Measurements below use the
same original system 6x16 font, visible verse numbers, 264x64 display and four
lines per page. They start on a key-driven operation in an already running
applet; boot/menu navigation and reference typing are excluded.

| Operation | Native file-backed editor | Buffered streaming | Direct streaming + full index/pruning |
| --- | ---: | ---: | ---: |
| Fresh Matthew2 initial page | 739 ms | 48 ms | 27 ms |
| Fresh John3 initial page | 839 ms | 49 ms | 28 ms |
| Matthew2 cached redraw | 80 ms | 2 ms | 27 ms |
| Matthew2 next page | 89 ms | 50 ms | 27 ms |
| Following page | 88 ms | 48 ms | 25 ms |
| Previous cached page | 85 ms | 51 ms | 28 ms |
| Cached first page | 85 ms | 49 ms | 27 ms |
| Fresh Matthew2 jump to verse12 | 799 ms | 128 ms | 106 ms |

The native timing taps bracket the firmware work, not the keyboard wait. Native
page movement uses four normal editor arrow commands, as in the current reader.
The tests first position the caret at the appropriate viewport edge, then assert
an exact four-line viewport shift. We did not discover or benchmark an alternate
single-call native page-navigation operation. Native full cached redraw provides
a separate comparison unaffected by that paging implementation.

Streaming timers include checkpoint restoration (when needed), decompression,
layout and drawing. The buffered redraw is deliberately different: it can replay
its retained pixels without decoding. That is its remaining advantage, at the
cost of roughly 2.1 KiB more static RAM. Direct drawing is faster for ordinary
page construction/scrolling and is the preferred tradeoff here.

Each renderer independently passes its source/font bitmap oracle. As an extra
comparison, the initial median page and four forward/backward page captures were
then checked to be pixel-identical between native and direct streaming renderers.
Thus these cached paging timings show the same text pages and wrapping, rather
than different jump-anchored views.

The native median chapter file holds 3,458 formatted bytes plus its 512-byte gap:
3,970 bytes of file content. Allocation capacity/reservations can be larger.
Streaming requests zero files. The latest direct prototype has 1,538 static RAM
bytes without search, or 2,544 with the full search backend. Firmware stack/OS
shared state are additional in every configuration.

## Compact context restores backward pages

A 68000 codec resume point is **10 bytes**:

- Absolute bit position of the current top-level compressed symbol (32 bits).
- Count of top-level symbols preceding that anchor (32 bits).
- Expanded source bytes to replay within that symbol (16 bits).

This reconstructs grammar-stack and dictionary-spelling context by replaying only
the anchored symbol prefix. It does not copy the entire decoder. A page point
adds the source offset, verse/marker state and page number, for **20 bytes**.
The 32-page cache consumes **640 bytes**, plus its validity flags and a pending
word checkpoint. It is bounded; older evicted pages fall back to replay from the
reference anchor without painting intermediate pages. It is a page-start cache,
not a complete chapter line index or a single-line scrolling implementation.
Font/number/reference changes invalidate it.

Both Huffman and word SCDC passed 134,087 host resume-point comparisons each,
across all 1,189 chapters. At every 31-byte source position the verifier saves a
point and compares up to 97 subsequent bytes against uninterrupted decoding.
The host ABI pads the codec struct to 12 bytes; target static assertions enforce
10-byte codec and 20-byte page points. MAME backward-page checks require the
checkpoint-hit counter to advance and verify all resulting pixels.

## Complete streaming/search combination

The combined prototype now includes actual Find entry, exact word/phrase KMP,
Cmd+G next match, the packed exact chapter index and grammar pruning. A search
result starts at its actual word ordinal, not merely the chapter or verse.
It remains a prototype: native selection, clipboard, full reference dialog,
font-dialog integration and previous-result history have not been ported.

| Build | Full ROM | Static RAM | Guest files |
| --- | ---: | ---: | ---: |
| Buffered Huffman + checkpoints, no search | 1,016,350 B | 3,662 B | 0 |
| Direct Huffman + checkpoints, no search | 1,016,084 B | 1,538 B | 0 |
| Direct Huffman + checkpoints + full packed/pruned search | 1,280,782 B | 2,544 B | 0 |
| Same, partial index below | 1,258,174 B | 2,544 B | 0 |

The combined direct build has the same 27/25/28 ms median-page results as the
no-search build. Its complete `Jesus Jesus` no-hit search uses **16.698 CPU s**;
a complete `Melchizedek` search uses **0.164 CPU s**, finding two occurrences.
These profile scans include setup and run without UI idle gaps. Ordinary search
uses bounded 50 ms idle slices, so CPU times are not interactive wall times.
The MAME suite separately verifies real Find/next-result screen anchoring.

## Partial concordance indexes save less than expected

The index stores **chapter presence**, not an entry for every occurrence. Its
hybrid representations already encode very frequent words compactly: `the`
uses three posting bytes and `and` four. Omitting them replaces each list with
a one-byte 'known word, no chapter filter' marker; the query still participates
in exact phrase matching. The full lexicon and normalization map remain.

| Posting policy | Indexed words | Index bytes |
| --- | ---: | ---: |
| Full packed exact index | 12,517 | 252,739 |
| Omit the 30 tested function/stop words | 12,487 | 249,986 |
| Omit 128 words occurring in the most chapters | 12,389 | 235,675 |
| Non-stop words with at least five occurrences | 5,333 | 230,131 |
| Top 2,000 non-stop words by frequency | 2,000 | 196,073 |

These are mechanical frequency/stop-list policies, not an expert-curated list
of theologically important concordance terms. An omitted known word does not
become 'not found': it requires text scanning, while other indexed terms in a
phrase can still restrict candidate chapters. The partial backend also passes
the 15-query host occurrence oracle.

The 5,333-word policy was benchmarked in the same combined direct prototype:

| Complete search | Full index | Partial index |
| --- | ---: | ---: |
| `Jesus Jesus`, zero matches | 16.698 s | 16.698 s |
| `Melchizedek`, two matches | 0.164 s | 84.469 s |

`Jesus` remains indexed in both. `Melchizedek` is omitted by the frequency
threshold, forcing a full corpus scan instead of two candidate chapters. That
is over 500x more CPU for only 22,608 saved ROM bytes (about 1.8% of the combined
applet). Rare words are often precisely what a concordance is used to find, and
their short posting lists are cheap. Keep the full packed index unless a hard ROM
limit justifies a carefully chosen partial vocabulary. Simply dropping `the`
provides almost no saving.

## Verification and a harness correction

Final safe-entry captures cover:

- Native system-font median/layout benchmark: 12 checks, plus the full 36-check
  native reader acceptance regression.
- Direct system-font layout/checkpoint prototype: 22 checks.
- Combined direct full-index system-font reader: 27 checks.
- Combined direct partial-index system-font reader: 27 checks.
- Combined direct full-index Small proportional 11px font: 27 checks.
- Direct Extra Large proportional 32px font: 22 checks.

The Small-font direct run exposed a test-harness bug, not a renderer mismatch:
a frame-end 68000 PC can point at an instruction extension word. Restoring that
value as a fresh opcode corrupted execution after a capture. The failed records
show original PC 0x4233d0, the operand of the instruction starting at 0x4233ce.
The Bible harnesses now wait for the verified Neo3.21 ROM instruction entry
0x426758 (`move.w SR,D0`) before injecting the real cursor-mode calls. They still
check cursor geometry first, preserve registers/scratch RAM, observe hide/restore
returns and retain three identical LCD samples. Streaming additionally records
and asserts unchanged original stack bytes. The corrected Small run passes all
27 checks. Failure records remain under `layout3-combined-direct-small*`.

No Neo screenshot/model inference was used. Expected pixels come from explicit
source text and verified original font assets. Each controller flag, hidden
cursor state and applicable native viewport/word anchor is independently checked.

Raw evidence is under `.research-work/bible-compression/layout3-*`; aggregate
results are [layout-checkpoints-results.json](layout-checkpoints-results.json).
The earlier buffered comparison passes 22 checks but is retained as a historical
pre-safe-entry timing comparison. Full final binaries are copied in each tested
session's `artifacts` directory.

## Reproduce

From the workspace root, use new output directories:

```sh
python3 betawise/research/bible-reader/partial_index.py
python3 betawise/research/bible-reader/check-checkpoints.py --output /tmp/checkpoints-new
python3 betawise/tests/mame/asneo/check-bible-reader.py --system-font --profile \
  --layout-bench --output /tmp/native-layout-new
python3 betawise/tests/mame/asneo/check-bible-stream.py --direct --combined \
  --experiment huffman-prune --output /tmp/stream-combined-new
python3 betawise/tests/mame/asneo/check-bible-stream.py --direct --combined \
  --experiment huffman-prune-partial --output /tmp/stream-partial-new
```

`check-bible-stream.py` selects buffered drawing unless `--direct` is passed, so
both modes remain explicitly testable even though the applet Makefile defaults
to direct drawing for Streaming. `--vendor-font small` or `xlarge` selects the
verified original proportional font. Benchmark shortcuts A/B/C select Matthew
2:1, Matthew2:12 and John3:1; R redraws; N/P page. Native shortcuts are available
only in PROFILE=1 builds.

To build the full tested combined prototype:

```sh
make -C betawise/applets/BibleReader READER=Streaming TEST_FONT=0 \
  STREAM_SEARCH=1 PRUNE=1 PREBUILT_DATA=1 \
  DATA_DIR=../../../.research-work/bible-compression/device-comparison/huffman-prune
```

It has the same 0xA1B1 alternative-installation ID. The default published applet
remains the native KJV reader; the default streaming build is the direct,
checkpointed no-search prototype. Both defaults and the combined direct build
were rebuilt byte-identically to their corresponding passing test artifacts.
