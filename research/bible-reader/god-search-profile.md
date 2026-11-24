# Why a full-index God search takes 70 seconds

Measured 2026-11-23, KJV, pinned Neo 3.21 MAME. **Full is the original
IDXEXP02 packed word/chapter index, now supporting word prefixes. It is not the
four-letter-gram index.** The latter is Compact. See [the three-option table](prefix-search.md).

The 70.004 seconds enumerate **every** match. First backend hit takes 0.150 s;
the first visible result takes 1.187 s including chapter loading and UI scheduling.
`God` is case-insensitive prefix search: god, god's, goddess, godhead, godliness,
godly and gods, producing 4,754 occurrences in 4,094 verses. It is not whole-word
God alone.

## Where the time goes

The chapter index retains 936 of 1,189 chapters. It tells us which chapters might
match, not where inside them. Search still reads 492,495 compressed Huffman
symbols. Grammar pruning skips 185,352 rule occurrences, but those rules must
first be identified by decoding the enclosing Huffman symbols.

A frame-end PC sampler collected 4,200 samples during the backend sweep, without
altering guest code. Approximate distribution (sampling, not exact function timing):

| Area | Samples | Share |
|---|---:|---:|
| BibleReadNode, bit refill, big-endian reads, individual bit reads | 3,456 | 82.3% |
| SearchStep | 456 | 10.9% |
| Normalized word-ID mapping | 257 | 6.1% |
| Grammar stack push | 10 | 0.2% |
| Remaining loop/filter work | 21 | 0.5% |

The benchmark performs no LCD writes, no dictionary spelling of the Bible, and
no user-key delays. It includes identical lightweight result count/checksum work.
Only 13.7% of these symbols fit the original eight-bit lookup. Most enter the
bit-at-a-time canonical Huffman fallback; ROM table accesses are bytewise there.
Ten-bit lookup covers 36.4%; twelve-bit covers 65.5%. Larger lookup tables plus
aligned native 68000 table reads remove substantial work without changing payload.

## Measured alternatives

Production PROFILE=0 sizes; timings use the common instrumented backend. ROM
changes are complete-app differences, including code, data and alignment. A5
changes include GOT pointers; these are not total OS/file/stack RAM consumption.
All rows retain the original full chapter index and identical Bible payload.

| Full-index variant | First hit, s | All hits, s | Extra ROM bytes | Extra A5 bytes |
|---|---:|---:|---:|---:|
| Original full index + prefix matching | 0.150 | 70.004 | 0 | 0 |
| Clear completed grammar matcher state sooner | 0.150 | 69.732 | 12 | 0 |
| 10-bit Huffman lookup, native aligned load | 0.150 | 48.506 | 4,078 | 4 |
| 12-bit Huffman lookup, native aligned load | 0.150 | 36.164 | 16,366 | 4 |
| Selective God-prefix verse postings/restarts | 0.185 | 14.642 | 32,238 | 3,922 |
| Selective verse acceleration + 12-bit lookup | 0.185 | 8.333 | 48,604 | 3,926 |

Baseline complete applet is 1,291,506 bytes, A5 3,168 bytes. The lookup tables are
4,096/16,384 bytes; net ROM changes are slightly smaller because code changes too.
They are directly accessed in ROM, with no RAM copy. The original 1 KiB table
remains in the unchanged container, so these are additional table costs.

Clearing the accepted highest NFA bit preserves all partial overlaps. It prunes
more grammar expansions, but does not reduce the 492,495 Huffman symbols, explaining
the negligible gain. Merely storing a better rule-level contains flag will not
solve that bottleneck: search needs symbols or a higher-level seek/skip structure.

## Verse index scope and cost

The selective prototype is deliberately **not a general verse index**. It covers
only the seven God-prefix vocabulary entries; other terms fall back to normal
chapter search. Narrower prefixes and phrases beginning with these words also use
it. It unions verse postings, checks the regular chapter filter, restarts decoding
at each candidate verse, and verifies the phrase normally. It stores no final
word positions; every occurrence still comes from the same matcher.

Data is 31,235 bytes: 24-byte header, 2,380 chapter-base bytes, 24 posting-offset
bytes, 24,564 sparse restart bytes (six per matching verse), and 4,243 delta-coded
posting bytes. A restart is a global verse ID, chapter-relative Huffman bit pointer,
and grammar-leaf skip. No full-Bible restart table is required. The RAM increase
is mostly a 3,888-byte candidate-verse bitmap.

A general all-word verse index using the tested hybrid posting choices is an
estimated 631,878 bytes, before restart data. Straightforward four-byte restarts
for every verse plus chapter bases add 126,788 bytes. Replacing the existing
252,739-byte index this way adds approximately **494 KiB**, not a small increase.
This is a host estimate, not a built or MAME-timed general-index implementation.
Other encodings or selective word policies could improve it.

## Recommendation and status

The 12-bit lookup is the strongest general improvement here: about 1.94× faster
God enumeration for 16 KiB ROM and four bytes A5. The 10-bit option saves ROM while
still improving speed by about 1.44×. Selective verse postings are attractive for
an explicitly chosen set of frequent concordance terms, but the God-only result
must not be extrapolated to every query. Its ~3.8 KiB A5 cost also matters.

These remain opt-in research flags; the ordinary applet/demo defaults are unchanged:
`FAST_BITS=10|12 FAST_NATIVE=1`, `SEARCH_CLEAR_COMPLETE=1`, `VERSE_BOOST=1`.
The verse generator currently selects God prefixes specifically. It is not a
user-configurable common-word policy yet. No battery-energy measurement was made.

## Reproduction and validation

- `profile-god-host.py`: symbol/rule workload and general verse-index sizing.
- `measure-god-builds.py`: six production ROM/A5 builds.
- `check-wide-huffman.py`: all 1,189 chapters decoded byte-for-byte identically
  using 8/10/12-bit tables (same 4,148,083-byte framed output SHA-256).
- `check-prefix-search.py --verse-boost PATH`: independent source-token comparison,
  prefix and whole-word modes, all three index policies; additional narrower God
  prefixes and multiword/overlapping God phrases included.
- MAME checker: `--prefix-bench --bench-query God --search-index full`, optionally
  `--fast-bits 12 --native-fast-load`, `--clear-complete`, `--verse-boost`, or
  `--sample-search`; ordinary pinned-ROM/disposable-session arguments still apply.

Every measured optimized run passed three deterministic source/font bitmap and
cursor checkpoints plus the backend count and ordered checksum (4,754 / 1819816850).
Host verse tests compare every (chapter, verse, word) tuple. Raw records, logs,
PC samples and artifacts live under `.research-work/bible-compression/god-*`;
[structured production/timing/sample results](god-search-profile.json) retain paths.
Normal NKJV streaming demo was restored byte-identically to its previous tested
build, SHA-256 `f9b7b1780bc1ebc49046775a6016584bfb709717565e393337e904e5d64cb034`.
