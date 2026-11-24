# KJV Neo layout and codec comparison

All results below use original Neo 3.21 firmware in MAME, disposable flash/RAM,
and deterministic source/font bitmap comparisons. These are emulated CPU/device
timings, not physical battery measurements. Default publishing remains the native
Huffman reader; codec alternatives and the streaming layout are prototypes.

## Native position saving replaces the status file

BibleReader now requests one file, containing the current chapter. Translation,
chapter, verse-number visibility, search and editor state remain in A5 globals.
Leaving calls `TextEditorSavePosition`, records its return, then closes the file.
Returning reopens with `FILE_OPEN_KEEP_POSITION`, refreshes, and redraws without
re-decoding or jumping to a verse. There is no file 2 / BIB2 status record.

The firmware moves the internal gap during position saving. The tests therefore
compare independent **logical** caret/viewport positions, not unchanged raw byte
offsets. They also check the native saved file position, successful API return,
retained A5 chapter/visibility, and exact screen after an AlphaWord round trip.
`MSG_INIT` still resets A5; reset recovery is not promised. Same-chapter jumps use
the existing 256-entry uint16 verse-offset table (512 RAM bytes).

The new save path exposed a harness handoff timing assumption: the first Applets
press initiates native position saving and AlphaWord launch. The harness now
waits for a changed stable menu display and for AlphaWord's visible-cursor state
before sending the return Applets key. Failures are retained in
`reader-native-position*`; `reader-native-position-probe-v3` and the full final
suites prove the corrected behavior. No failing capture became a reference.

## Native editor with three codec/search configurations

| Configuration | Full applet ROM | Static RAM | Psalm119 pure decode | Load and show Psalm119:176 | No-hit search CPU |
| --- | ---: | ---: | ---: | ---: | ---: |
| Phrase Huffman + original exact chapter index | 1,432,380 B | 2,874 B | 0.631 s | 2.554 s | 18.595 s |
| Word SCDC + query lexicon/map, no chapter postings | 1,425,750 B | 2,874 B | 0.435 s | 2.358 s | 38.948 s |
| Phrase Huffman + pruning + packed exact chapter index | 1,323,740 B | 3,146 B | 0.631 s | 2.554 s | 16.619 s |

File storage and native stack are additional. The complete numbered Psalm119
file is 14,467 content bytes plus the 512-byte native gap: **14,979 bytes**.
Static figures include diagnostic counters used in these builds. All displayed
ROM sizes come from the tested PROFILE=0 applet, not the profiling binary.

Word SCDC uses 223 stopper / 33 continuer bytes, the same raw front dictionary,
and the same 2,626-byte ROM spelling cache as Huffman. It decodes words directly,
without phrase expansion. With no chapter postings it retains a 53,542-byte
canonical query dictionary/normalization map. Its text container is 1,315,319
bytes including that spelling cache. It is only 6,630 bytes smaller than the
baseline complete reader, despite its faster decode.

The packed exact index is 252,739 bytes versus the baseline 368,039. Hybrid
postings choose delta/Elias–Fano/bitmap/complement representations; records use
14-bit canonical IDs and 18-bit posting offsets, and normalization IDs use 14
bits. The same chapters are selected as before. Pruning adds a 256-byte query
bitmap and 6,144 ROM bytes of grammar summaries, skipping irrelevant subtrees
while preserving verse and word ordinals. The complete combined applet saves
108,640 ROM bytes versus the current baseline; additional code/state accounts
for the difference from the raw index saving.

### Search timings and responsiveness

The no-hit query is `Jesus Jesus`; the profile runs the complete backend search
without idle gaps or painting between chunks. It includes query setup. Indexed
variants scan 207 candidate chapters; SCDC without postings scans all 1,189.
These are the intended end-to-end search configurations, not an equal-byte-count
microbenchmark. Native idle scheduling makes ordinary UI scans longer.

The first `believe` result illustrates that difference:

| Configuration | Query setup CPU | Scan CPU until first hit | Enter through final result screen |
| --- | ---: | ---: | ---: |
| Baseline | 6.03 ms | 1.7 ms | 1.381 s |
| Word SCDC without postings | 5.25 ms | 2.015 s | 20.857 s |
| Huffman + pruning + packed index | 79.4 ms | 1.5 ms | 1.380 s |

UI timings include idle waits, chapter construction and drawing, excluding the
user typing the query. Setup for pruning builds the rule bitmap once per query.
The native font is 6x16 for these comparisons.

The original 64-terminal-per-idle policy timed out during the unindexed SCDC
acceptance run. It left most of each roughly half-second idle interval unused.
All final configurations instead perform up to **50 ms** of search work per idle
callback, checked between 64-unit blocks. A block can slightly exceed the target;
this is a cooperative responsiveness bound, not a hard real-time deadline. Esc
remains handled by the normal message loop. Full corpus no-hit UI scans can
still take minutes, so CPU timings must not be presented as ordinary UI latency.

