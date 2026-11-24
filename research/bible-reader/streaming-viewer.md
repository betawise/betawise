# Streaming viewer with selection: measured checkpoint

Historical measurements/design below. See the [current UI revision](reader-ui.md)
for the updated repainting renderer and demo.

Tested on original Neo 3.21 firmware in disposable MAME sessions. Current
emulator now exposes the full **264×65** physical panel. Streaming text uses
the 64-row scrolling ring and leaves the independent COMS row blank. The
[geometry/control investigation](lcd-and-controls.md) corrects the earlier
64-row-only AlphaWord interpretation. No energy measurements
were made. Machine-readable results: [streaming-viewer-results.json](streaming-viewer-results.json).

The viewer uses original installed font bitmaps with raw DrawBitmap/RasterOp
syscalls, native firmware caret drawing and direct LCD start-line commands.
It has cursor/word/chapter movement, Shift selection, exact-selection clipboard
copy with citation, native partial reference entry, full-index exact search,
32-result history, font selection, optional superscript numbers and applet-return
state in A5. There is no screen bitmap or private chapter/status file.

## Speed

Times exclude boot, menus, typing and keyboard scheduling. Streaming includes
checkpoint restore, decoding, layout, drawing and native caret placement.
Native phase taps bracket the corresponding firmware operation. Same original
6×16 system font, numbered text and full packed chapter index/pruning backend.
Matthew 2 is the median chapter: 3,284 ASCII bytes and 23 verses.

| Operation | Native editor | Streaming viewer |
| --- | ---: | ---: |
| Fresh Matthew 2 first page | 739 ms | 44 ms |
| Fresh John 3 first page | 839 ms | 45 ms |
| Cached Matthew 2 redraw | 80 ms | 45 ms |
| Page forward | 89 ms | 53 ms |
| Page backward | 85 ms | 51 ms |
| One-line scroll down | 22.2 ms | 19 ms |
| One-line scroll up | 21.0 ms | 18 ms |
| Cursor right, no scrolling | — | 6 ms |
| Extend selection one character | — | 25 ms |
| Fresh Psalm 119:176 jump | — | 747 ms |

Ten forward/backward pages exercise eviction of the bounded 32-line checkpoint
cache. Normal pages cost 49–54 ms; an evicted backward page costs 116 ms in
this sample. It replays from the reference anchor. Long chapter-end selection
also scans chapter text; ordinary viewport navigation does not decode the whole
chapter. An unnecessary second prefix decode on fresh verse jumps was removed;
Psalm 119:176 fell from 1,464 to 747 ms without adding a seek index.

A single-line roll paints exactly one new text line. Instrumented LCD data writes
are 1,052 down / 1,007 up, versus roughly 4,340 for a full redraw. Cursor movement
alone writes four to eight data bytes. These include normal native caret
hide/show. At the ring boundary the caret occupies the longer contiguous segment
of its line; full text and selection are preserved. Split glyph blits handle
wrapped controller addresses, including fonts whose pitch does not divide 64.

## ROM and RAM

| Equivalent full-index KJV build | ROM bytes | Static RAM | Private chapter file |
| --- | ---: | ---: | ---: |
| Native editor | 1,323,794 | 3,146 | 3,970 bytes typical; 14,979 max |
| Streaming viewer | 1,291,122 | 3,816 | None |

Streaming uses **670 more static bytes**, saving **3,300 bytes total** for the
median chapter or **14,309 bytes** at Psalm 119, before file allocation overhead.
Firmware stack, shared clipboard and OS allocations are additional in both.
Copying a chapter intentionally creates ordinary shared clipboard content.

Common ROM data is 1,268,416 bytes: text 1,007,155; full packed exact index
252,739; grammar summaries 6,144; verse counts 2,378. Streaming's remaining
code/navigation/resources total **22,706 bytes**. It is **32,672 bytes smaller**
than the equivalent native reader, which includes padded local superscript font
faces. Compared with the old scrolling-only streaming prototype, cursor,
selection and full UI add 10,340 ROM bytes and 1,272 static RAM bytes.

## Acceptance and remaining work

The production build passes 51 deterministic source/font/bitmap/state checks;
the system-font benchmark passes 35, all against the corrected 65-row panel. Original Small and Medium pass 54 checks each on the corrected
emulator;
Large, VLarge, XLarge and Tiny retain 50 checks each from the earlier revision, including the real font picker,
selection/citations, font return and repeated forward/backward LCD wraparound.
All 1,189 chapters match independent source decoding, including reverse chapter
order. Exact pixel assertions use reviewed original font assets, not captures as
expected images or model vision. Captures preserve native registers/scratch,
check cursor geometry before firmware hide, observe returns, record three
identical LCD RAM/flag samples and restore cursor state. Raw evidence is retained
under `.research-work/bible-compression/` in the sessions listed in the JSON.
The canonical Neo suite also passes all nine cases (91 assertions), including
Logo graphics; all 25 offline oracle unit tests pass.

Original AlphaWord uses pitch 11 for the Small font: six rows span 66 pixels,
with the final blank row outside its 65-row panel. Descender ink on font row 9
is displayed at physical y=64. The old 64-row capture incorrectly omitted it. Streaming uses pitch 10 only when
that final blank row is verified, preserving descenders. Full-panel source/font
checks now cover AlphaWord's sixth-line descenders and streaming's blank COMS
margin. Find/Cmd+Find and Ctrl+G aliases are implemented and tested. Notes,
editing, persistent bookmarks and physical battery measurements remain deferred.
