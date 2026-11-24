# ROM-resident KJV reader: representation experiment

Output retention and regeneration: [2026-11-24 cleanup guide](cleanup-20261124/README.md).

Current costs: [application-only ROM and maintenance metrics](reader-costs.md),
with compact native superscript fonts.

Latest: [unified Find and navigation UI](unified-find.md).

Earlier UI work: [native reader review and vendor dialog evidence](ui-review.md).

Previous: [production simplification](simplification.md): native whole-chapter editor,
one codec and Full index, with the original experiments [archived for regeneration](prototype/REPRODUCE.md).

Previous: [Same verse, Exact phrase and Nearby search](search-modes.md),
with explicit trailing wildcards, source validation and Full/Compact MAME timings.

Previous: [find next/previous and true no-index search](navigation-search.md),
with navigation timings from three Bible locations and full/compact/scan/none comparisons.

Previous: [prefix search and full/compact/scan index options](prefix-search.md),
with KJV MAME first-hit/full-scan timings, ROM/RAM and matching-result validation.

Previous: [prewrapped native text](native-prewrap.md) supplies cached breaks without
private layout calls: 0.345 s first screen, 4.162 s chapter page-through, and
634 passed screen/state checks. Whole-chapter prewrapping is also compared.

Previous: [native layout disassembly and private viewport prototype](native-layout-disassembly.md):
full-file reflow identified, faster append-only reading demonstrated, long-selection
regression remains in the private experiment.

Previous: [native TextScanInsert page lookahead](native-lookahead.md), with zero
LCD data writes during append, but a retained growing-prefix processing cost.

Previous: [native moving-window, on-demand and background prototypes](native-streaming.md),
with complete read-through speeds, production ROM/A5 sizes and file RAM.

Previous: [native editor API usage follow-up](native-overhead.md) finds redundant
reconciliation and uses the firmware page command, nearly tying streaming.

Previous measurement: [complete Psalm 119 read-through](readthrough.md), comparing
native whole-chapter storage with streaming for line and page scrolling.

Current UI: [reader UI revision](reader-ui.md), with full-panel font spacing,
chapter-anchored jumps, incremental selection and system-font centered panels.

[NKJV streaming demo with all five vendor fonts](reader-ui.md) is now available,
with 83 deterministic MAME checks and translation-specific build outputs.

Earlier: [streaming viewer with selection and LCD roll](streaming-viewer.md),
including production ROM/RAM totals and native-editor speed comparisons.
The [65-row panel investigation](lcd-and-controls.md) fixes MAME's omitted
last row and documents Find/reference controls.

**Reader applet:** the [native-editor BibleReader](prototype/README.md)
now provides installed fonts, superscript numbers, reference jumps, exact search
and verse copying with citations. It defaults to the repo KJV; optional translation
builds share applet ID 0xA1B1. The experiments below retain their original corpus
and artifact measurements.

**Current recommendation:** [ASCII Huffman speed measurements](huffman-speed.md)
now favor the 1,009,276-byte direct-ROM dictionary profile: 894 ms to decode
Psalm 119 and 70 ms per page in MAME. The prototype defaults to this profile.
The earlier UTF-8 format experiments below are retained as historical results.

Research performed 2026-11-20. This is a host-side format/codec experiment,
not a finished SmartApplet or a target performance qualification.

**Follow-up:** [small contextual models](context-models.md) improved the best
self-contained image to **948,662 bytes**, using previous-word probabilities,
arithmetic coding and Huffman-coded dictionary suffixes. The original results
and format below are retained as the baseline.

**Native prototype:** [MAME measurements](mame-prototype.md) now demonstrate a
working ROM-resident applet: about **0.39 s per page**, with an eight-verse seek
index reducing Psalms 119:176 from **17.33 s to 0.83 s**. The full indexed applet
is 1,024,178 bytes; the native decoder workspace is 1,524 bytes.

**Translation comparison:** the formatted-source KJV, NKJV and ESV compress to
944,016, 972,830 and 951,659 bytes respectively, before the optional verse seek
index. [Source/annotation details and results](translations.md) distinguish
plain text from the separately preserved formatting and note bundles.

## Recommendation

