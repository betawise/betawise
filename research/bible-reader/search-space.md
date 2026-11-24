# KJV search-space experiments (host only)

The applet is unchanged. These experiments use the exact ASCII KJV source and
trained phrase grammar from the current production resource. No emulator,
physical-device timing or battery measurements were run.

## Exact index compression is the strongest immediate size improvement

The production 368,039-byte index stores delta-encoded chapter postings. An
experimental hybrid picks the shortest representation for each word: delta,
Elias–Fano, bitmap, complement delta, or complement Elias–Fano. Its size is
268,818 bytes. Packing canonical terminal IDs and posting offsets into 32-bit
records (14 + 18 bits), plus a 14-bit terminal-normalization map, reduces it to
**252,739 bytes**. This retains exactly the same candidate chapters, saves
**115,300 bytes**, and does not change the compressed Bible text.

All 12,517 posting lists round-trip exactly. Packed IDs, offsets, normalization
markers and unchanged payloads are checked after serialization. Elias–Fano
encodes sorted values as packed low bits and a unary high-bit vector. The hybrid
uses it only where it beats the alternatives. There are 10,858 delta lists,
1,479 Elias–Fano lists, 151 bitmaps, 25 complement Elias–Fano lists and four
complement delta lists. The decoder would need new native code; the saved-byte
figure excludes that unimplemented code and its speed is not established.

Grouping chapters trades additional scanning for a smaller index:

| Index | Bytes | Chapters examined for `believe` | Chapters for `Jesus Jesus` |
| --- | ---: | ---: | ---: |
| Current exact chapter delta | 368,039 | 82 | 207 |
| Packed exact hybrid | 252,739 | 82 | 207 |
| Packed hybrid, groups of 2 | 213,327 | 140 | 239 |
| Packed hybrid, groups of 4 | 180,845 | 220 | 253 |
| Packed hybrid, groups of 8 | 155,248 | 328 | 253 |
| No postings, retain query lexicon/map | 53,542 | 1,189 | 1,189 |

Grouping intersects groups first, then verifies text in their chapters. It has
no false negatives, but adds candidate chapters. An unknown query word still
terminates without scanning. Eliminating the remaining lexicon/map would require
another query-to-terminal strategy; zero additional search-index ROM is not a
measured implementation here.

Chapter Bloom filters were also measured at 128–4,096 bits per chapter. The
512-bit variant uses 129,638 bytes but scans 172 chapters for `believe` and 591
for `Jesus Jesus`. Its hash generation/lookup implementation is not device-ready;
the size excludes any precomputed per-word hash table. Coarse exact grouping is
a clearer option to try first. Full per-query scan-volume counts remain in the
private experiment results; terminal counts are work proxies, not cycle counts.

## Byte-aligned codes

