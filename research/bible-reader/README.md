# ROM-resident KJV reader: representation experiment

Production code and current controls are documented in the [BibleWise manual](../../applets/BibleWise/README.md). This file retains chronological research; measurements refer to their named historical baselines. Generated reports are kept under ignored `build/` directories.

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

The following experiments are historical comparisons against explicitly named
baselines. Their byte counts and timings are not current release measurements.
Generated JSON and old audit snapshots live under ignored `build/` directories;
the source helpers and concise conclusions are retained here.

### Small-cap italics without persistent alias tables (2026-11-26)

Research-only variants are in `smallcaps-italics/rewrite.h`; the normal applet
still uses the alias tables. The generated `smallcaps-italics/build/results.json` records release
sizes, individual MAME timings, full-corpus provenance counts and artifact paths.
All tests use disposable state and source/font/bitmap/cursor assertions locally.

The current KJV has no italic small-cap letters. NKJV has only 21: the lowercase
`ord` of italic `Lord` in Exodus 33:9, Numbers 23:15, 1 Samuel 3:17 and 16:7,
1 Kings 13:22, and 2 Chronicles 3:1 and 18:21. Ordinary body italics remain
implemented by selecting the normal face for the editor's italic slot.

The alias baseline uses 3,740 A5 bytes and 37,491 application ROM bytes with the
current SDK. Bible/index/formatting resources are identical between variants and
are excluded from application ROM. These are fresh controlled builds, not a
comparison with earlier SDK builds in this directory.

| NKJV research method | A5 bytes | A5 saved | ROM added | Off / on, mean ms |
| --- | ---: | ---: | ---: | ---: |
| Existing width/offset aliases | 3,740 | 0 | 0 | 256 / 245 |
| Replay formatting metadata | 2,988 | 752 | 894 | 334 / 643 |
| ROM small-cap ordinal ranges | 2,976 | 764 | 618 | about 335 / 335 |
| RAM native-file offset list | 2,980 | 760 | 354 | 248 / 248 |
| In-file region provenance bit | 2,976 | 764 | 516 | 335 / 335 |

Timings include busy display, font setup, native reflow, viewport/caret/selection
restoration and redraw, but exclude test-only offset-reconstruction probes.
Samples cover all seven affected chapters, Century Schoolbook Tiny, Neo 3.21.
The three-offset list's own rewriting pass takes 2.6 ms; replay takes 88 ms off
and 398 ms on; the two file-scan methods take about 90 ms each way. Exact final
numbers, ranges and Times checks are in the JSON. The alias off toggle also
pays about 11 ms to construct its alias tables. KJV's empty provenance set allows
the metadata and ROM-index variants to compile out rewriting entirely: 2,956 A5
bytes (784 saved), and 262 fewer ROM bytes. Psalm 119:176 toggles take 592 ms
versus alias 603 ms off / 592 ms on.