The initial experiment recommended independently seekable chapters, a shared word dictionary, a small
shared phrase grammar, and canonical Huffman codes. Front-code the dictionary
in blocks of 16 entries. Keep all dictionaries, grammar, Huffman symbol maps,
chapter records and compressed text in applet ROM; stream decoded text into
the display/layout code. Do not decompress the Bible into RAM.

The implemented optimized experimental image is **1,025,262 bytes** (1001.2 KiB,
24.71% of the normalized UTF-8 text). It includes the complete 66-book text,
book names, chapter index, chapter CRCs, dictionary, phrase grammar, code lengths
and canonical-order symbol map. All **1,189 chapters / 31,102 verses** were
reconstructed byte-for-byte, seeking chapters independently in reverse order
from the saved binary. This is the strongest measured candidate here, not a
proof of globally optimal compression.

## Source and fidelity

Project Gutenberg was unavailable. Obtained `json/en_kjv.json` from
[thiagobodruk/bible](https://github.com/thiagobodruk/bible), pinned to
[`df0860fe0921b5b899d1b554041900ab072cd4c4`](https://github.com/thiagobodruk/bible/commit/df0860fe0921b5b899d1b554041900ab072cd4c4).
The pinned URL, exact source hash, size and host versions are in `source.json`.
The downloaded moving-branch file and pinned-revision file matched exactly.
The original JSON is retained in the workspace's `.research-work/bible-compression`.
This corpus is the 66-book KJV without Apocrypha.

Only JSON framing is removed: each source verse becomes its exact UTF-8 text
plus LF. Book/chapter relationships live in the index; verse numbers are ordinal
positions between LFs. No lowercasing, punctuation rewriting or guessed spaces.
The result is 4,148,450 bytes, SHA-256
`2a05d336e4c4401f6369e0f7cc312ddde853ba62887e8a89a98936a6f0f45d2b`.
This verifies codec fidelity to this source, not scholarly accuracy of the
transcription. Upstream itself notes potential conversion issues; audit the
edition before shipping. Source footnotes, italics and paragraph structure not
present in the JSON cannot be reconstructed by the codec.

There are 1,996 curly apostrophes, 93 `æ`, three `Æ`, eight ellipses and one
em dash. These are preserved. A Neo renderer needs explicit verified glyph
support or a documented display conversion; silently dropping them is wrong.

## Measured comparison

Sizes below include book/chapter framing except the explicitly whole-file
archive baselines. Native reader code, font, search index and saved bookmarks
are not included. The detailed results retain exact byte sizes and hashes.

| Representation | Bytes | Access / working set |
| --- | ---: | --- |
| Raw UTF-8 + index | 4,168,819 | Chapter seek; stream bytes |
| Byte Huffman | 2,307,035 | Chapter seek; small decoding state |
| Dictionary, fixed 14-bit IDs | 1,870,944 | Chapter seek; ROM lexicon |
| DEFLATE, chapters, 1 KiB window | 1,767,865 | Chapter seek; history plus decoder state |
| DEFLATE, chapters, 4 KiB window | 1,670,904 | Chapter seek; history plus decoder state |
| DEFLATE, chapters, 32 KiB window | 1,667,230 | Chapter seek; little gain over 4 KiB |
| LZ4 HC, chapters | 2,394,950 | Chapter seek; output history/buffer |
| Word Huffman, plain dictionary | 1,229,013 | Compact storage; lengths scanned or map added |
| Word Huffman, front dictionary + ROM symbol map | 1,150,713 | Chapter seek; no LZ history |
| Front dictionary + 2,048 phrases + Huffman + ROM map | **1,025,262** | Chapter seek; bounded phrase stack |
| Whole-file zlib | 1,211,106 | Baseline only: no chapter restart index |
| Whole-file bzip2 | 871,397 | Baseline only: not a qualified embedded reader |
| Whole-file xz, preset 9 | 906,224 | Baseline only: large dictionary, no chapter restarts |

`results.json` contains the main run. `alternative-results.json` records the
singleton, alternating-alphabet and classic LZSS experiments. Alternative totals
include explicitly accounted table/framing sizes; their `.payload` files are
compressed streams, not complete self-describing packages. Unlike the optimized
grammar image, those alternatives are sizing experiments rather than standalone
serialized container implementations. Their streams all round-trip chapterwise.

### Follow-up ideas: measured results

These comparisons all include front-coded dictionaries, canonical-order ROM
maps and the same 20,369-byte book/chapter framing budget:

| Variant | Bytes |
| --- | ---: |
| Word Huffman baseline | 1,150,713 |
| Escape singleton tokens, raw UTF-8 spelling | 1,147,032 |
| Escape singleton tokens, byte-Huffman spelling | **1,130,979** |
| Alternating word/separator Huffman dictionaries | 1,152,545 |
| Alternating dictionaries + raw singleton escape | 1,146,418 |
| Classic LZSS, 1 KiB history, 6-bit match length | 2,328,770 |
| Classic LZSS, 2 KiB history, 5-bit match length | 2,161,179 |
| Classic LZSS, 4 KiB history, 4-bit match length | 2,113,328 |

Singleton escape works: 4,768 one-occurrence tokens leave the main lexicon.
Each is encoded as ESC, an eight-bit UTF-8 byte length, then its spelling.
Huffman-coding spelling bytes saves 19,734 bytes versus the comparable word
baseline (1.71%); raw literals save only 3,681 bytes. This is why dictionary
savings must be weighed against the one-time literal text and escape overhead.
The literal-byte codebook is conservatively budgeted at 512 bytes. In this
experiment singleton removal means tokens, including a possible leading space;
the alternating variant instead removes 4,418 singleton words.

Alternation has separate Huffman models for words and separator runs, with
empty strings in both alphabets. Insert an empty entry whenever needed to
preserve strict word/separator alternation. Consecutive spaces/punctuation can
also be one separator-run entry. Reconstruction is exact, with 13,756 word
entries and 84 separator entries. The result is just 1,832 bytes larger than
the word baseline: a reasonable design, but no compression win on this corpus.
Combining it with raw singleton escapes helps modestly. Other tokenizations,
per-context models, phrase combinations and escape thresholds might change
these results; those combinations have not all been explored.

The phrase candidate beats the best singleton experiment by 105,717 bytes.
These gains are not assumed additive: combining phrase coding with singleton
escapes needs its own measured format. Prefer the already verified phrase
candidate as the first native-decoder implementation.

The classic LZSS tests are LZ77-family encodings: flag bytes select literals
or two-byte distance/length matches. They are simple to stream and chapter
seekable with 1–4 KiB of history, but substantially larger here. DEFLATE adds
Huffman coding to LZ77 and improves size to 1.67 MB with a 4 KiB history. All
of these are viable architecture choices; measured 68000 speed/code/RAM is
still needed to choose among them for a shipping reader.

## Why these representations

The fixed-width suggestion is valid: this exact tokenizer produces 14,417
dictionary entries, so 14 bits suffice. But 951,750 token occurrences still
consume 1,666,013 bytes before dictionary/index costs. Huffman assigns short
codes to frequent words and punctuation and long codes to rare names. Byte
Huffman misses whole-word repetition and is much larger.

Tokenization attaches one literal preceding ASCII space to a word when present;
everything else, including repeated spaces, line feeds and non-ASCII characters,
is explicitly represented. This avoids fragile grammatical spacing rules.

The phrase stage repeatedly replaces common adjacent symbol pairs, never
across chapters. It adds up to 128 pairs per pass over 16 passes. Every phrase
is two 16-bit references to older symbols. The measured maximum expansion depth
is five, so expansion needs only a small explicit stack. This is a simple
Re-Pair-like grammar heuristic, not the exact globally most frequent-pair
algorithm, and not a sliding-window LZ77 decoder.

Dictionary compression stores the first word of each 16-entry sorted block
fully, then a byte prefix length and NUL-terminated suffix for each later word.
A block offset allows lookup by decoding at most 16 very short entries. The
longest terminal is 17 UTF-8 bytes. This cuts the terminal dictionary from
184,562 bytes (strings + four-byte offsets) to **77,420 bytes**. The optimized
image additionally spends 49,395 bytes on code lengths and a ROM symbol map,
8,192 bytes on phrase pairs, 20,369 bytes on header/book/chapter records and
869,886 bytes on chapter payloads.

## RAM, seeking and Neo integration

The existing `os3k/os3k.lds` places `.rodata` in ROM, and `os3k/crt0.S` copies
only the GOT/initialized writable data into RAM. Embed the corpus as a single
const byte blob or assembly `.rodata` section. Use relative offsets inside it,
not thousands of relocated C pointers. Read multi-byte fields bytewise or with
alignment-safe helpers: applet placement promises only two-byte alignment.

`os3k/os3k.h` documents recognized flash capacities of 2 or 4 MiB; actual
available applet space must be queried on the target. The emulator guide's
4-MiB layout starts applets at flash offset `0x70000`; that is not a guarantee
that any particular user's device has room beside its installed applets.

Chapter records are 16 bytes: payload-relative byte offset, compressed size,
decoded symbol count and reconstructed chapter CRC-32, all big-endian uint32.
Chapters are byte-aligned independent Huffman streams. A verse jump currently
starts at that chapter and counts LF delimiters. The largest uncompressed
chapter is only 13,019 bytes and can be streamed; it need not be buffered.
Seeking a chapter does not decode preceding chapters or books.

This is chapter-random-access, not constant-time direct access to every verse.
If target timings justify finer access, add verse groups with their own restart
boundaries. A bit offset alone is insufficient if it lands inside a phrase:
either prohibit phrases across restart boundaries or record expansion state.
Encoding every verse independently also adds alignment/index costs and can
reduce phrase compression, so measure it before choosing that design.

A target decoder can keep canonical counts/first-code/first-symbol summaries
in a few hundred bytes (or precompute them in ROM), read the symbol map from
ROM, and expand a phrase with a tiny stack. Front decoding needs two short
word buffers. No whole lexicon, chapter or sliding window is required in RAM.
These are design budgets, not measured 68000 stack/RAM or speed figures.
The Python verifier deliberately uses larger host data structures.

Prototype format magic is `KJVGRMF1`; the 64-byte header has seven big-endian
uint32 fields: metadata bytes, terminal count, total symbol count, front lexicon
bytes, chapter count, normalized text bytes, phrase count. Sections follow:
compact JSON book metadata; one byte per symbol's code length; uint16 symbol
IDs in canonical order; front lexicon (ceil(terminals/16) uint32 offsets then
prefix/suffix records); phrase pairs; chapter records; payload. Production
firmware needs explicit limits, corrupt-input handling, decoded output limits,
edition/version identification and container integrity checks before use.
The current verifier validates encoder output; it is not a hardened parser.

## Search and general ebooks

Do not assume a word dictionary is a full-text search index. Initially stream
chapters and compare normalized expanded words, reporting book/chapter/verse.
Search must expand phrases, not scan only top-level symbol IDs. A small
word-to-book/chapter filter could reduce scans; a full positional/inverted
index is a separate ROM budget. Keep stop words in the readable text.

For an ebook reader, convert EPUB on the host into normalized content plus
paragraph/style/navigation markers, then pack it into a ROM resource applet.
The same dictionary/grammar method can be trained per title or collection.
Compression ratios must be measured on those books. Supporting EPUB ZIP/XHTML
directly on the Neo adds parsing and layout work without being required for
this ROM-first reader. General books also need not fit wholly in RAM if they
are streamed from independently seekable flash blocks.

## Reproduce

From the workspace root, download the pinned URL in `source.json` to
`.research-work/bible-compression/kjv.json`, verify its SHA-256, then run:

```sh
python3 betawise/research/bible-reader/measure.py \
  .research-work/bible-compression/kjv.json \
  --output .research-work/bible-compression/results
python3 betawise/research/bible-reader/alternatives.py \
  .research-work/bible-compression/kjv.json \
  --output .research-work/bible-compression/results
```

Python standard library suffices; the LZ4 comparison runs only when python-lz4
is installed. The measured host has python-lz4 4.0.2+dfsg. LZSS uses a greedy
64-candidate hash-chain encoder, not an exhaustive optimal parser. Neither
script accesses the network, firmware, display captures or saved device data.
No target UI was changed, so Neo screen regression was not used for this work.

## References

* [Dan Watt: text compression](https://www.danwatt.org/2021/04/studying-an-old-e-reader-for-fun-text-compression-1/)
  motivates separating text storage from search and handling random access.
* [Dan Watt: Huffman dictionary compression](https://danwatt.org/2021/04/compressing-a-dictionary-with-huffman-codes/)
  discusses compressing the lexicon itself; it does not establish our measured
  whole-text codec results.
* [Franklin's electronic-text patent, US5153831A](https://patents.google.com/patent/US5153831A/en)
  describes a lexicon, text/search subfiles and linked repeated-word references.
  These experiments do not implement its forward-reference search scheme.
* [DEFLATE specification](https://www.rfc-editor.org/rfc/rfc1951)
  documents LZ77 plus Huffman coding and bounded history.
* [LZ4 block specification](https://github.com/lz4/lz4/blob/dev/doc/lz4_Block_format.md)
  describes byte-oriented matches/literals without an entropy backend.
* [heatshrink](https://github.com/atomicobject/heatshrink) is another viable
  embedded LZSS implementation with configurable streaming history. It was
  researched but not benchmarked here; the custom LZSS numbers are not
  heatshrink measurements.

## Formatting storage experiments (2026-11-24)

The [host experiment suite](formatting/run.py) and
[verified results](formatting/results.json) compare chapter-seekable style and
layout sidecars, inline phrase-Huffman controls, word defaults, heading pools
and small canonical Huffman models. Production formatting remains disabled;
the renderer and any additional font data/code are not included in these sizes.

KJV's pinned source has 31,102 paragraph-start flags, one at every verse start,
with no exceptions. One translation-level default replaces all of them. It has
6,883 small-caps words and 41,809 red-letter words, but no italic, bold, poetry
line-break or indentation flags. All 1,189 level-one chapter titles are exactly
book name plus chapter and can be generated. Preserve the remaining 138
headings/superscriptions, including Psalm 119's alphabet sections.

Additional resource bytes for KJV typography and non-generated headings:

| Representation | Bytes |
|---|---:|
| Gamma-coded style sidecar plus compressed headings | 18,741 |
| Inline Huffman style controls plus compressed headings | 13,927 |
| Inline controls with per-book word defaults plus headings | 5,926 |
| Separate sparse sidecars with word defaults plus headings | **5,105** |
| Same sidecars, preserving red-letter metadata too | **7,117** |

The recommended 5,105-byte layout splits into 2,352 bytes of styling and 2,753
bytes of headings. A 45-byte per-book default table references the existing
normalized IDs for god, jehovah, lord and lord's. Residual runs describe the
exceptions; a tagged delta makes length-one runs implicit. Per-chapter defaults
were tested too, but their larger tables cost more than they saved. Sparse
chapter bitmaps plus offsets omit empty chapters. All component headers, model
tables, offsets and byte padding are included.

Heading text is deduplicated and front-compressed in blocks of sixteen strings,
then each block is independently Huffman coded. The canonical model is only
107 bytes: counts by code length plus ordered byte symbols, without a 1-KiB fast
lookup. This shrinks the heading dictionary from 2,801 to 1,823 bytes; location/
level records and chapter lookup make the complete heading resource 2,753.
Huffman coding the small style-exception streams made them slightly larger.
Reusing the Bible's word/grammar/Huffman model for headings was also larger than
a dedicated front-compressed heading pool.

Sidecar trials verify that container.bin, search.bin, pruning.bin and verses.bin
remain byte-identical. Four inline alternatives retrained grammar/Huffman and
rebuilt the Full index; all 1,464 production C search cases matched the original
source oracle. Production C decoding checked 3,158,524 atom styles across those
four streams, as well as exact plain text. Inline word defaults still cost more
than the best sidecars. Header text stays outside the verse search index.

This schema also stores italics, bold, alignment, indentation and internal line/
paragraph breaks. All six translations were audited and their marker streams
round-tripped. NKJV, for example, has 22,847 italic atoms: italics alone take
25,968 bytes with a compact byte-Huffman run stream. Its complete typography,
headings and layout sidecar trial takes 112,600 bytes, or 114,267 with red-letter
metadata. Thus the very small KJV result must not be interpreted as a size
estimate for restoring missing KJV italics from another source.

For other translations, 22 NKJV, 22 NIV and 110 CSB headings contain actual
Hebrew acrostic letters beside Latin transliterations. The research ASCII
conversion removes only the Hebrew glyph prefix and retains its Latin name;
it does not treat these letters as OCR errors. KJV needs no such mapping.

A future formatter must keep canonical word positions separate from native
encoded-file offsets and inserted heading text, including for clipboard and
search navigation. Metadata round trips do not prove native rich-text rendering.
The private fourth font face currently used for superscripts also needs a plan
if combined bold-italic text is supported. No renderer ROM/RAM cost is claimed.

Reproduce the host-only suite (requires already-built production KJV data):

```sh
python3 betawise/research/bible-reader/formatting/run.py --output /tmp/bible-formatting
```

The optional wider comparison can be regenerated with combine.py using the
sidecars/layouts outputs. small_huffman.py --version nkjv --layouts PATH measures
the richer source. The committed summary records exact source/resource hashes
and paths to retained raw experiment artifacts. No production format or index
was changed by these trials.

## NKJV formatting method comparison (2026-11-24)

The same methods were rerun on NKJV, now preserving paragraph/poetry layout,
italics, small caps and bold. [Results](formatting/nkjv-results.json) include
source/resource hashes and artifact paths. These are resource bytes only, not
renderer implementation or additional font assets. Red-letter metadata and
footnotes are excluded from this comparison.

| Method | Styles and layout, KiB | Including headings, KiB |
|---|---:|---:|
| Rice event sidecars, per-book small-caps defaults | 77.9 | 127.1 |
| Inline style/layout controls, best tested defaults | 73.1 | 123.6 |
| Run sidecars plus compact Huffman, no word defaults | 65.2 | 115.6 |
| Run/Huffman sidecars plus small-caps word defaults | 58.2 | 108.5 |
| Run/Huffman sidecars plus italic/small-caps defaults | **56.8** | **107.2** |

The smallest measured resource is 58,194 bytes without headings or 109,775
bytes with headings. Each column is a complete package, including model tables,
chapter indexes, framing and padding. Shared-index widths change at 64 KiB, so
the incremental heading cost differs slightly among rows. Inline figures include
any growth of the rebuilt Full search index.

NKJV has 22,847 italic atoms, 6,950 small-caps atoms, 54 bold atoms and 9,683
paragraph starts. Unlike KJV, a paragraph-per-verse default is wrong: the best
layout sidecar uses no implicit break at each verse, plus 33,352 sparse layout
exceptions. It preserves internal line breaks, single/double indentation,
centering and alignment as well as paragraph starts. Its complete standalone
resource is 32,214 bytes. A compact canonical byte-Huffman model beat the large
fast-lookup model, Rice and gamma. Per-book/chapter paragraph defaults were also
tested; the translation-wide default still won for the sidecar.

Headings account for much of the difference from KJV: NKJV has 2,992 extra
headings versus 138. Its independently seekable front/Huffman heading pool,
locations and levels use 51,713 bytes. The 1,189 generated chapter titles remain
implicit. The same research ASCII mapping retains Latin acrostic names while
removing their redundant Hebrew glyph prefix; it does not modify the verse text.

For styling, a 138-byte per-book vocabulary table covers eleven words: eight
italic profiles and three small-caps profiles. Defaults are selected by a
minimum-gain threshold; global defaults and book thresholds 4, 12 and 32 were
tested. Book/32 plus run/Huffman residuals was smallest (26,114 bytes for the
standalone style file). This saves 1,362 bytes over the small-caps-only predictor.
The source is reconstructed exactly by XORing the decoded default with decoded
residual masks.

Five inline alternatives cover styles alone with separate layout, both
translation-wide and per-book inline layout defaults, and extended italic word
defaults. All 1,830 production C search cases matched the original plain-source
oracle. C decoding additionally verified 3,844,115 atom styles and all inline
layout flags. Every original verse byte is recovered after stripping controls.
Sidecar alternatives instead leave the original Bible/index/pruning/verse
resources byte-identical. Production rendering is unchanged.

Reproduce against already-built NKJV resources:

```sh
python3 betawise/research/bible-reader/formatting/run_nkjv.py --output /tmp/nkjv-formatting
```

### Formatting CPU and literal inline headings

The [formatting speed trials](formatting/speed/README.md) compare actual portable
C metadata decoders on the Neo CPU in MAME. Sidecar style/layout overhead is
modest; front-compressed heading dictionary lookups dominate the expensive
cases. Putting actual heading text in the main grammar/Huffman stream was both
smaller and faster than a heading pool in the four tested NKJV chapters. The
research copy retains canonical verse search and passed all 366 search cases.
See the linked results for scope, sizes, timings and reproduction commands.
Production rendering remains unchanged.
