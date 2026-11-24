# Prefix search: full, compact and scan in MAME

Measured 2026-11-23 on the pinned Neo 3.21 dynamic-clock MAME with KJV and native
full-chapter display. All variants use identical phrase-Huffman text, direct-ROM
front dictionary, grammar pruning and UI/layout code. No codec retraining or
compression change. Search code/assets are the same across the three binaries;
only search metadata and the applet-name suffix differ.

## Semantics and implementation

Search is now **case-insensitive word-prefix matching**. Each of 1–8 query words
is a prefix, and phrase words must be consecutive within one verse. Existing
punctuation/apostrophe tokenization is unchanged. `Methus` matches Methusael and
Methuselah; `God` also includes words such as gods and godly. This is literal
prefix matching, not synonym, typo or stemming expansion.

Normalized vocabulary IDs are lexically ordered. Two binary bounds find each
term's accepted ID interval; no new word dictionary or spelling expansion of the
Bible is needed. Full mode unions the completions' chapter lists and intersects
those unions across query terms. Grammar pruning checks whether a phrase subtree
contains any ID in the first interval, preserving verse/word ordinals.

An eight-bit Shift-And state replaces exact-word KMP: overlapping prefix sets
cannot safely reuse the old KMP failure function. Host tests cover overlapping
phrases (`a a`, `be bel`, `in i`), case, apostrophes and missing words. The
`SearchStartMode(..., prefix_match=0)` API retains whole-word matching;
`SearchStart` and both reader UIs default to prefix matching. There is no new UI
whole-word toggle in this change.

* **Full (original full index, now with prefix matching):** existing IDXEXP02
  packed word/chapter hybrid postings, unchanged; no four-letter grams.
* **Compact:** PFXLEX01 canonical word references and packed normalization map,
  followed by PFXGRP01 four-character word-prefix postings over groups of eight
  chapters. Queries shorter than four characters union matching prefix buckets.
  Candidate chapters are verified by the same ID-range matcher.
* **Scan:** PFXLEX01 only. Known prefixes select all chapters; a prefix with no
  vocabulary completions immediately selects none. Grammar pruning remains.

`search_options.py` derives the latter two from each translation's packed index
and source. Full stays the default; packed/pruned source data now defaults on for
both reader frontends. The old chapter-index input remains supported by Search.c.
No lossy text or result filtering is used in any option.

## Production ROM/RAM

PROFILE=0, no test font/counters; optimized native open and native page command.
All share applet ID **0xA1B1**, so they are alternative installations.

| KJV option | Complete applet bytes | Search metadata bytes | A5 bytes |
|---|---:|---:|---:|
| Full | 1,291,506 | 252,739 | 3,168 |
| Compact | 1,166,684 | 127,917 | 3,168 |
| Scan | 1,088,748 | 49,981 | 3,168 |

Compact saves **124,822 bytes (121.9 KiB)** against full; scan saves **202,758
bytes (198.0 KiB)**. Every build contains 21,242 application code/assets bytes
(**20.74 KiB**, excluding all Bible/navigation/search resources), of which
14,380 bytes are executable. Common text/navigation/pruning resources occupy
1,017,525 bytes. The superscript font remains included in application assets.

The index is read directly in ROM. Dropping it does not shrink the shared RAM
matcher/decoder: all three support the same fixed buffers. The search object is
798 bytes, included in A5. The largest search-function stack frame is 392 bytes;
the compiler's own query-setup call chain sums to about 668 bytes before app
callers/library/firmware frames. This is not a measured whole-stack high-water.
The same chapter file peaks at 4,838 bytes in these first-hit UI cases, additional
to A5; it varies with the displayed chapter. OS/dialog/clipboard RAM is also
additional. Complete-reader RAM must not be described as A5 alone.

## Backend speed

Emulated service seconds, including query initialization and a common lightweight
hit-order checksum/count callback. No display, keyboard gaps or firmware idle
scheduling is included in the backend loop. The checksum overhead is the same
for a given query across options; this is not an energy measurement.

### Time to first backend hit

| Query | Full | Compact | Scan |
|---|---:|---:|---:|
| Methus | 0.152 | 0.368 | 0.369 |
| believ | 0.154 | 0.516 | 1.041 |
| love | 0.139 | 0.526 | 1.521 |
| God | 0.150 | 0.126 | 0.114 |
| in the beg | 0.644 | 0.241 | 0.123 |
| th | 0.829 | 0.183 | 0.098 |

Full can spend more time gathering postings for very broad prefixes before a
match near the beginning. Those cases do not imply scan is faster for later
matches or exhausted searches. Dictionary/grammar/filter setup alone for `th`
is 0.829/0.183/0.098 seconds respectively; the first hit is effectively immediate
once setup completes.

### Time to enumerate every result

| Query | Hits | Full | Compact | Scan |
|---|---:|---:|---:|---:|
| Methus | 8 | 0.347 | 2.643 | 85.426 |
| believ | 322 | 12.204 | 43.796 | 85.552 |
| love | 521 | 17.543 | 56.302 | 85.467 |
| God | 4,754 | 70.004 | 85.270 | 86.175 |
| in the beg | 19 | 25.166 | 66.286 | 88.602 |
| Jesus Jesus | 0 | 17.086 | 21.171 | 86.223 |
| th | 128,223 | 100.693 | 100.047 | 99.962 |