The metadata prototype decodes sidecars and text to recover original small-cap
styles, walking matching private letters in the existing file. It rewrites glyph
codes only, without recreating the chapter or changing length. A generated
14-byte affected-chapter list skips replay/scanning elsewhere. Scratch is on
stack (364-byte rewrite frame plus the formatter's 1,596-byte frame and callees).
The ROM alternative stores seven six-byte `(chapter, ordinal, count)` records,
42 ROM bytes. Ordinals count private small-cap letters, so the index is independent
of font-dependent layout padding. The RAM alternative records three 16-bit file
offsets plus a 16-bit count during initial decode: eight persistent bytes. It
adjusts offsets for centered/right-aligned padding and maps the native gap when
patching. All variants also support loading with italics already disabled.

The marker prototype piggybacks bit `0x10` into existing `B1/B2` private-face
records, preserving the original italic provenance while changing glyph codes.
It adds **zero file bytes**, and the tests verify provenance survives reflow,
headings/verse-number hiding and copying in both tested fonts. This bit is undocumented;
these tests establish behavior on Neo 3.21 only. It is not a new fixed ROM call or
RAM address. Separate begin/end `B1/B2` or opaque `B3` records would cost six bytes
per run (42 bytes over NKJV). A hidden one-byte literal begin and end marker,
each enclosed in its own hidden region, would cost fourteen bytes per run (98
bytes); it would additionally need escaping and separation from hidden headings
and verse markers. These last marker encodings are host cost estimates, not
MAME implementations. Opaque records require extending our native text filters.

Recommendation: the tiny RAM offset list for NKJV, with a generated no-italic-
small-cap specialization for KJV. It retains only useful chapter context, avoids
undocumented token semantics, and is faster and smaller in ROM than replay. If
every A5 byte matters, the ROM ordinal index removes the eight-byte list (four net A5 bytes
after linker effects) for roughly 90 ms per affected toggle, without replaying the chapter. No production
choice has been changed by this experiment.

Reproduce from the workspace root (substitute `alias`, `metadata`, `rom-index`,
`offsets`, or `marker`; choose fresh output directories):

```sh
python3 betawise/tests/mame/asneo/check-biblewise.py --version NKJV --case italic-rewrite --vendor-font schoolbook --italics-prototype offsets --output /tmp/smallcaps-offsets
python3 betawise/tests/mame/asneo/check-biblewise.py --version NKJV --case italic-interactions --vendor-font schoolbook --italics-prototype offsets --output /tmp/smallcaps-offsets-interactions
make -C betawise/applets/BibleWise VERSION=NKJV ITALICS_PROTOTYPE=offsets
```

`build_ranges.py` generates bounds and ordinal indexes from the production C
formatting iterator over the entire source. `summarize.py` reads release ELFs
and completed exact-verifier results; `--evidence /tmp/bible-italic-prototype
--output ...` regenerates the report. Raw LCD records, expected/actual bitmaps,
font tables, chapter files, cursor samples, timings, manifests and logs remain
under the evidence directory. No user's saved flash or RAM was used.

### Shared provenance pass versus chapter rebuild (2026-11-26 follow-up)

This supersedes the preceding offset-list recommendation. Both new paths remain
opt-in research builds; the production default is still `ITALICS_PROTOTYPE=alias`.
Machine-readable measurements, release hashes, timings and passed suite paths:
`smallcaps-italics/build/followup-results.json` (generated, not committed).

The `integrated` variant permanently sets region bit `0x10` at decode for original
italic text, including ordinary italic body text and italic small-cap letters.
Disabling italics never clears this provenance. The existing heading/verse-number
visibility scanner accepts a third operation: for a source-italic private letter
(flags masked by `0x1C` equal `0x1C`), exchange Regular/Italic glyphs with XOR
`0x2B`. Each preference toggle exchanges them exactly once. No standalone rewrite
scanner, chapter-presence index, offset list, or additional persistent storage is
needed. Ordinary italics still use the normal font in the editor's italic slot.
The provenance bit is verified independently against every source character,
not only the small-cap letters, including while italics are disabled. In-file
length and records are retained through toggles. Bit `0x10` remains undocumented;
MAME acceptance here is scoped to Neo 3.21, not a claim about every ROM release.

The `rebuild` variant erases and regenerates the existing chapter temporary file
using the normal decoder and editor setup. It needs no additional file. Absolute
byte offsets are insufficient for restoring positions: italic right-aligned
`Selah` can have different generated padding. Three stack-only `(verse, word,
byte delta)` anchors restore the viewport, caret and selection anchor using our
existing word scanners. They add no persistent A5 data. The research helper is
`smallcaps-italics/rebuild-view.h`.

Fresh release builds against the same SDK archive:

| Method | A5 bytes | A5 saved | App ROM bytes | ROM change |
| --- | ---: | ---: | ---: | ---: |
| Alias baseline | 3,384 | 0 | 37,753 | 0 |
| Chapter rebuild with source anchors | 2,608 | 776 | 37,861 | +108 |
| Integrated permanent provenance | 2,600 | 784 | 37,625 | -128 |

These figures are identical for KJV and NKJV application code; the six Bible,
index and formatting resources are excluded and remain identical across methods.
Use this fresh baseline rather than mixing in the older SDK/overlay sizes above.
A5 savings include GOT effects: the 768-byte aliases disappear; shared/removed
address-table entries account for the remaining difference. Compiler inlining
and code sharing also affect the ROM totals. The integrated visibility routine
grows 90 code bytes, the chapter event writer grows 100, its toggle glue grows
14, alias construction shrinks 180, other shared-helper code shrinks a net 136,
and the ROM's initialized GOT image shrinks 16: net -128 bytes. These counts are
whole-release symbol comparisons, not standalone microbenchmark estimates.

NKJV, Century Schoolbook Tiny, selected verse at the given location, milliseconds
(off / on). End-to-end guest CPU time includes source-anchor capture, busy display,
font changes, native layout, restoring the view/selection and final redraw; it
excludes the test-only verse-table reconstruction probes.

| Chapter / selected verse | Aliases | Rebuild | Integrated |
| --- | ---: | ---: | ---: |
| Genesis 1:2 | 255 / 244 | 1,048 / 1,048 | 282 / 282 |
| Exodus 33:9 | 246 / 235 | 978 / 978 | 268 / 268 |
| Psalm 119:176 | 639 / 628 | 2,626 / 2,626 | 768 / 768 |
| Psalm 3:8, aligned italic Selah | 156 / 145 | 586 / 586 | 156 / 156 |

KJV rebuilding costs 1,010 ms at Genesis 1:2, 953 ms at Exodus 33:9, and
2,506 ms at Psalm 119:176. Its integrated path costs 274, 255 and 717 ms.
There is deliberately no KJV/affected-chapter scan-skipping index in this new
integrated variant. Full line-scrolled timings are included in the JSON as well.

202 final deterministic checkpoints passed: KJV and NKJV across all three
methods, Genesis 1, Exodus 33, Psalms 119 and 3, selected whole verses and an
eight-line cursor-scrolled view; Times additionally covers forward phrase
selection, copied text, and combinations of italic/headings/verse-number toggles.
The main reverse selections come from verse lookups. Whole-source styles, exact
provider glyphs, caret and selection geometry, all provenance flags and full
264x65 LCD pixels are checked independently. Captures contain three identical
cursor-hidden LCD RAM samples via the firmware API, and original cursor modes
are restored. Disposable flash/RAM only.

The strict tests exposed an existing native reflow case in both the aliases and
integrated variant: turning off italic can wrap right-aligned Selah onto another
line and push an originally bottom-row caret below the viewport. Retain the
current source viewport unless that caret would become invisible, then move only
the minimum number of lines required to show it. The source caret and selection
must never change. The verifier independently renders the new layout at the
previous viewport and asserts that precise minimum adjustment. On re-enabling,
it retains the then-current viewport; it does not jump back to an earlier view.
Other main comparisons assert identical viewport text and caret source position.
Raw failed strict captures and diagnostic runs remain in the evidence directory;
expected pixels were never learned from a capture. Rebuilding's source anchors
also account for alignment padding changes rather than retaining stale offsets.

Reproduce from the workspace root, using fresh output paths:

```sh
python3 betawise/tests/mame/asneo/check-biblewise.py --version NKJV --case italic-comparison --vendor-font schoolbook --italics-prototype integrated --output /tmp/integrated-comparison
python3 betawise/tests/mame/asneo/check-biblewise.py --version NKJV --case italic-comparison --vendor-font schoolbook --italics-prototype rebuild --output /tmp/rebuild-comparison
python3 betawise/tests/mame/asneo/check-biblewise.py --version NKJV --case italic-interactions --vendor-font times --italics-prototype rebuild --output /tmp/rebuild-selections
make -C betawise/applets/BibleWise VERSION=NKJV ITALICS_PROTOTYPE=integrated
```

For the archived evidence layout, `compare_followup.py --evidence
/tmp/bible-italic-followup --output ...` regenerates the final JSON and checks
passed suite logs, deterministic result reports, and frozen source/SDK hashes.
Recommendation: the integrated source-provenance flag. It has the lowest A5 and
ROM costs of these three builds, retains the native chapter file, and avoids the
chapter rebuild delay without a second scanning implementation.

### Integrated provenance promoted to production

BibleWise now always uses the shared region pass and permanent source-italic
`0x10` flag. There is no production codec switch, alias-table allocation, alternate
rewrite scanner, ordinal index or rebuild branch. `ITALICS_PROTOTYPE` is rejected
by the production Makefile. The original complete multi-variant applet and
Makefile, plus the comparison harness/verifier, are retained in
`smallcaps-italics/archive/`. The alternative helper implementations remain beside
that directory, and the measurements are under `smallcaps-italics/build/`.

To regenerate a historical variant, restore the four archived files to their
original locations in a **disposable workspace copy**: `BibleWise.c` and `Makefile`
under `applets/BibleWise/`, and `check-biblewise.py` and `bible_rich.py` under
`tests/mame/asneo/`. The archived Makefile selects the seven implementations via
`ITALICS_PROTOTYPE`. Do not restore them over production files in the active
workspace. Remaining SDK, applet helpers, source data, emulator and firmware are
those of the workspace; archived manifests identify the measured builds.

Current acceptance cases are `italic-retention`, `italic-source-flags`, and
`italic-interactions` in the production `check-biblewise.py`; no variant argument
is needed. The interactive launcher defaults to a windowed 1056x260 (4x) screen
with `-nofilter`; `--prepare-only --version NKJV` prints the plain MAME command
without launching it or sending keys.

### GOT and remaining A5 audit

`got-audit/audit.py` reads the final release ELF's initialized GOT words and maps
all retained `R_68K_GOT*O` relocations back to the slot, source symbol, and owning
function. Its full per-entry inventory and grouped report are generated under
`got-audit/build/`. `got-audit/build_variants.py` produces isolated **host-only**
code-generation probes; production sources, SDK and release artifacts are not
modified by these builds.

The current 2,600 bytes split into a 1,192-byte GOT and 1,408 other bytes. The GOT
contains 298 four-byte words: 105 applet function addresses (420 B), 56 syscall
wrapper addresses (224 B), 33 SDK/compiler function addresses (132 B), 39 RAM
addresses (156 B), 42 literal-string addresses (168 B), 20 ROM-data addresses
(80 B), and three unused ELF-reserved entries (12 B). It is predominantly call
addressing, not Bible data or large application workspaces. The three reserved
words are the initial `.got.plt` area; the remaining 295 slots all have retained
references. Two additional address pairs duplicate an address: the adjacent
BibleDataEnd/BibleSearchData resource boundary, and two compiler-folded functions.
At most eight bytes are available from coalescing those pairs; this does not
account for most of the overhead.

`-msep-data` currently compiles ordinary calls, including static local functions,
as a GOT load followed by an indirect call. PIC startup relocates those words for
the applet's actual ROM/RAM bases. Internal PC-relative calls can avoid the word
because code and callee move together. Conversely, far Bible resource addresses
cannot generally use a 68000's short PC-relative data displacement. We should not
replace this with fixed absolute addresses.

The remaining 1,408 bytes are:

| Use | Bytes |
| --- | ---: |
| Three 177-entry chapter-position tables | 1,062 |
| One native editor descriptor | 94 |
| Editable Find text and retained query, 33 B each | 66 |
| Font descriptors/pointers and stable font ID | 38 |
| SDK display state and console parser | 72 |
| SDK font picker/cache state | 21 |
| Settings, retained match, flags and timers | 52 |
| Padding | 3 |

Six of those bytes are initialized settings; the remaining 1,402 are zeroed BSS.
The tables hold heading-inclusive search starts, verse-number starts, and verse
ends; these boundaries differ when headings and native region records intervene.
They are retained chapter context, not decompressor or active-search scratch.
`g_input` holds the current/draft form and `g_last_find` the accepted query used by
Find Next/Previous; merging them directly changes cancellation/repeat behavior.
The console's 52-byte parser is currently pulled in solely by the unconditional
focus `_ConsoleReset` in the SDK entry shim. BibleWise does not otherwise use
console parsing. Display state is another 20 bytes and is used by drawing/cursor
wrappers. The unused console is a separate possible SDK opt-out, not proof that
all 72 display/console bytes can be removed.

Measured host-link probes (same sources/resources/SDK archive):

| Probe | GOT | Total A5 | A5 saved | ROM saved |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 1,192 | 2,600 | 0 | 0 |
| Linker --relax | 1,192 | 2,600 | 0 | 0 |
| Compile applet C files together | 1,180 | 2,588 | 12 | 182 |
| Group zero-initialized reader fields into one state object | 1,072 | 2,482 | 118 | 150 |
| Adjacent direct calls made PC-relative | 880 | 2,288 | 312 | 960 |
| State grouping plus relative calls | 752 | 2,162 | 438 | 1,134 |
| No-op unused console reset, as a size probe only | 1,188 | 2,544 | 56 | 46 |

The state prototype removes 30 independent RAM-address GOT slots; the aggregate
layout adds two bytes, for 118 net A5 bytes saved. Its temporary generated field
macros are a measurement technique, not the proposed production coding style.
The relative-call probe rewrites only an immediately adjacent `move.l
symbol@GOT(a5),a0/a1; jsr(a0/a1)` into `bsr.w symbol`. There are 322 converted call
sites; many other cached function/callback references are deliberately untouched.
The linker checks all PC16 reaches and the normal OS3K fixup process is rerun.
The combined probe converts 330 sites after different register allocation. This
is **not** a production-ready general assembly optimizer: additional ABI, code
placement, tail-call/register-use and relocation regression coverage plus MAME
acceptance are needed before adopting it. No fixed ROM calls are introduced.
`-mpcrel` combined with `-msep-data` is rejected by this compiler for the 68000;
`-fno-plt`/`-fno-semantic-interposition` did not fix its indirect-call generation
in the small compiler probe. No untested 68020 instructions were used.

Next candidates are a properly tested relative-call code-generation improvement,
a normal named ReaderState object, and making the unused console reset optional
in the SDK. A named string pool could also reduce some literal-address slots,
but has not been measured here. Changing chapter table policy is a different
space/lookup-speed trade-off and was not applied. The production 2,600-byte
allocation and its accepted MAME behavior remain unchanged by this audit.

### One-table and every-16-verse boundary prototypes

`verse-boundaries/prepare.py` generates isolated applet copies under its ignored
`build/` directory; production code is unchanged. `boundaries.h` implements both
variants. The original `offset-rebuild-probe.h` every-16 experiment was a test-only
reconstruction comparison while all three production tables remained allocated.
It was not an active sparse index in the reader.

The new `one` variant retains a single heading-inclusive search-start offset for
every verse, indexed from zero: 176 x 2 = 352 bytes maximum. From that entry it
scans the existing native chapter file for the verse marker and body end. A
six-byte boundary triple plus its two-byte verse ID is cached. Headings are
recognized through their permanent visibility records, and native font/style
records, cached wrap bytes, alignment padding, and the file gap are handled.

The `sparse` variant retains offsets only for verses 1, 17, 33, ... 161: eleven
two-byte checkpoints (22 bytes). It scans forward from the nearest checkpoint,
using the explicit verse number in native marker records. Its cache holds the
same triple and ID, plus the following search-start limit: ten bytes. That upper
limit permits a cache hit at the verse end and in following separators without
misclassifying the next heading. Both caches are invalidated on chapter decoding;
visibility/style toggles preserve byte positions and do not require rebuilding
them. The scanned byte buffer and parser state are stack-only; the compiler's
scanner frame is 364 / 368 bytes for one/sparse, plus callees.

Matched NKJV release images in the measured shared-SDK snapshot:

| Method | Index/cache payload | Total A5 | A5 saved | ROM added |
| --- | ---: | ---: | ---: | ---: |
| Three full tables | 1,062 B | 2,624 B | 0 | 0 |
| One full index + cached boundaries | 360 B | 1,930 B | 694 B | 768 B |
| Every-16 index + cached boundaries | 32 B | 1,610 B | 1,014 B | 1,082 B |

GOT sizes are 1,212 / 1,220 / 1,228 bytes respectively. Thus net savings are
slightly less than raw table savings. This snapshot includes font-picker/SDK work
that was in progress during testing; compare these matched figures, not a prior
2,600-byte release. The measured release image hashes, header sizes and CRT GOT
loop bounds are retained in `verse-boundaries/build/results.json`. A later attempt
to relink an older UI snapshot against a newer live SDK failed after an unrelated
font-preview API was removed. That failed diagnostic did not change the captured
release images; their original bytes are the size evidence. Regenerate fresh
isolated copies with `prepare.py` to match the current SDK, rather than relinking
a historical copy against changed headers.

MAME cold boundary-reconstruction time (not whole key-to-screen latency):

| Target | One full index | Every-16 index |
| --- | ---: | ---: |
| Genesis 1:16 | 7.17 ms | 96.95 ms |
| Genesis 1:31 | 6.46 ms | 109.61 ms |
| Psalm 119:16 | 4.88 ms | 65.04 ms |
| Psalm 119:17, checkpoint | 5.31 ms | 5.32 ms |
| Psalm 119:160 | 6.25 ms | 71.21 ms |
| Psalm 119:176 | 5.39 ms | 64.11 ms |

Ranges across the tested cold targets are 4.3–7.7 ms and 4.3–110 ms. Repeated
lookups and copies of the cached verse perform no boundary scan; this is not a
claim that copying text or native layout performs no reads. Native cursor/page
scrolling does not request these boundaries in production. The actual callers
are verse lookup/selection, locating search words/origins, copying/citing, and
obtaining a verse for reading-font operations.

The canonical test observer also locates a verse to assert the cursor's identity.
For fair measurement its calls are marked with phases 712/713, and its temporary
cache changes are saved/restored on stack. Phases 710/711 bracket scanner work;
`summarize.py` excludes observer scans from real-operation latency. No expectations are derived
from captured pixels. The normal source/style, provider-glyph, cursor/selection,
three identical cursor-hidden LCD RAM samples and exact 264x65 bitmap verifiers
all remain active. Final acceptance is 152 checkpoints: three NKJV benchmark
variants (22 each), KJV retained-view/selection suites for both prototypes (29
each), and NKJV search/copy/visibility interaction suites for both (14 each).
Earlier diagnostic runs and their raw artifacts also remain under `build/`.
Neither current KJV nor NKJV source has an empty verse; handling other translations
or differently normalized native files would need further coverage before release.

Reproduce from the workspace root, using fresh output directories:

```sh
python3 betawise/research/bible-reader/verse-boundaries/run.py --variant one --boundary-bench --version NKJV --case italic-retention --vendor-font schoolbook --output /tmp/verse-one
python3 betawise/research/bible-reader/verse-boundaries/run.py --variant sparse --boundary-bench --version NKJV --case italic-retention --vendor-font schoolbook --output /tmp/verse-sparse
python3 betawise/research/bible-reader/verse-boundaries/run.py --variant sparse --version KJV --case italic-retention --vendor-font schoolbook --output /tmp/verse-sparse-kjv
python3 betawise/research/bible-reader/verse-boundaries/run.py --variant one --version NKJV --case italic-interactions --vendor-font schoolbook --output /tmp/verse-one-interactions
```

The runner patches only its in-memory copy of the canonical acceptance script to
select an isolated applet; it does not modify production sources or the canonical
harness. Shared SDK builds are serialized by a research lock to avoid competing
version-header temporary files. The historical `memory-rebuild` diagnostic is not
supported in these reduced-table variants because it expects all three originals.

The one-table variant is a strong low-latency reduction. Every-16 checkpoints
save another 320 A5 bytes for 314 additional ROM bytes, at the cost of scanning up
to a block of verses on a cold request. Given the reader's infrequent boundary
queries and otherwise native scrolling, either remains viable; neither has been
promoted to production by this experiment.

### GCC-emitted PC-relative call investigation

`verse-boundaries/compiler_flags.py` records assembly and diagnostics from the
installed Debian m68k GCC 12.2 compiler. Normal separate-data mode, `-fpic`,
`-fno-plt`, hidden visibility, and `-fno-semantic-interposition` all retain the
same GOT-load/indirect-call pairs in the controlled probe. Combining separate
data with `-mpcrel` is rejected for the 68000. Without separate-data mode,
`-mpcrel` emits PC-relative data loads and PC-relative function-address LEAs,
followed by indirect JSRs; it is not a drop-in for independently placed A5 RAM.
[GCC's m68k option documentation](https://gcc.gnu.org/onlinedocs/gcc/M680x0-Options.html)
describes the addressing modes and restrictions.

A compiler-side solution is feasible: the Retro68 fork documents a dedicated
16-bit BSR call mode in its
[GCC patch notes](https://git.applefritter.com/Macintosh-Tools/Retro68/src/branch/master/GCC-PATCHES.md),
section 9. That is a lead for adapting the m68k backend while keeping OS3K's data
ABI, not evidence that the whole Macintosh toolchain can replace our ELF toolchain.
No patched compiler was built, installed, or used here. Stock-compiler boundary
measurements above use no assembly rewriting. Adapting and validating the BSR
backend change would be a separate toolchain task from the reader's table policy.

### No-table and chapter-file-resident index prototypes

The additional `none` and `file` variants live in the same isolated research
runner. Production remains unchanged. The generated report is
`verse-boundaries/build/file-experiment-results.json`; `summarize_file.py` verifies
all passed suite reports/logs and preserves per-operation CPU timings, file sizes,
SDK hash and release hashes. These are fresh matched builds against the current
SDK, whose baseline is again 2,600 A5 bytes, not the earlier in-progress font-picker
snapshot's 2,624 bytes.

`none` retains no offset/checkpoint array. It retains only a ten-byte current-verse
cache (search/start/end, ID and following boundary), and on every cold miss scans
from chapter start. This measures that straightforward strategy; a future
forward-walk hint from the cached verse could improve sequential misses but was
not implemented or measured. `file` retains the same ten-byte cache and stores
all three 16-bit offsets per verse in the existing chapter file, not another
workspace file. Six-byte entries are packed 32 per B8 native opaque record, with
four bytes of framing per record. The records are appended after chapter text,
consume no display cells or lines, and are omitted by plain-text conversion.

The file's index costs `6 * verses + 4 * ceil(verses / 32)` bytes: Genesis 1 uses
190 bytes; Exodus 33 uses 142; John 3 uses 224; Psalm 119 uses 1,080. Direct verse
lookup reads the selected six-byte entry and, except for the final verse, the
next search offset. Locating a verse from an arbitrary caret uses binary search.
All file accesses map around the editor's current gap and preserve FileTell.

To build this index, the original decoder's three tables are fields in its local
ChapterOutput stack object, rather than permanent globals. After body decoding,
records are appended from those fields. This keeps the implementation simple
and preserves its exact heading/alignment logic. The compiler reports a 2,676-byte
DecodeChapterToFile frame instead of 1,388: 1,288 additional transient stack bytes,
including the table and index-record buffer. This is not a reduction in all peak
RAM requirements. No-table decoding retains the 1,388-byte frame, with a separate
364-byte scan frame only when reconstructing boundaries.

| Method | Total A5 | A5 saved | ROM added | Added chapter-file bytes |
| --- | ---: | ---: | ---: | ---: |
| Existing three tables | 2,600 | 0 | 0 | 0 |
| No table, current-verse cache | 1,556 | 1,044 | 738 | 0 |
| File-resident full index, cache | 1,560 | 1,040 | 882 | 10–1,080 |

GOT sizes are 1,192 / 1,200 / 1,204 bytes. Application ROM excluding unchanged
Bible resources is 37,643 / 38,381 / 38,525 bytes. Moving data to the file is not
necessarily reducing total retained RAM. NKJV Genesis 1's captured file grows
from 5,288 to 5,478 bytes including the unchanged 512-byte editor gap. Together
with A5, file-index retained data is 850 bytes smaller than baseline. Psalm 119
file data grows from 18,517 to 19,597 bytes, making A5 plus captured file data
**40 bytes larger** than baseline. File record bookkeeping is unchanged and not
included in these totals; transient stack is also separate. No-table retains
1,044 fewer bytes than baseline in both examples.

MAME cold boundary lookup CPU time (not entire key-to-screen response):

| Target | No table | File-resident index |
| --- | ---: | ---: |
| Genesis 1:16 | 96.15 ms | 1.11 ms |
| Genesis 1:31 | 204.49 ms | 0.73 ms |
| Psalm 119:16 | 64.54 ms | 1.11 ms |
| Psalm 119:160 | 668.93 ms | 1.11 ms |
| Psalm 119:176 | 731.14 ms | 0.73 ms |

Repeated lookups/copies of the cached verse perform no boundary scan/index read.
The file-index binary search from an arbitrary caret costs 2.6–4.5 ms in the
separately marked observer-probe measurements. Observer calls save/restore the
cache and are excluded from real-operation lookup results. Footer writing itself
takes 0.65 ms for Genesis 1 and 4.35 ms for Psalm 119. Full NKJV decode-to-file time
was essentially unchanged: Genesis 1 baseline/no-table/file = 489/487/488 ms;
Psalm 119 = 1,679/1,672/1,674 ms, excluding native layout/display. Stack-field
accesses replace global table accesses, so index writing is not simply additive
to the old decoding time.

B8 records use the audited framing documented in
[`token-records.md`](../syscalls/text/token-records.md). The research native text
filter and region-update walker explicitly skip whole opaque records, so payload
bytes resembling B1/B2/verse digits cannot be interpreted as text or rewritten
by visibility/italics toggles. The independent `file_oracle.py` validates framing,
entry count/order/range, and every indexed verse body against source at every
checkpoint. Its tokenizer omits records according to that framing rule. Trailing
zero-width record positions are mapped to the final source-derived display
coordinate; expected pixels are never learned from captures or masked out.

158 deterministic MAME checkpoints passed: NKJV baseline/no-table/file benchmarks
(22 each), KJV retention suites for no-table/file (29 each), and NKJV interactions
for no-table/file (17 each). Coverage includes checkpoint edges, three-digit
verses, selected lookups, retained caret/view/selection, search, copying, combined
italics/headings/number visibility changes, AlphaWord focus switching, and a cold
lookup/copy after the native gap moves. File-index payload and full verse bodies
remain valid after reflow and focus changes. The standard three identical
cursor-hidden LCD samples, cursor restoration/geometry, exact glyph/pixel and
source-style assertions remain active. Raw samples, fonts, files, logs, validation
reports and diagnostic failures are retained under the evidence directories.

**Focus lifecycle:** the production `MSG_KILLFOCUS` handler calls
SaveReadingPosition, which uses TextEditorSavePosition and FileClose. It does not
call FileDelete or FileEraseCurrent. Focus regain opens the same file with
FILE_OPEN_KEEP_POSITION and restores the editor. File data, including a prototype
index, therefore remains allocated while another applet is active. Different
chapter/font loading erases and repopulates that same file. This experiment did
not change that lifecycle.

Reproduce from the workspace root with fresh output directories:

```sh
python3 betawise/research/bible-reader/verse-boundaries/run.py --variant none --boundary-bench --version NKJV --case italic-retention --vendor-font schoolbook --output /tmp/verse-none
python3 betawise/research/bible-reader/verse-boundaries/run.py --variant file --boundary-bench --version NKJV --case italic-retention --vendor-font schoolbook --output /tmp/verse-file
python3 betawise/research/bible-reader/verse-boundaries/run.py --variant file --version NKJV --case italic-interactions --vendor-font schoolbook --output /tmp/verse-file-interactions
python3 betawise/research/bible-reader/verse-boundaries/run.py --variant file --version KJV --case italic-retention --vendor-font schoolbook --output /tmp/verse-file-kjv
```

No-table offers little additional retained-data saving over a tiny sparse
checkpoint array, but gives up bounded cold-scan time. The file index is attractive
when specifically reducing A5 or wanting direct lookups; it shifts storage to
chapter-file RAM, especially in the longest chapter. Neither prototype was
promoted to production.

### Scan overhead and a cache-free file index

The current-verse cache is optional. The `file-nocache` prototype removes all
three `g_boundary_cache*` globals, reads an index entry into six stack bytes, and
returns requested fields by value. Its generated header is produced by
`cache_free.py`. Measured A5 falls from the cached file-index variant's 1,560 to
**1,534 bytes**, including removed GOT entries/function changes. GOT is 1,188;
release ROM is 1,458,104, or 634 bytes above the matched 1,457,470-byte baseline.
No cached offsets are retained outside the existing chapter file. No-cache verse
jumps currently make two reads for verse 1 and three for other verses, totaling
1.10 / 1.65 ms respectively. Repeated jumps cost the same. Existing copy code
makes thirteen boundary-related requests, including binary searches from caret
positions; their combined lookup overhead is 12.25–15.71 ms in the benchmark.
This is not total copy/display time. Batching needed fields into caller-local
structs could reduce repeated reads without restoring persistent cache state.

“Cold” in prior tables means the requested verse was absent from the single
last-requested-verse cache. It does not mean disk access, processor cache state,
or decompression: lookups read the decoded chapter already in RAM. Boundaries are
needed for verse navigation/selection, positioning a search match, mapping the
caret to a verse for a search origin/citation or font change, and selecting/copying
whole verses. Normal native line/page scrolling does not call these routines in
release builds. The test observer's separate verse identification remains marked
and excluded from timings.

The original no-table scanner was a conservative token parser rather than a
minimal scan: it filled a fifteen-byte lookahead window and called memmove to
shift that window after nearly every character. The emitted m68k object has the
GOT-load/indirect-call memmove in its inner loop. The 731 ms figure should not be
interpreted as raw RAM scanning throughput or an inherent hardware limit.

`fast_boundaries.py` generates a parser with a 256-byte working block, copying at
most fourteen seam bytes only when refilling. Ordinary consecutive bytes are
handled together; full record/verse parsing is attempted at control bytes. It
preserves the same boundary rules, cache and file format—no inserted markers.

| Cold target | Original no-table | Block scanner |
| --- | ---: | ---: |
| Genesis 1:16 | 96.15 ms | 17.84 ms |
| Genesis 1:31 | 204.49 ms | 36.02 ms |
| Psalm 119:16 | 64.54 ms | 12.29 ms |
| Psalm 119:160 | 668.93 ms | 123.96 ms |
| Psalm 119:176 | 731.14 ms | 135.08 ms |

The block scanner retains 1,556 A5 bytes / 1,200 GOT bytes, matching the old
no-table variant. Its release ROM is 1,458,290 bytes, 820 above baseline and 82
above the old scanner. It is still parsing native records and reconstructing
three boundaries, not just searching one byte or copying memory. More focused
marker searches or binary seeking remain possible. The 78 new deterministic
NKJV checkpoints comprise the two 22-check benchmarks and two 17-check
search/copy/formatting/focus interaction suites. Cache-free file-index framing
and every indexed verse body are independently checked at every checkpoint by
file_oracle.py, and all standard exact LCD/source/glyph/cursor checks remain
active. Both experiments remain outside production.

The file index already uses direct entry addressing for a known verse number,
and binary search over sorted search offsets when mapping a caret byte position
to a verse. Binary search in the variable-length text stream is also feasible:
probe a byte midpoint, resynchronize to a complete numbered verse record, compare
its ordinal, and narrow the byte interval. The existing formatted verse-number
records provide an ordinal without adding bytes. Resolving heading-inclusive
search starts and exact ends would still require a small neighboring scan;
termination, record resynchronization and progress need careful validation.
No such binary stream-seek variant was implemented or benchmarked in this audit.

An optional explicit opaque ordinal marker at each heading-inclusive start could
simplify that resynchronization and remove the need to look behind the numbered
body start. A three-byte `B3 ordinal B3` record would cost 3 bytes per verse, up to
528 bytes, and need no full A5 index. Native framing support is already audited,
but the new insertion/scanning/copy conventions and binary-search algorithm
would still require testing. A formatting flag alone identifies a kind of region
but does not by itself supply its ordinal or locate the next boundary. Try the
existing numbered records before adding another format convention.

Reproduce using the existing runner and fresh output directories, selecting
`--variant fast` or `--variant file-nocache`; `--boundary-bench` supplies the same
edge/late/repeated/copy cases, and `--case italic-interactions` adds focus/gap and
visibility changes. `summarize_scan_audit.py` generates
`verse-boundaries/build/scan-audit-results.json` from the retained evidence.


### Binary text seek using existing numbered records (2026-11-26)

This follow-up implements the previously proposed binary stream seek, replacing
rather than supplementing the chapter offset index. Production is unchanged.
The whole-Bible word-search index in ROM is a separate resource and is unchanged
in every variant here.

`binary_boundaries.py` and `binary_seek.h` reuse the block parser, probe byte
midpoints, resynchronize to complete numbered verse records, and compare their
ordinals. A neighboring scan recovers heading-inclusive starts and exact ends;
caret-to-verse lookup starts near the known byte position. No new markers,
footer or index bytes are inserted. The same ten-byte last-verse cache remains.

| Cold boundary lookup | Linear block scan | Binary text seek |
| --- | ---: | ---: |
| Genesis 1:31 | 36.02 ms | 11.08 ms |
| Psalm 119:160 | 123.96 ms | 12.93 ms |
| Psalm 119:176 | 135.08 ms | 10.58 ms |

These are emulated CPU times for boundary resolution, excluding observer work,
not total chapter decode/layout/display latency. Cached repeated lookups do not
scan. Binary uses 1,572 A5 bytes (GOT 1,216) and 1,459,032 release ROM bytes:
16 A5 bytes and 742 ROM bytes above the linear block scanner, saving 1,028 A5
bytes against production at a cost of 1,562 ROM bytes. It adds no chapter-file
storage. This supports removing the full chapter offset tables; the linear
scanner is also viable if less code matters more than late-chapter seek time.

All 76 deterministic checks passed: NKJV numbered-boundary benchmark (22),
search/copy/formatting/focus interactions (17), heading and cross-heading search
(8), and KJV viewport/selection retention (29). Canonical source, exact glyph,
bitmap and cursor checks remain active. These datasets have no empty verses;
other translations still require validation. Evidence and summary are retained
in `verse-boundaries/build/binary-results.json` and the four named suite folders.

Reproduce with `python3 research/bible-reader/verse-boundaries/run.py --variant
binary --boundary-bench` plus the runner's output-directory argument; use
`--case italic-interactions`, `--case heading-search`, and KJV
`--case italic-retention` for the interaction suites. See `run.py --help` for
output and translation options. Do not run simultaneous builds of the same
variant/translation in its shared isolated build directory.

### Focused marker search, with and without BMH (2026-11-26)

The `marker` and `marker-bmh` research variants synthesize the existing full
13–15-byte verse-number record, allowing either visibility mask. `marker` skips
to possible record prefixes and compares the pattern; `marker-bmh` uses a
Boyer–Moore–Horspool skip table, accounting for both allowed mask bytes. Neither
adds markers or file data. Both retain the binary prototype's neighboring-record
reconstruction to recover the heading-inclusive start and exact body end; only
the initial target-marker search is replaced. Caret-position lookups are unchanged.

| Cold lookup | Linear parser | Marker scan | Marker BMH | Binary seek |
| --- | ---: | ---: | ---: | ---: |
| Genesis 1:31 | 36.02 ms | 31.54 ms | 23.87 ms | 11.08 ms |
| Psalm 119:176 | 135.08 ms | 111.66 ms | 73.31 ms | 10.58 ms |

The focused marker-search portion alone takes 106.77 ms without BMH / 68.11 ms
with BMH for Psalm 119:176; the rest is neighboring boundary reconstruction.
These are lookup CPU times excluding test-observer work, not full display delays.

All four release images were rebuilt after the formatting-write batching change:
linear 1,458,246 ROM / 1,556 A5; binary 1,458,988 / 1,572; marker
1,459,232 / 1,572; marker BMH 1,459,282 / 1,572. Relative to the linear parser,
marker adds 986 ROM bytes and BMH adds 1,036. BMH costs only 50 ROM bytes over
plain marker search, but uses an additional transient 256-byte stack table.
All retain the ten-byte last-verse cache and no chapter offset index. These
complete implementations are not smaller than binary: synthesized-pattern and
comparison logic replaces a relatively compact ordinal comparison loop while
retaining neighboring reconstruction.

Each marker variant is tested by the 22-check NKJV boundary benchmark, 17-check
KJV interaction suite, and 8-check NKJV heading-search suite, with canonical
source/glyph/cursor/exact LCD assertions. Run `run.py --variant marker` or
`--variant marker-bmh` with `--boundary-bench --version NKJV --case
italic-retention --output <fresh-directory>`; omit `--boundary-bench` and select
`--case heading-search` or KJV `--case italic-interactions` for those suites.
`summarize_marker.py` records the measurements and release sizes in
`verse-boundaries/build/marker-results.json`. Production is unchanged.

### Specialized single-pass linear reconstruction (2026-11-26)

`linear_boundaries.py` replaces per-character end tracking with a pointer scan
to the next control byte, then trims whitespace backward only at the relevant
run end. Earlier verse bodies need no end-offset calculation for a known-verse
lookup. `lean_boundaries.py` additionally ignores closing formatting records
before the target verse; numbered records reset heading state, while preceding
heading starts remain available. Once at the target it resumes full boundary
handling. Caret-position lookup keeps general parsing because its verse ordinal
is not known beforehand. No backward search or second neighborhood pass is needed.

| Cold target | Old block parser | Trim-at-run-end | Specialized opening-record scan |
| --- | ---: | ---: | ---: |
| Genesis 1:31 | 36.02 ms | 20.97 ms | 17.82 ms |
| Psalm 119:160 | 123.96 ms | 74.15 ms | 63.43 ms |
| Psalm 119:176 | 135.08 ms | 81.02 ms | 69.28 ms |

All timings exclude test-observer work and chapter decoding/layout. The final
`lean` variant uses 1,458,276 release ROM bytes and 1,556 A5 bytes: only 30 more
ROM bytes than the original block parser, with unchanged A5 and stack-buffer
capacity. The intermediate `linear` image is 1,458,236 bytes, ten smaller than
the original. Neither adds file data, markers, a skip table, or a chapter index;
the ten-byte last-verse cache remains. Lean is faster and 1,006 ROM bytes smaller
than the BMH marker prototype; binary remains faster but costs 712 ROM bytes
and 16 A5 bytes more than lean. Production remains unchanged.

The earlier marker-prototype ROM delta was the whole replacement, not the cost
of writing digits and formatting alone. `marker_size.c` isolates the straightforward
pattern construction (184 code bytes) and a comparison-call wrapper (10 bytes)
under the applet's m68000/-msep-data/-Os options. Those are object-code sizes,
not marginal linked ROM; arithmetic and memcmp support/GOT are excluded and
inlining differs. No general itoa is required. Existing arithmetic support may
already be linked for unrelated code.

Reproduce with `run.py --variant linear` / `--variant lean` and the same boundary,
KJV interaction and NKJV heading/interaction cases as the marker experiments.
`summarize_linear.py` collects exact-validated suites, sizes and timings into
`verse-boundaries/build/linear-results.json`.

### Compact binary anchor plus local parsing (2026-11-26)

`compact_binary_seek.h` removes the backward expanding-window scanner. A single
binary routine keeps a numbered record below the requested verse as an anchor,
stopping immediately when it finds the preceding numbered verse. The specialized
linear parser then runs forward to recover the requested heading-inclusive
start, number start, and body end. Caret-position lookup uses the same routine
with byte positions and then obtains one additional preceding verse for heading
context. Full numbered-record validation remains shared with the parser; no
synthesized string or memcmp is used.

| Cold target | Specialized linear | Original binary | Compact binary |
| --- | ---: | ---: | ---: |
| Genesis 1:31 | 17.82 ms | 11.08 ms | 5.83 ms |
| Psalm 119:160 | 63.43 ms | 12.93 ms | 7.93 ms |
| Psalm 119:176 | 69.28 ms | 10.58 ms | 8.70 ms |

Release ROM is 1,458,820 bytes: 168 smaller than original binary and 544 above
the specialized linear scanner. A5 remains 1,572 bytes, 16 above linear. The
same ten-byte last-verse cache remains; no file bytes or index tables are added.
Times measure actual lookup CPU work excluding observer/decode/layout. Generic
binary anchoring also runs for verse 1: that cold lookup is 14.43 ms in Genesis
and 17.08 ms in Psalm 119 versus 1.03/1.15 ms in linear. A verse-1 early return
could remove that work at a small additional code cost; not included here.

The isolated runner accepts `--variant compact-binary`. Validation includes the
22-check NKJV boundary benchmark, 17-check KJV interaction suite, and NKJV
heading (8) and formatting/search/copy/focus interactions (17), using canonical
exact source/glyph/cursor/LCD assertions. `summarize_compact_binary.py` records
sizes and timings in `verse-boundaries/build/compact-binary-results.json`.
Production is unchanged.

### Further binary size audit (2026-11-26)

`tiny_binary_boundaries.py` removes the local parser's redundant FileTell/restore
pair: its only caller already preserves the file position across the entire
binary lookup. It drops the returned record length (the stream position already
advances past it) and initializes only stream bookkeeping. The former zero
initializer emitted a memset of the entire 282-byte stream, including the
256-byte read buffer, at every probe. The buffer is filled by reads before use;
its initial contents are irrelevant. All bookkeeping read before assignment is
still initialized. Production is unchanged.

The release image is 1,458,700 ROM / 1,572 A5: 120 ROM bytes smaller than compact
binary, 288 smaller than original binary, and 424 above specialized linear.
A5 is unchanged. Parser / probe / wrapper stack frames shrink from 376/352/68
bytes to 364/336/52 bytes respectively; these are separate function-frame
measurements, not a summed peak estimate.

| Cold target | Compact binary | Trimmed binary |
| --- | ---: | ---: |
| Genesis 1:31 | 5.83 ms | 4.63 ms |
| Psalm 119:160 | 7.93 ms | 6.06 ms |
| Psalm 119:176 | 8.70 ms | 6.61 ms |

These are boundary lookup CPU times excluding observer/decode/layout. Verse-1
lookups remain generic (11.03 ms Genesis / 13.24 ms Psalm 119); no extra early
return was added. No format, marker, file-storage or persistent-cache changes.

Additional release-only size probes were rejected: 16-bit record fields grew
ROM to 1,458,726; scalar/out-pointer return grew it to 1,458,712; noinline marker
helper grew it to 1,458,760 and A5 to 1,576. Candidate snapshots remain under
`build/tiny-binary-{u16,scalar,noinline}/app/candidate.h`; they were not promoted
or correctness-tested because none improved size.

Use `run.py --variant tiny-binary` for the same 22-check boundary benchmark,
17-check KJV interaction suite and NKJV heading (8) / interaction (17) suites.
`summarize_tiny_binary.py` records all measured release sizes and validated
lookup timings in `verse-boundaries/build/tiny-binary-results.json`.

### Final small binary variant and readable sources (2026-11-26)

The former trimmed-binary implementation was assembled into ignored build
headers by Python transforms. It now has standalone sources:
`verse-boundaries/tiny_binary_seek.h` and `tiny_binary_parser.h`; its generator
only returns the parser path. The unchanged implementation remains available
as `--variant tiny-binary`.

The new `small_binary_seek.h` and `small_binary_parser.h` are the further
size-oriented variant (`--variant small-binary`). The binary loop is
`FindEarlierRecord`, followed by `ReconstructBinaryBoundary` calling the local
parser. The default anchor is now chapter start / verse 1, eliminating repeated
zero-sentinel conditionals; the default position already is zero. Removing the
"found immediately preceding verse" early exit saves another branch but requires
binary narrowing to finish. No validation, framing or cache behaviour is removed.

Release ROM is 1,458,666 bytes and A5 1,572: 34 ROM bytes smaller than trimmed
binary and 390 above specialized linear. Compile-only candidates were position
conditional removal (1,458,692), default-anchor simplification (1,458,684), early
exit removal plus position simplification (1,458,676), and both (1,458,666).
All have the same A5 size. Candidate snapshots and exact release sizes remain
in `build/tiny-binary-{position,default,nostop,default-nostop}` and
`build/further-binary-candidates.json`.

The 34-byte saving trades speed: Genesis 1:31 is 12.63 ms versus 4.63 ms for
trimmed binary; Psalm 119:176 is 9.60 ms versus 6.61 ms. Psalm 119:160 is
12.68 ms versus 6.06 ms. These exclude observer/decode/layout. Thus this is an
optional size-oriented alternative, not an unconditional improvement. No new
file bytes or persistent data are introduced. The additional validation suite
is the same 22-check NKJV boundary benchmark, 17-check KJV interactions and
NKJV heading (8) / interactions (17). `summarize_small_binary.py` retains exact
results under `build/small-binary-results.json`. Production is unchanged.

### Direct file-buffer lookup: linear and binary (2026-11-26)

`verse-boundaries/direct_boundaries.h` contains both direct-memory variants;
`DIRECT_LINEAR` selects linear, otherwise binary anchoring is used. No firmware
or fixed-RAM addresses are hardcoded: each synchronous lookup calls the SDK
`FileBindState(READER_FILE, NULL, NULL, NULL, NULL)` once and borrows its returned
pointer on the stack. Nothing allocates, resizes or mutates file/editor state
while that pointer is borrowed. The loop has no further file syscalls and needs
no FileTell/restore pair. Existing chapter offsets are logical offsets; the
reader maps them around the current editor gap. It scans contiguous spans in
place and uses only a 15-byte stack seam buffer when a record straddles the gap.
The 256-byte buffer, block refill and memmove are gone.

Focus/chapter changes are not the only possible invalidation boundaries:
clipboard growth can allocate file RAM while the applet keeps focus, and native
editor operations can change storage/gap state. Acquiring once per lookup avoids
retaining an untracked pointer across those operations and costs no persistent
A5 variable. The returned pointer is not a stack output binding; passing a
stack address as a retained FileBindState mirror would be incorrect. These
prototypes use null output bindings, as existing native text paths do; they do
not install new persistent mirrors or depend on any old binding surviving.

| Cold lookup | Buffered linear | Direct linear | Buffered fast binary | Direct binary |
| --- | ---: | ---: | ---: | ---: |
| Genesis 1:31 | 17.82 ms | 6.66 ms | 4.63 ms | 1.76 ms |
| Psalm 119:160 | 63.43 ms | 24.40 ms | 6.06 ms | 1.87 ms |
| Psalm 119:176 | 69.28 ms | 26.65 ms | 6.61 ms | 1.91 ms |

These times include pointer acquisition and full boundary reconstruction,
exclude observer/decode/layout, and are measured on the same Neo 3.21 harness.

| Variant | Application ROM excluding unchanged Bible resources | Total A5 |
| --- | ---: | ---: |
| Buffered linear (`lean`) | 38,449 B | 1,556 B |
| Direct linear | 38,391 B | 1,564 B |
| Buffered fast binary (`tiny-binary`) | 38,873 B | 1,572 B |
| Direct binary | 38,729 B | 1,576 B |

Resources remain exactly 1,419,827 bytes. Direct images total 1,458,218 and
1,458,556 ROM bytes. Direct linear saves 58 ROM bytes; direct binary saves 144
versus fast buffered binary (110 versus the slower small binary). The small
A5 increases are GOT/address-table entries; writable application state remains
350 bytes in each image. No chapter index, new file bytes or persistent pointer
state are introduced; the existing ten-byte last-verse cache remains. Direct
binary is 338 ROM / 12 A5 bytes above direct linear.

Compiler frame reports: direct linear lookup wrapper (with parser inlined)
124 bytes versus buffered linear scanner 360; direct binary wrapper/parser 124,
anchor search 80, fill 24 and marker 16. Buffered binary equivalents were
wrapper 52, parser 364, anchor search 336, fill 32 and marker 16. These are
individual generated frames, not total applet stack peaks or simple sums.

Both variants passed 22 NKJV benchmark, 17 KJV interaction, 8 NKJV heading and
17 NKJV interaction checkpoints: 128 total. The canonical verifier asserts
source text, exact font/LCD pixels, selection/cursor geometry, formatting,
clipboard and focus restoration using disposable RAM/flash. In addition,
`check_direct_gap.py` compiles the actual BoundaryFill/BoundaryMarker source
with host fixtures and passed 1,322,676 assertions for verses 1–176, both
visibility masks, all gap splits, gap lengths 0/256/512, and every byte position.
This verifies records split anywhere by the gap, including their markup/digits.

Reproduce through `run.py --variant direct-linear` / `--variant direct-binary`
with the existing benchmark, heading and interaction arguments. Run
`check_direct_gap.py` and `summarize_direct.py` to preserve the gap results,
release sizes, all suite results and lookup timings in
`verse-boundaries/build/direct-results.json`. Production is unchanged.

### True read-only initialization and end-gap experiment (2026-11-26)

Per-use binding remains the chosen policy. `check_readonly.py` extends the
hash-pinned original-ROM text probe, running Neo 3.21 in disposable state. The
real `TextEditorInit(...TEXT_EDITOR_READ_ONLY...)` succeeds with the required
file flag and leaves a three-byte source file at three stored bytes, with
zero gap. A Down key is consumed with zero status (this is not a rendered
navigation/selection acceptance test). `TextEditorSetFonts`, including an all-null
request, returns TEXT_ERROR_READ_ONLY. `TextEditorSavePosition` is a no-op;
file length remains three. The extended original-ROM probe passed all 75 cases,
including these typed assertions. It observes syscall outcomes and raw RAM,
not model interpretation of screenshots. This confirms a gap-free native mode,
but not a feature-complete BibleWise replacement: our current custom font API
and native position-save path cannot be carried over unchanged.

The `end-gap` variant uses direct binary lookup and retains the editable editor.
After decode it positions a scanner at EOF and invokes public
TextEditorSetScanPosition/TextEditorSavePosition, then performs the normal verse
seek. All 17 canonical exact NKJV formatting/search/copy/focus checks pass.
Every capture retains a 512-byte gap. The first 14 keep it at EOF, including
format toggles, selections, searches and clipboard writes. Focus save moves it
back to the caret: the final three captures have gap 1,837–2,349 inside a
4,998-byte raw chapter file. This proves EOF placement is feasible but not
self-maintaining across the current focus-save path, and frees zero RAM.

`summarize_readonly.py` preserves syscall outcomes, every raw editor/file gap
measurement and validated suite status in `build/readonly-results.json`.
Production is unchanged. Moving to true read-only mode would require a tested
alternative for custom font/layout setup and reading-position persistence;
there is no audited public close-gap operation that preserves all current
editable-editor behaviours.

### EOF-gap speed, read-only fonts/navigation and manual position (2026-11-26)

`eof-linear` / `eof-binary` use the existing direct reader with the gap moved to
EOF once after decode. Every one of the 22 checkpoints in each benchmark has
512 gap bytes at EOF. Psalm 119:176 times are 27.03 / 1.919 ms versus ordinary
direct-reader 26.65 / 1.909 ms; Genesis 1:31 is 6.73 / 1.766 versus 6.66 /
1.761 ms. No useful speed advantage was measured from gap placement alone.

`eof-fast-linear` / `eof-fast-binary` additionally define DIRECT_CONTIGUOUS,
removing mapping and seam-buffer logic. A guard rejects any gap inside chapter
text rather than reading invalid data. Their 22 checkpoints each pass. Psalm
119:176 is 30.46 / 1.717 ms (Genesis 1:31 7.92 / 1.654 ms). The linear generated
code is actually slower; eliminating a source branch does not establish a CPU
speedup. Release ROM/A5: EOF normal 1,458,306/1,564 linear and 1,458,644/1,576
binary; contiguous 1,458,162/1,564 and 1,458,558/1,572. The EOF-positioning setup
largely offsets mapper removal. These variants still retain 512 file bytes and
cannot be used after ordinary native focus saving moves the gap inward.

#### Read-only custom fonts and layout

`readonly-view` initializes directly with READ_ONLY, assigns the documented
Neo descriptor's four font pointers and dimensions, and requests redraw through
the normal message handler. The first-four-check test fails its initial exact
LCD comparison by 1,343 pixels; the chapter has no native cached wrap points
versus 97 in the editable control. The longer viewport case also fails a later
verse positioning operation. Direct pointer assignment alone is not a complete
replacement for the editable font/layout setter.

`readonly-prewrapped` first lets the normal editable API lay out the chapter,
then maps the existing viewport/caret/anchor offsets, removes the gap using
FileSeek/FileDeleteAtPosition, initializes a real READ_ONLY descriptor, and
installs the four borrowed font pointers and saved position/geometry fields.
The two-check custom-font/8-Down test passes the canonical exact source/style/
font/LCD/cursor assertions. This shows another way to supply fonts without a
fixed ROM entry point; it still requires prewrapping. No hardcoded private
ROM or RAM addresses were introduced into the applet prototype.

#### Native key parity

`readonly_navigation.c` and `check_readonly.py` run 14 sequential navigation/
selection actions plus eight independent shortcut trials from the same starting
location, separately in real read-only and editable descriptors. All 44 actions
return consumed=1/status=0. Read-only has zero gap, editable 512 bytes. Eighteen
pairs match caret, selection anchor/state, viewport and pixel cursor geometry,
including arrows, paging, word movement and selection expansion/contraction.
Home, End, Shift+Home and Shift+End differ: Home leaves stale geometry and End
fails to reach the editable endpoint. Reopening the file immediately after
initialization does not fix them. These are raw state/geometry comparisons, not
an LCD oracle or a claim that the complete application is accepted. Original
ROM inspection confirms editable-only layout branches in those paths.

#### Manual reading position

The successful prototype does not use TextEditorSavePosition in read-only mode.
The existing retained editor/A5 already stores viewport/caret/selection, and
FileSeek records the viewport offset in the file's position metadata. On focus
return it updates borrowed font pointers and redraws the retained read-only
state, without reinitializing/reflowing it. Exact 3-check focus and 4-check
selection+focus suites pass. The latter explicitly selects source text `th`
after eight Down keys and verifies its inversion, caret and retained selection
on return. Normal focus policy hides the cursor on return; the first focus
fixture incorrectly expected visible mode and was corrected without changing
geometry or bitmap expectations.

The successful read-only prototype release is 1,459,040 ROM / 1,584 A5, 484 ROM
and 8 A5 above ordinary direct binary. It removes 512 stored gap bytes after
layout, but still needs temporary editable gap space while preparing layout;
immediate physical capacity reclamation and peak RAM were not measured. Font/
format reflow, Home/End and programmatic verse/search positioning remain
integration work. None of these research changes is promoted to production.

`run.py` supports `--first-checks`, `--focus-smoke`, and
`--selection-focus-smoke` for these bounded scenarios. `summarize_viewer_modes.py`
preserves all results under `build/viewer-modes-results.json`: 88 EOF benchmark
checkpoints, nine accepted read-only UI checkpoints, 77 original-ROM syscall
probe cases and 44 key actions, including the four documented differences.

### Read-only speed versus external UI code (2026-11-26)

`profile_modes.py` inserts BIBLEWISE_TEST-only phase pairs around native key,
redraw, position, save, refresh and font-setup calls, plus read-only conversion.
The normal harness records emulated CPU timestamps through its existing memory
tap. Release images contain none of these profiling wrappers. Benchmarks use
Neo 3.21, NKJV and the captured 16-pixel reading font. All reported scenarios
pass the canonical exact source/style/font/cursor/LCD oracle; time spent waiting
for keyboard scheduling and small uninstrumented applet glue is excluded.

The read-only prototype alone initially appears substantially faster for pages
and focus return. The native drawing work barely differs. Its advantage comes
from not invoking editable position/reflow services, not a substantially faster
read-only renderer. Two editable counterfactuals isolate this:

- `editable-retained` retains the existing descriptor on focus return and
  reinstalls its font pointers, rather than refreshing, reflowing and reconstructing
  the same viewport/caret again. Native focus-save/gap behaviour is unchanged.
- `editable-cached` also copies the current viewport scanner's already-valid
  layout state into the caret before paging, clamping an offset inside the gap.
  This avoids TextEditorSetScanPosition's whole-prefix layout work. The native
  page key and redraw remain unchanged. It assumes the retained chapter/font
  metrics have not changed; a production implementation needs a change check
  and the existing refresh/reflow fallback.

| Native-operation CPU work | Existing editable | Read-only | Editable retained/cached |
| --- | ---: | ---: | ---: |
| Eight Down keys, Genesis 1 | 110.73 ms | 109.37 ms | 110.73 ms |
| Expand selection by two characters | 36.94 ms | 36.68 ms | 36.94 ms |
| Page forward, Genesis 1 | 115.93 ms | 42.89 ms | 43.23 ms |
| Page forward, Psalm 119 | 296.71 ms | 36.18 ms | 36.53 ms |
| Focus return, Genesis 1 | 364.97 ms | 17.96 ms | 18.06 ms |
| Focus return, Psalm 119 | 1,264.24 ms | 14.48 ms | 14.58 ms |

Page totals sum nonoverlapping native position/key/redraw calls. Focus-return
work sums refresh, font setup, positioning and redraw, excluding focus-out save.
The editable focus-out save workflow takes 6.19 ms in Genesis / 17.01 ms in
Psalm 119; read-only manual saving takes 0.35 ms. Raw redraw examples are
18.06/17.89 ms (editable/read-only Genesis), 14.58/14.41 ms (Psalm), confirming
similar rendering work. Read-only adds extra initialization after the same
editable layout: conversion + extra redraw costs 125.45 ms in Genesis and
406.59 ms in Psalm 119. This prototype setup is not a fundamental lower bound.

| Release variant | Application ROM excluding Bible resources | ROM delta | A5 |
| --- | ---: | ---: | ---: |
| Existing direct-binary editable | 38,729 B | baseline | 1,576 B |
| Read-only prewrapped prototype | 39,213 B | +484 B | 1,584 B |
| Editable retained focus | 38,617 B | -112 B | 1,568 B |
| Editable cached paging + retained focus | 38,649 B | -80 B | 1,568 B |

The read-only implementation is still not functionally equivalent: Home/End,
arbitrary verse/search positioning, and font/format reflow need more integration.
Thus +484 bytes is its current prototype overhead, not a completed replacement
cost. Relative to cached editable it is 564 ROM / 16 A5 bytes larger. It removes
512 stored gap bytes after preparation but still requires temporary gap space
while wrapping; physical allocation reclaim and peak RAM were not measured.

51 accepted exact checkpoints cover matched navigation, selection expansion/
contraction/collapse, forward/back pages, focus retention with selection, and
Psalm 119 cases. Failed initial combined page fixtures incorrectly asserted
verse/page origins after prior cursor movement; only corrected independent
page suites are summarized. The first retained-editable build inadvertently
inherited EOF-only assumptions and was rejected; the corrected variant uses
the general gap-safe direct reader. No negative or unvalidated result is counted
as a speed improvement.

Reproduce using `run.py --variant direct-binary` / `readonly-prewrapped` with
`--navigation-profile`, `--page-profile`, or `--long-profile`, all with
`--version NKJV --case viewport --output <fresh-directory>`. Compare
`editable-retained` and `editable-cached` using the same scenarios; the latter
also has `--selection-focus-smoke`. `summarize_mode_speed.py` preserves full
phase durations, exact statuses, release sizes and limitations in
`build/mode-speed-results.json`. Production is unchanged. The evidence favours
keeping editable mode and avoiding redundant layout calls, rather than adopting
read-only solely for CPU speed; the 512-byte gap remains a separate RAM tradeoff.

### Production cached-layout adoption and fresh marker comparison (2026-11-26)

Production BibleWise now keeps the native editable editor and reuses the current
viewport scanner when paging. It copies valid viewport/caret flags and line
state, clamps the raw caret around the gap, and anchors pixel coordinates at the
viewport top. A selection is cleared directly because the final full viewport
paint removes its highlight: sending a native Left first can move to a distant
selection anchor and disturb paging. `check_cached_layout.py` verifies exact
screens plus a raw-state/source-renderer invariant: forward/back pages advance
from the pre-page viewport by one screen, including a selection spanning pages.

On focus return the existing editor descriptor retains viewport/caret/selection.
An unchanged reading-font provider reuses that state and reinstalls its borrowed
face pointers before repainting. If resolving the provider produces another font,
the original refresh/SetReadingFonts/RestoreReadingView path remains. The built-in
System face is a fixed ROM pointer (SDK SYS_INT_GET_SYSTEM_FONT_PTR), not the
mutable AlphaWord font preference, so it can safely use the cached path too.
The chapter remains editable with its ordinary gap and native SavePosition.
No read-only changes or experimental lookup format are promoted.

NKJV release before/after: 1,457,426 → 1,457,484 ROM bytes (+58), A5 unchanged
at 2,600. Both KJV and NKJV release builds are refreshed. The earlier -80-byte
counterfactual lacked the production change-detection fallback and the complete
selected-page handling; its figure was not the final implementation size.
The existing batched-format-write change is already included in the before image.

Accepted production suites cover 141 checkpoints across formatting/search/copy
(14), usage (73), all-family font picker (26), KJV paging/toggle retention (9),
long-selection paging (3), built-in font/focus (3), and local UI (13). The local-UI
fixture used obsolete flat-picker keys; only the keys were updated to choose the
same Times/Neo Large/System fonts through the current family picker. Font-ID,
source, pixel, cursor and global-preference assertions remain unchanged. Earlier
incorrect key sequences and page-origin assumptions are retained as rejected
fixtures, not counted as passes.

Historical preparation variants now read `verse-boundaries/reference/BibleWise.c`
(the post-batched-write, pre-cached-layout source), so adopting production UI
changes does not silently invalidate their string transformations or comparison
baseline. `cached-direct-*` variants explicitly use current production source.
Data resources and SDK remain supplied by the workspace; evidence snapshots
retain the built images and raw records used for each measurement.

The earlier memcmp experiments included file seek/read buffering. Fresh direct
memory variants synthesize the previous numbered verse's complete record, find
it by memcmp (optionally BMH), and use the same local parser as direct binary to
recover the requested verse's exact boundaries and heading context. They keep
binary byte-position classification for caret operations. These are research
known-verse comparisons, not completed replacements for all translations with
omitted verses or whole-Bible word-search benchmarks.

| Cold boundary target | Direct memcmp scan | Direct BMH + memcmp | Direct binary |
| --- | ---: | ---: | ---: |
| Genesis 1:31 | 14.58 ms | 7.78 ms | 1.76 ms |
| Psalm 119:160 | 58.83 ms | 25.63 ms | 1.87 ms |
| Psalm 119:176 | 64.24 ms | 27.97 ms | 1.91 ms |

Each 22-check benchmark passes the canonical exact oracle. Cached viewport
layout avoids reflow after lookup but does not alter these search algorithms;
binary remains much faster for late verses. The direct BMH initializer required
explicit two-byte alignment: the initial device build emitted an odd-address
longword store to the byte pattern and faulted. Host tests alone did not expose
that 68000-specific fault; the aligned MAME run passed. `direct_marker_seek.h`
and `direct_marker_boundaries.py` retain the implementation and the explicit
alignment requirement. No such initializer is introduced into production.

`summarize_cached_adoption.py` preserves production before/after image sizes,
source/image hashes, accepted statuses, page-origin assertions and the new
lookup timings in `build/cached-adoption-results.json`. `cached-layout-final-profile`
also validates final cached-layout source in the Psalm 119 paging/focus scenario;
native focus return is one 14.58 ms repaint without refresh/reflow calls.

A final allocation stress scenario (`--relocation-profile`, cached-direct-binary)
creates a 10-KiB clipboard payload, switches to AlphaWord, sends paste, then waits
for stable native input dispatch before switching back. The stress-only harness
records the actual chapter backing address through public FileBindState; there
is no production pointer cache. The chapter moved from 0x1529C to 0x1789C
(+9,728 bytes) and the three exact source/font/cursor/LCD checkpoints still pass,
including retained viewport/caret. This establishes that retaining editor offsets
survives a real backing-buffer move, not just a focus change with fixed storage.
It does not independently assert AlphaWord's pasted text contents or attribute
which allocation moved the chapter. Raw before/after addresses are preserved in
`cached-layout-relocation-final/file-relocation-03.bin` and the adoption summary.
Earlier stress-driver attempts sent keys while AlphaWord was busy or used an
inapplicable cached-file pointer predicate; they timed out and are excluded.
The final driver uses bounded native-input/unchanged-LCD state predicates rather
than a fixed delay. This profiling/stress code exists only in isolated research
TESTING builds, not either production release.

### Production direct binary search and chapter lifecycle (2026-11-26)

Adopted the simple midpoint/backward-marker binary search without an early-exit
or first-verse special case. The forward midpoint variant was 58 ROM bytes larger.
Moving the native editor gap to EOF permits a contiguous borrowed pointer for each
lookup. Supporting an arbitrary gap instead saved only 24 ROM bytes overall, cost
4 more A5 bytes, and retained the marker-seam machinery; the contiguous version
was chosen for simplicity. No index bytes are added to the decoded file.

The three former per-verse arrays are gone. A 10-byte last-verse cache remains.
Release NKJV is **1,458,752 ROM bytes / 1,582 A5 bytes**, versus 1,457,484 / 2,600
before this adoption: **1,018 A5 bytes saved, 1,268 ROM bytes added** including file
delete/recreate and view restoration. Measured uncached lookups in the 73-step
NKJV/Century suite were 5.7–17.8 ms; Psalm 119 verse lookups were 9.5–10.7 ms.

Kill focus closes and deletes the chapter file, releasing its 512-byte gap as
well. The 51-step KJV reader capture records 16,300 allocated bytes before delete
and FileQuerySize=-7 afterward. Reopening reconstructs and restores the selected
Psalm 119 verse and viewport. This is namespace deletion, not a claim of secure
erasure or protection against an active USB export.

The compiler-chat test failure was a stale flat-text reference joining native
verse paragraphs, not a compiler pixel-rendering regression. The default reader
suite now uses the source-aware formatting oracle: source text/styles, exact
font glyphs, native wrap points, independent cursor/selection checks and exact
three-sample LCD comparisons. Its partial-copy fixture now moves past both digits
of verse 16 before selecting the expected F. Find-input navigation and applet-menu
keys do not clear the expected reading selection in the fixture.

Reproduction lives in `verse-boundaries/compare_final_binary.py` and
`check_final_binary.py`. The latter compares every verse number and byte-position
lookup against the full linear parser across captured chapter/formatting variants.
Acceptance artifacts are under ignored `verse-boundaries/build/final-binary-*`.

Final acceptance: KJV reader 51 checkpoints, NKJV/Century usage 73, NKJV italic
interactions 14, and long-selection paging 3; all exact source/glyph/cursor/LCD
checks passed. The direct binary parser also matched the full linear parser for
every byte position and verse in 42 distinct captured chapter/settings variants.
All 138 main-suite captures retained the native gap at EOF.

### Accounting for the 1,268-byte adoption increase

The earlier adoption total combined boundary reconstruction with binary search
and chapter lifecycle changes. Binary search alone adds **280 bytes** over the
same direct-memory linear parser. A controlled series of isolated NKJV release
builds, with the same SDK, compiler flags and resource files, accounts for the
entire change:

| Stage | ROM bytes | Net ROM change | A5 bytes |
|---|---:|---:|---:|
| Cached native editor with three verse tables | 1,457,484 | baseline | 2,600 |
| Replace tables with direct linear boundary reconstruction | 1,458,230 | +746 | 1,564 |
| Use the simple backward binary anchor search | 1,458,510 | +280 | 1,576 |
| Delete/recreate chapter and restore retained view/selection | 1,458,728 | +218 | 1,586 |
| Move gap to EOF; replace gap/seam handling with contiguous reads | 1,458,752 | +24 | 1,582 |
| **Total change** | | **+1,268** | **−1,018** |

The +746 replaces three constant-time array lookups and decoder bookkeeping
with a runtime parser: it recognizes complete superscript records, follows
heading/hidden/style regions, distinguishes heading-inclusive search starts
from number-marker starts, trims verse ends, and classifies arbitrary cursor
positions. Those operations are required by search selection, copying and verse
lookup whether the anchor is found linearly or by binary search. The +280 is the
incremental binary-anchor machinery, not that entire parser.

These are incremental linked-image deltas in the order shown, including any
inlining, alignment and address-table effects; they are not independent function
symbol sizes. The bundled Bible/index/formatting resources do not change.
Reproduce with `python3 research/bible-reader/verse-boundaries/audit_adoption_size.py`
from `betawise/`; its source snapshots and build logs are retained in ignored
`verse-boundaries/build/baseline-size-audit-*`, with the report in
`build/adoption-size-audit.json`.

### Boundary-parser simplification and focus-memory tradeoff

The first simplification merges end-of-file and next-marker completion into one
path, replacing the pending-heading boolean with a heading-offset sentinel. It
saves 46 release ROM bytes. The second removes validation of the fixed six-byte
trailer written by `BufferVerseNumber`; the unique prefix, visibility flag and
digits still identify the record. This is an internal reader for the complete
file produced by BibleWise, not a validator for arbitrary native text. That saves
another 56 bytes. Release NKJV is now **1,458,650 ROM / 1,582 A5 bytes**: **102 ROM
bytes less** than the initially adopted parser, with no A5 increase.

Next-marker position alone cannot define every boundary. A heading before that
marker belongs to the following verse's search span, not the preceding verse's
copied text. Closing formatting records and trailing CR/wrap-space bytes also
have to be distinguished. `NativeTextCharacter` is useful for filtering displayed
characters but discards these structural distinctions; `Formatting.c` operates
on compressed ROM metadata, not offsets in the native chapter file. Neither
replaces the small record walk without additional work or rereading source data.

Using the same staged linked-image audit after simplification gives +652 bytes
for replacing tables with a linear parser, +244 for binary anchoring, +218 for
file deletion/recreation, and +52 net for contiguous EOF-gap handling: **+1,166 ROM
bytes / −1,018 A5 bytes** against the table baseline. These net stage costs vary
with compiler inlining/layout; the actual production reduction is 102 bytes.

The new KJV focus tests measure allocation released and foreground reopen time:

| Chapter | Deleted allocation, including gap | Reopen and restore |
|---|---:|---:|
| Genesis 1 | 5,024 bytes | 898 ms |
| 1 Corinthians 13, with selection | 2,136 bytes | 604 ms |
| Psalm 119, with selection | 16,300 bytes | 2,232 ms |

Deletion releases the whole decoded chapter, including the 512-byte editor gap,
for other applets/files. Closing alone does not do that. The applet's 1,582-byte
A5 context remains retained, so the saved viewport and selection survive. Keeping
delete/recreate remains the chosen policy; its small ROM cost trades a bounded
foreground reload for useful shared RAM while the reader is inactive.

Reproduce isolated size builds with `verse-boundaries/build_simpler_parser.py`,
then `check_simpler_parser.py` for exact old/new marker recognition, verse bounds,
and cursor classification at every captured byte position (42 distinct chapter/
settings combinations). The original parser is frozen in
`verse-boundaries/reference/ChapterPositions.h`. `audit_adoption_size.py` retains
the original adoption accounting; `--current` measures the simplified version.
Fresh deterministic MAME acceptance covers 53 KJV reader checkpoints, 73 NKJV
usage checkpoints and 14 NKJV italic interactions. Captures, lifecycle records,
source/font/cursor assertions and exact LCD comparisons are under ignored
`verse-boundaries/build/simpler-final-*`.

### Audit of remaining native-editor glue (research only)

Initial loading combines compressed text and formatting while decoding; it does
not first write a complete plain chapter and then format that file. The small
style stream is unpacked on the stack, text terminals are decoded, and the event
writer emits native regions, paragraph/poetry layout and verse markers. Native
layout/rendering follows. Visibility/italic toggles edit the retained native
records without decoding the source chapter again.

An isolated build audit identifies more useful simplifications than removing
necessary verse/heading semantics. No production code is changed by this audit:

| Cumulative prototype | NKJV ROM | Incremental saving | A5 |
|---|---:|---:|---:|
| Current accepted reader | 1,458,650 | baseline | 1,582 |
| Direct reads in word-offset and cursor-word scans | 1,458,312 | 338 | 1,582 |
| Rebind/copy each clipboard input block directly | 1,458,150 | 162 | 1,582 |
| Edit visibility/source-italic records through a local binding | 1,457,948 | 202 | 1,578 |
| Shrink generated book-name fields from 24 to 16 bytes | 1,457,426 | 522 | 1,578 |
| **Total potential saving** | | **1,224 ROM** | **4 A5** |

The EOF-gap invariant makes the old buffered seeks/reads and gap-crossing paths
in these functions redundant. Word scans do not yield or allocate. Toggle writes
would remain within a synchronous operation with constant file length; native
layout is still refreshed afterward. Copy must rebind for every input block and
copy that block to the stack **before** growing the clipboard, since clipboard
allocation may relocate the chapter. It must not keep a file pointer across
clipboard writes. The longest canonical book name is 15 characters; the table's
24-byte name field wastes space. Six bytes of changed addressing code offset
part of the 528-byte data reduction in the measured build.

These are compiler/linker size measurements, not MAME acceptance results. They
require focused validation before promotion, especially clipboard relocation
and native layout after direct region updates. `verse-boundaries/audit_native_glue.py`
regenerates isolated sources/builds and `build/native-glue-sizes.json`. Production
resources and code are untouched; the narrowed Navigation.h is a local copy.

Native editor painting, wrapping, scrolling, caret movement and selection are
already reused. `RestoreCaretInViewport` is an exception: it measures advances
through cached lines to preserve the exact view after a display change. Replacing
that helper with native positioning alone needs a separate view/selection
experiment because the native setter also chooses/reflows a viewport. Native
plain-copy cannot by itself recover the original letters from our private
small-cap codes or attach Bible citations/partial-verse ellipses.

Precompressing native style controls could remove some event-writing code, but
it is not an established total-ROM win. The earlier NKJV inline-control trial
used about 16 KiB more formatting/search resources than the selected sidecars;
that exceeds the current 2,748 bytes of Formatting.o code. A literal-native-markup
codec would need a fresh complete data-plus-code comparison before replacing
that design. The direct-access/table-padding reductions above preserve it.

### Adopted direct chapter access and compact navigation records

The four native-glue prototypes are now production. Word-position scans borrow a
fresh chapter pointer for a synchronous read. Visibility/source-italic changes
write constant-length records directly, then let the native editor refresh its
layout. Both rely on the verified EOF-gap invariant and never dispatch messages
or allocate while a file pointer is borrowed. Clipboard copying rebinds for each
256-byte input block and copies that block to stack storage before any clipboard
append can relocate the chapter. No chapter pointer is retained across writes.

The navigation generator sizes its name field from the longest ASCII book name
plus NUL, rather than using 24 bytes unconditionally. Current translations need
16 bytes. The shrink preserves all 66 canonical names; MAME lookup/copy exercises
Song of Solomon, the longest name, without truncation.

| Release | Before ROM | After ROM | Saved ROM | Before A5 | After A5 |
|---|---:|---:|---:|---:|---:|
| KJV | 1,312,650 | 1,311,424 | **1,226** | 1,582 | **1,578** |
| NKJV | 1,458,650 | 1,457,424 | **1,226** | 1,582 | **1,578** |

The four measured reductions save 1,224 ROM bytes; a two-byte copy-start fix
accounts for the remaining two. The last production FileTell reference is gone,
removing its four-byte GOT entry. All five bundled NKJV resource sections have
identical hashes before/after (1,419,827 section bytes). The sizes above are full
release images, not test builds. Relative to the earlier table baseline, the
reader is now 60 ROM bytes smaller and uses 1,022 fewer A5 bytes while retaining
binary lookup and file deletion/recreation.

The allocator test copies all of Psalm 119 through normal selection and Ctrl+C.
Read-only probes record addresses immediately before/after normal clipboard
appends: the chapter moved **25 times in 54 writes**, from 86,684 to 99,484. A
second full copy with headings hidden moved it **25 times in 53 writes**; its
final address returned to its initial address after clipboard truncation and
regrowth. Therefore the test asserts movement during an append, not merely a
different final address. Both copies match original source text/citations exactly.
The test then toggles verse numbers, italics and headings, seeks within the moved
chapter, replaces the clipboard with one verse, and switches away/back.

The initial new fixture incorrectly omitted Psalm 119's acrostic headings from
its expected selected text. Correcting that independently from the upstream
source also exposed an existing copy-start bug: selection starting in a heading
before verse 1 omitted that first heading. Copy now primes the filter from the
heading-inclusive verse search start, while emitting only bytes actually selected.
This includes visible selected headings and skips hidden ones. Failed fixture
runs remain archived and are excluded from the accepted totals.

Fresh deterministic acceptance: KJV reader 53 checkpoints; NKJV/Century usage 73;
NKJV italic interactions 14; NKJV/Times formatted copy 3; KJV clipboard relocation
and longest-name copy 17; NKJV typography 6; and long-selection paging 3:
**169 accepted checkpoints**. Every captured chapter retains its gap at EOF.
Source/style/private-font/cursor/selection and exact three-sample LCD assertions
remain enabled. The clipboard relocation probes exist only in TESTING builds;
no stress key, workspace file or new production state was added.

Reproduce the targeted allocator case with:

```sh
python3 tests/mame/asneo/check-biblewise.py --version KJV --case copy-relocation --vendor-font schoolbook --output research/bible-reader/verse-boundaries/build/copy-relocation-recheck
```

Accepted artifacts are in ignored `verse-boundaries/build/glue-*` directories.
The pre-adoption source is frozen in `verse-boundaries/reference/pre-native-glue.c`;
`audit_native_glue.py` still regenerates the original staged size comparison using
local navigation headers, without modifying production resources.

### Preallocated decode and native-copy comparisons

[Preallocated output research](preallocated-output/README.md) compares the archived
buffered design, a fresh-file buffered control, direct bounded chapter output,
native ClipboardCopy plus in-place cleanup, and the combined design. Combined
NKJV Psalm 119 load drops from 2.349 s to 1.892 s; decode/write alone improves
about 9%. Full-Psalm copy drops from 1.048 s to 0.533 s. Most short-load improvement
comes from avoiding a roughly 303 ms whole-allocation FileEraseCurrent call.
The combined images save 234 ROM and 8 A5 bytes; long-copy physical clipboard
capacity peaks 3,072 bytes higher. These are the historical isolated prototype results (205 deterministic MAME
checkpoints and 38,048 actual-C writer/bound profiles). The combined design is now
the production default. Final production saves 180 ROM bytes and 8 A5 bytes,
including failed-open cleanup and safe byte writes for partial-copy ellipses.
The former implementations remain in `preallocated-output/reference/`.

### In-stream formatting terminals

[Huffman formatting-token research](inline-format-tokens/README.md) led to the
[production HUF04 migration](inline-format-tokens/adoption.md). Generated verse
numbers remain; sidecar encoders, decoders and models are archived in
`inline-format-tokens/sidecar-reference/`. Release ROM falls by 2,036 bytes for
KJV and 17,510 for NKJV; A5 falls by 40 bytes. Decode/write is 15–21% faster in
matched MAME measurements, with 208 accepted checkpoints and full-corpus checks.