All three native configurations pass **36** exact screen/state checks and **7**
profile checks each. Both new backends also match every occurrence tuple for
15 host queries, covering case normalization, punctuation, internal apostrophes,
whole-word distinctions, overlaps and verse boundaries. SCDC reconstructs every
chapter byte-for-byte; the final Huffman decoder does too.

## Streaming layout without a chapter file

`Streaming.c` is a separate scrolling-only prototype. It requests **zero files**
and does not call the editor or guest filesystem. It keeps a 2,112-byte 264x64
one-bit screen buffer, the decoder, and one pending word. It greedily wraps words
using installed-font widths, composites original font glyphs and local verse
digits into that buffer, then submits one `DrawBitmap` operation. Digits have no
trailing space and use the same lowered superscript placement.

| Prototype | Full ROM | Static RAM | First Genesis page | Next Genesis page | Jump Psalm119:176 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Streaming phrase Huffman | 1,015,188 B | 2,866 B | 49 ms | 47 ms | 731 ms |
| Streaming word SCDC | 1,323,058 B | 2,866 B | 47 ms | 45 ms | 536 ms |

The link separates text/search/verse/summary resources so unused indexes are
actually discarded from this prototype. The streaming ROM totals contain **no
search UI or search index**, unlike the native applets above; the 1.015 MB figure
must not be called a complete searchable applet size.

The first Genesis page consumes 178 source bytes, versus decoding all of Genesis
for the native editor. This includes a pending word for the next line/page.
Forward paging continues from the current decoder state. A jump to a later verse
still decodes its prefix without laying it out: Huffman Psalm119:176 spends
701 ms seeking, 27 ms decoding/compositing the visible tail and 3 ms drawing.
The SCDC counterpart reduces seek/decode time. Whole-chapter buffers are absent.

Initial pages and jumps anchor wrapping at the requested verse, rather than
reconstructing the native editor's chapter-start layout. Forward pages are
continuous from that anchor. Previous page currently replays from the anchor;
it has no backward checkpoint cache. At chapter end, further paging can show an
empty page. General reference entry, search UI, selection, clipboard and full
font-dialog integration remain in the native reader, not this prototype. Font
profiles can be selected by the test/provider mechanism. No support for empty
omitted verse slots is claimed; the tested KJV has none.

The two streaming codecs each pass 12 exact screen/state checks with the system
6x16 font. Huffman also passes 12 each with the original Small proportional
11px and Extra Large proportional 32px fonts. Their pixel oracles are independent
source typesetting plus verified original font bitmaps/tables, not guest-rendered
references. There are 48 final streaming captures, including paging back,
references near chapter end, number toggles and clearing unused screen rows.
Cursor geometry is independently checked as hidden at (0,0); the test still makes
the real firmware hide/restore calls and preserves three identical LCD records.

The streaming layout is clearly faster for an initial page and substantially
reduces file RAM. SCDC's ~308 KB extra ROM barely changes first-page latency.
The most promising next integration is the streaming Huffman renderer with the
packed exact index/pruned search, retaining the native applet as the selection/
clipboard comparison. That integration is not performed by this prototype task.

## Reproduce

From the workspace root, after the host experiments documented in
[search-space.md](search-space.md):

```sh
python3 betawise/research/bible-reader/prepare_comparison.py
python3 betawise/tests/mame/asneo/check-bible-reader.py --system-font \
  --experiment word-scdc --output /tmp/bible-word-new
python3 betawise/tests/mame/asneo/check-bible-reader.py --system-font --profile \
  --experiment huffman-prune --output /tmp/bible-prune-profile-new
python3 betawise/tests/mame/asneo/check-bible-stream.py \
  --output /tmp/bible-stream-new
python3 betawise/tests/mame/asneo/check-bible-stream.py --vendor-font small \
  --output /tmp/bible-stream-small-new
```

All output directories must be new. Checks use private sessions, original
firmware/installed font assets, source-based exact screen expectations and
independent cursor/controller assertions. Raw logs, three-sample LCD records,
source/font captures, manifests, native binaries and timing taps remain under
`.research-work/bible-compression/compare2-*` and `stream2-*`. Earlier failed
experiments are retained as such. Aggregate results are in
[device-comparison-results.json](device-comparison-results.json).

The primary release `BibleReader.OS3KApp` is restored to the tested baseline,
PROFILE=0, TEST_FONT=0. The default streaming prototype is also restored to its
system-font Huffman build. Both are byte-identical to their passing captures.
Alternate codec builds are retained in each acceptance session's artifacts.
The publication list still selects only the base KJV BibleReader.

Standalone notes formats remain deferred; see [notes-formats.md](notes-formats.md).