Every option returns identical hit counts, first (chapter, verse, word-ordinal)
positions and complete hit-order checksums, checked against the independent
source tokenizer. All backend loops produce **zero LCD data writes**.

Candidate chapters help explain the difference:

| Query | Full | Compact | Scan |
|---|---:|---:|---:|
| Methus | 3 | 32 | 1,189 |
| believ | 140 | 576 | 1,189 |
| love | 247 | 805 | 1,189 |
| God | 936 | 1,173 | 1,189 |
| in the beg | 273 | 821 | 1,189 |
| Jesus Jesus | 207 | 261 | 1,189 |
| th | 1,189 | 1,189 | 1,189 |

## Interactive first visible result

This separate measurement starts when Find input is accepted and stops after
the actual matching chapter/word is painted. It includes native chapter loading,
wrapping/drawing and cooperative idle scheduling, but excludes typing the query.

| Query | Full | Compact | Scan |
|---|---:|---:|---:|
| Methus | 1.322 s | 3.325 s | 3.325 s |
| believ | 0.931 s | 4.425 s | 8.965 s |
| love | 0.993 s | 4.534 s | 13.967 s |
| God | 1.187 s | 1.137 s | 1.170 s |
| in the beg | 1.506 s | 1.006 s | 1.005 s |
| th | 1.323 s | 0.823 s | 0.822 s |

Find returns on the first match; it does not perform the full-result scan before
displaying that match. Find Next resumes the retained matcher. Exhaustion and
no-hit UI elapsed time can exceed backend service due to the existing 50 ms
cooperative slices and sparse idle callbacks. No new search scheduler or spinner
was added. These results favor **full by default**, compact as a ROM-saving
alternative, and scan when maximum ROM saving is worth potentially long searches.

## Validation, artifacts and reproduction

96 host cases compare every returned hit tuple for all three options in prefix
and whole-word modes. MAME has 21 complete backend query validations, plus 24
exact prefix-result screen states, 40 native regression states and 83 streaming
regression states: **147 screen/state checks**. Streaming regression includes
selection/copy, history, jumps, fonts and applet return. Historical whole-word
fixture expectations were updated from independently tokenized source matches;
expected bitmaps were not derived from failing captures.

MAME uses disposable flash/RAM, original glyph profiles, exact source bitmaps,
cursor assertions before hiding, three identical LCD samples and firmware cursor
restoration. No model/vision oracle. PROFILE=1 timing binaries are separate from
the PROFILE=0 ROM/RAM builds. The profiler reads no decoder state from an external
model and makes no guest text/file substitutions.

Artifacts under `.research-work/bible-compression/`:

* `prefix-search-host/validation`: host runner, serialized inputs, every result
  checksum and source comparisons.
* `prefix-mame-full-v2`, `prefix-mame-compact-v1`, `prefix-mame-scan-v1`: accepted
  runs, raw LCD/editor/cursor records, source/font references, logs, timings and
  independent expected backend hits/checksums. `full-v1` is a rejected harness
  setup run (Python import scope), not a timing input.
* `prefix-search-production/{full,compact,scan}`: production binaries, ELF/maps,
  sources and compiler stack reports.
* `prefix-native-regression` and `prefix-stream-regression`: accepted UI suites.

[Machine-readable results](prefix-search-results.json).

```sh
python3 betawise/research/bible-reader/check-prefix-search.py --output HOST_OUTPUT
python3 betawise/tests/mame/asneo/check-bible-reader.py --version KJV --search-index full --prefix-bench --system-font --profile --native-open-test direct --native-page-test --experiment huffman-prune --output MAME_OUTPUT
python3 betawise/research/bible-reader/measure-search-builds.py --output PRODUCTION
```

Repeat MAME with `--search-index compact` / `scan`, then run
`summarize-prefix-search.py FULL_RUN COMPACT_RUN SCAN_RUN --production PRODUCTION
--output SUMMARY.json`. Normal production builds:

```sh
make -C betawise/applets/BibleReader READER=BibleReader VERSION=KJV SEARCH_INDEX=full PRUNE=1 PROFILE=0 TEST_FONT=0 NATIVE_OPEN_TEST=1 NATIVE_PAGE_TEST=1
```

Change SEARCH_INDEX to compact/scan. Outputs are `BibleReader.OS3KApp`,
`BibleReader-compact.OS3KApp`, `BibleReader-scan.OS3KApp`; VERSION=NKJV adds its
translation suffix before the index suffix. The existing custom NKJV demo is
rebuilt with prefix support, rather than restored to the old exact-search binary.

## Profiling the broad God query

[Decoder profile and verse-posting experiments](god-search-profile.md) explain the
70-second complete enumeration and compare 4/16 KiB wider Huffman lookups, a small
grammar-state change, and selective verse restarts. Full above already denotes
the original pre-gram word index enhanced for prefixes.

[Directional search follow-up](navigation-search.md) now compares find next/previous
from the reading cursor, including a true zero-search-metadata streaming matcher.
The exhaustive timings above remain historical benchmarks, not ordinary UI waits.