[The dense-code authors' description](https://vios.dc.fi.udc.es/codes/semistatic.html)
provides the ETDC and (s,c)-Dense Code definitions. The host prototype assigns
codes by descending frequency. ETDC uses 128 stopper and 128 continuer bytes;
SCDC chooses the best split exhaustively over 1–255 stopper values.

These are complete experimental text-resource sizes, including the existing raw
front dictionary, metadata, rank table, grammar where applicable, and chapter
framing. They exclude search indexes and the existing hot spelling cache:

| Text encoding | Bytes |
| --- | ---: |
| Production phrase Huffman, including hot cache | 1,007,155 |
| Plain word ETDC | 1,363,110 |
| Plain word SCDC, 223 stoppers / 33 continuers | 1,312,693 |
| Existing phrase grammar + ETDC | 1,167,618 |
| Existing phrase grammar + SCDC, 211 / 45 | 1,134,805 |

Every chapter round-trips to exact original ASCII, including case, punctuation
and whitespace, in all four dense variants. Each experimental resource is
serialized; the chapter symbols are decoded from their byte streams and phrase
rules expanded to verify the original text.

Direct compressed single-word search was checked for God, Jesus, believe,
believed and LORD's. It includes every capitalization/leading-space spelling
variant and checks a valid preceding codeword boundary. All occurrence counts
match the independent source tokenizer. The stopper tag prevents interior-byte
false matches once the start boundary is checked.

A compiled host C KMP decoder also checks all matching (chapter, verse,
word-ordinal) tuples for 14 queries in both word-code variants. It ignores
punctuation, resets at verse boundaries, handles overlaps and distinguishes
inflections. Its test-only normalization table costs 28,488 bytes and is **not
included** in the text-resource figures. A device implementation could instead
match per-query sets of spelling/rank variants; that approach is not implemented.
The measured host process times include launch/output overhead and do not predict
Neo performance.

Phrase dense codes are smaller but retain the grammar problem: query text does
not have one context-independent encoded pattern. A match can start inside one
phrase symbol and end in another. They still need grammar-aware matching.
Likewise, native punctuation-insensitive, case-insensitive phrase semantics do
not reduce to one direct byte search even in the plain word stream.

The phrase SCDC resource plus the 53,542-byte query lexicon/map would total
1,188,347 bytes before applet code/fonts: 186,847 bytes below today's combined
text/index resources. It would scan every chapter for known words. This is an
interesting future speed/space alternative, not a demonstrated Neo improvement.
Keeping the packed exact index instead gives 1,387,544 bytes, slightly above
today's combined 1,375,194-byte resources.

## Grammar pruning without changing Huffman coding

For each query, compute a 2,048-bit (256-byte) bitmap saying which phrase rules
contain its first normalized word. At KMP state zero, a subtree lacking that
word cannot contain a match. Skip its expansion and update verse/word counters
using static summaries. A partially matched query still expands relevant text,
so matches spanning symbols remain correct.

The summaries need total words, newlines, and words after the last newline.
All three fit in one byte for every current rule (largest field is 10), so
2,048 rules require 6,144 ROM bytes. A target implementation can build only the
rule bitmap bottom-up, using the existing normalization map for terminal tests;
the Python prototype uses larger host lists for convenience.

All occurrence positions match the source oracle for all 14 queries. For a
full-corpus `Jesus Jesus` scan, visited terminals fall from 946,456 to 373,443;
visited tree nodes are 607,855. All 605,623 top-level symbols would still require
Huffman decoding. The current chapter index scans only 207 chapters for this
query, so these full-corpus counts must not be compared directly with the prior
17.325-second indexed Neo measurement. Combining pruning with the exact index
is possible but has not been implemented or timed on Neo.

The next device experiment should start with the packed exact hybrid index,
then independently test grammar pruning. Byte-aligned phrase SCDC with a reduced
or absent chapter index is a separate alternative if the size/speed tradeoff
warrants a codec change.

## Reproduction

From the workspace root, choose a new output directory:

```sh
python3 betawise/research/bible-reader/search_space.py \
  --output .research-work/bible-compression/search-space-new
python3 betawise/research/bible-reader/compact_search_index.py \
  .research-work/bible-compression/search-space-new
python3 betawise/research/bible-reader/grammar_search_pruning.py \
  .research-work/bible-compression/search-space-new
```

Reviewed run: `.research-work/bible-compression/search-space-kjv-verified/`.
Aggregate results and provenance are in
[search-space-results.json](search-space-results.json). Encoded resources and
source text remain outside the source repository.

## Deferred position/notes design

The local firmware API explicitly provides `TextEditorSavePosition`, which saves
the viewport into the current file's position, and `FILE_OPEN_KEEP_POSITION`.
We can use those when retaining the chapter file. The current applet instead
rebuilds it on entry and saves translation/chapter/verse/number visibility in a
16-byte state file. Retaining the file would avoid decoding on reopening, but
needs chapter identity and validity checks. This task makes no applet changes.
The native API promises a viewport position, not complete selection/caret state.

Notes remain deferred; the storage format is undecided. Established
scripture formats include [OSIS verse-addressed commentaries](https://wiki.crosswire.org/OSIS_Commentaries)
and [USFM/USX/USJ](https://docs.usfm.bible/usfm/latest/introduction.html), whose
common publishing model includes notes and has a JSON representation. USJ is the JSON representation of the USFM content model; JSON Lines is not
a selected format. A custom JSON record is not automatically either standard. Stable reference IDs
and explicit versification would preserve an export path without adopting their
entire document structures on the device.


## 2026-11-23: word-prefix matching and smaller filters

The full packed index above is now implemented/device-tested in the reader.
Word-prefix matching itself is not yet implemented: its existing sorted normalized
vocabulary allows a lower/upper-bound range lookup, union of those words' chapter
postings and source verification. It needs no additional index data or change to
the Huffman text format. Prefix phrase matching must handle overlapping word sets;
blindly substituting range comparisons into the exact-word KMP failure table is
not correct. An eight-term bit-parallel matcher is one small alternative.

New **host-only** sizing uses the production ASCII KJV. `prefix_filter.py` writes
three/four-letter word-prefix keys with hybrid postings for individual chapters
or groups of four/eight chapters. It serializes/reads back every bucket and
checks candidate containment for six example queries. New indexes are prototypes,
not an applet format already supported by Search.c. No MAME speed is claimed.

| Search metadata | Bytes | KiB | Candidate chapters for `Methus` |
|---|---:|---:|---:|
| Full exact word/chapter index, union completions | 252,739 | 246.8 | 3 |
| Four-character prefix, groups of eight chapters | 127,917 | 124.9 | 32 |
| Three-character prefix, groups of eight chapters | 81,888 | 80.0 | 328 |
| Lexicon/map only, no chapter filter | 49,981 | 48.8 | 1,189 |

The prospective compact lexicon/map is serialized too: 20 header bytes, two-byte
canonical terminal IDs and the existing 14-bit terminal-normalization map. It is
smaller than the older 53,542-byte uncompressed-map example above. Prefix rows
include that 49,981-byte component plus actual serialized filter bytes. Numbers
exclude application support code and the common 6,144-byte grammar summaries.
`Methus` expands to `methusael` and `methuselah`; their exact union spans three
chapters. A four-character individual-chapter filter takes 212,480 bytes and
selects five chapters, so it saves relatively little against the full index.

For overlapping character n-grams, candidate lists are intersected, then matches
verified for order/position. Prefix word alternatives are instead unioned. A
four-gram index is unnecessary just to add word-start prefixes to the existing
full word index. Arbitrary substring/fuzzy matching would be a separate policy.

No-postings search can retain grammar pruning and match word IDs without
expanding all text into spelling bytes, but it still scans the compressed stream
across the Bible. Grouped filters can skip entire chapter groups. Selective word
postings omitted above preserve prefix correctness only if omitted completions
are treated as unrestricted candidates; silently dropping them causes misses.

Artifacts: `.research-work/bible-compression/prefix-filter-host/`; reproducible
with `python3 betawise/research/bible-reader/prefix_filter.py`. See
[prefix-filter-results.json](prefix-filter-results.json). No reader build/default
was changed. These results support investigating an optional compact-index build;
they do not establish its device speed or finalize its binary interface.


The later [implemented prefix-search comparison](prefix-search.md) now provides
MAME timings for full, compact and scan, production ROM/A5 sizes and exact
source-backed regression checks. It supersedes the host-only speed uncertainty
above; all variants retain the same Huffman text.
