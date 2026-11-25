# Native moving-window and lazy Bible readers

Current costs: [application-only ROM and maintenance metrics](reader-costs.md),
with compact native superscript fonts.

Measured on 2026-11-23. Both requested approaches are implemented, with on-demand
and background completion measured separately. All use the current word/phrase
Huffman resource, full packed exact index/pruning, NKJV Psalm 119, visible verse
numbers, original system 6×16 font and 314 wrapped lines.

The native prototypes use the firmware editor for wrapping, drawing, cursor and
selection operations. They do not contain a second word-wrapping engine or a
private framebuffer. The frontend intercepts navigation to manage residency,
then passes movement to the native editor.

Latest: [prewrapped native text](native-prewrap.md) avoids append-time ROM reflow
and passes selection plus six font fixtures.

Previous: [ROM layout trace and private viewport experiment](native-layout-disassembly.md)
separates full-file reflow from viewport-relative cache preparation.

Previous: [TextScanInsert page-lookahead experiment](native-lookahead.md) appends
without LCD writes, but retains a prefix-dependent insertion cost.

## Timing and memory

Times are emulated service seconds, excluding boot, reference typing, reading,
keyboard gaps and test captures. Totals include initial display, traversal and
the final caret-to-EOF command, as in the previous reports. Background work is
included even when it runs between keys. These are not measured energy figures.

| Reader | First screen | Total by line | Total by page | App ROM KiB | A5 bytes | File peak bytes | CC sum/max |
|---|---:|---:|---:|---:|---:|---:|---:|
| Native, original wrapper | 2.050 s | 9.123 s | 9.131 s | 19.71 | 3,122 | 14,860 | 523/60 |
| Native, optimized full chapter | 1.414 s | 8.487 s | 4.123 s | 19.66 | 3,122 | 14,860 | 522/60 |
| Native moving window | 0.370 s | 11.850 s | 7.562 s | 23.06 | 3,294 | 4,250 | 675/65 |
| Native append on demand | 0.370 s | 18.550 s | 14.233 s | 22.77 | 3,282 | 14,860 | 663/65 |
| Native background completion | 0.370 s | 8.606 s | 4.230 s | 22.95 | 3,290 | 14,860 | 672/74 |
| Native TextScanInsert lookahead | 0.350 s | 16.157 s | 11.657 s | 23.03 | 3,546 | 14,860 | 680/74 |
| Native private viewport lookahead | 0.346 s | 11.308 s | 5.155 s | 23.19 | 3,546 | 14,860 | 688/74 |
| Native prewrapped lookahead | 0.345 s | 8.528 s | 4.162 s | 23.50 | 3,566 | 14,860 | 705/74 |
| Native prewrapped full chapter | 1.440 s | — | 4.152 s | 23.38 | 3,558 | 14,860 | 698/65 |
| Custom, full repaint | 0.068 s | 23.453 s | 5.980 s | 20.02 | 3,862 | 0 | 725/57 |
| Custom, LCD roll | 0.044 s | 6.002 s | 4.077 s | 20.20 | 3,834 | 0 | 723/57 |

**Private viewport row:** reading-only performance is accepted; the final
long-selection fixture fails. This is a Neo 3.21 research experiment, not a
feature-complete reader.

**Background row:** decoding is allowed to finish after the first screen and
before scrolling. The harness waits for the actual EOF state, not a fixed sleep.
This takes about **7.17 s elapsed** after first display under the
firmware idle schedule, while the text remains readable and navigation remains
available. Its actual background service work is about 0.90 s. With immediate
page commands while decoding continues, total service time is **6.345 s** instead.
Thus the fast first screen is real, but background completion is not instantaneous.

ROM/A5 costs above are current production builds with the compact superscript
font. **App ROM excludes 1,311,826 bytes of shared Bible text/dictionaries,
indexes, pruning/count tables and book metadata.** No choice here changes Bible
compression. It includes executable code, UI/font assets, headers and app data.
Native superscript storage is now **3,584 bytes**, reduced from 36,864, with no
change to digit pixels or character codes. The old large ROM gap was primarily
wasted glyph padding. [The cost/maintenance report](reader-costs.md) separates
executable bytes, assets and standardized structural metrics.

CC is summed cyclomatic complexity / maximum function complexity, counting our
active reader, decoder and search C implementations. SDK/firmware and generated
assets are excluded. It is a branching/maintenance proxy, not an inherent speed
or quality ranking. The JSON/report also give function counts and C-token volume.

Timing columns retain the earlier measured builds. The lossless font packing
was separately validated with 200 checked states and all 80 legacy digit/band
bitmaps. A fresh compact-font full Psalm 119 page test took 4.121 seconds versus
4.123 seconds previously; the complete timing matrix was not needlessly rerun.

A5 is static applet RAM, including decoder/search state and current diagnostics.
File peak is logical file content plus the native gap during the measured
6×16 read-through. Stack, clipboard contents, file-table bookkeeping and shared
OS/dialog workspace are additional. FileGetCapacity reports a large expandable
file capacity here; it is not treated as committed file RAM. A separate
[file-record audit](native-streaming-file-audit.json) matches the final raw file
to its private-session RAM record and verifies a 512-byte minimum reservation,
not a hidden 64 KiB reservation. Other fonts can
require larger residency because more text may fit on screen.

## Implementations

* `NATIVE_STREAM=1`, **moving window**: append complete words ahead of navigation.
  Near the window limit, evict at a line boundary reported by the native editor.
  The measured file peaks at 4,250 bytes instead of 14,860. Chapter-global cursor
  and selection anchors stay in A5; native selection sees their intersection
  with the resident file. Copying re-decodes the selected span with a citation,
  so selections are not restricted to resident text. Backward access outside
  the window replays a prefix and restores the old viewport; it is functional
  but can hitch. Compact compressed restart checkpoints are a remaining
  optimization, not implemented in this prototype.
* `NATIVE_STREAM=2`, **append on demand**: show a prefix, extend near its end, and
  keep everything decoded. It eventually occupies a full chapter file. Its
  repeated native layout/reconciliation grows with the prefix and makes this
  the slowest native variant on the first complete traversal. Later access to
  already decoded text needs no more decompression.
* `NATIVE_STREAM=3`, **background completion**: show the same initial prefix,
  then append the remainder on idle messages without repainting the page.
  Slices have a 50 ms budget plus one final word-aligned chunk. They check both
  queued and physically held keys, yielding before short key presses are lost.
  The largest measured slice was 66.7 ms. Native layout is reconciled when navigation
  needs the newly appended text. This is a good fast-first-screen compromise
  when keeping the full chapter in RAM is acceptable.

Native Home/End retain chapter/document semantics, including when only a prefix
has been decoded. Select All completes the chapter and preserves an exact
chapter-wide selection. These completion requests batch the remaining decode
rather than repeatedly reconciling every appended block.

## Native API details found by the prototypes

Appending through FileWriteBuffer alone leaves the native cached EOF/layout
state stale. Reapplying the scan position makes the new tail accessible, but
costs a layout pass; this is the major append-on-demand penalty. This experiment
does not establish that this is the fastest possible incremental-edit API use:
a TextScanInsert-based invalidation path remains a lead to investigate.

The native file stores cached soft wraps as byte 0x81 in place of spaces.
The verifier independently checks resident encoded bytes against the expected
chapter slice after normalizing that cache byte and the cached-hyphen byte 0xAD to 0x2D. Prefix deletion counts raw
encoded bytes, including the editor gap; source/global logical positions do
not. Accounting for that difference is essential when evicting text.

All variants still use one OS-owned file; chapter/translation/residency state
stays in A5, and applet switching uses TextEditorSavePosition. The streaming
custom readers use zero files. No user saved session is used in tests.

## Validation and production images

Accepted prototype runs contain **1,497 checked screen/state checkpoints**:
complete line and page traversals, immediate-input background traversal,
selection extending beyond an evicted anchor, exact selection/full-chapter
clipboard text and citations, backward movement through eviction, chapter
Home/End, verse and exact-search jumps, verse-number toggling, current-verse
copy, applet return, and original vendor Small → system font selection.

Every screen uses independent source/font bitmap expectations, separate native
caret/viewport assertions, normal cursor hiding/restoring, and three identical
LCD RAM/flag samples. Resident file slices are checked independently too.
The physical 65th row is asserted blank for native readers; LCD-roll custom
also leaves it blank, while repainting custom uses the full panel. No model
vision or screenshot inference is used. A [separate panel audit](native-streaming-panel-audit.json) also checks the
blank 65th row of every accepted native/control capture. The offline suite
passes 27 tests.

The moving-window path can perform visible layout work while reconstructing a
far-away window. Busy indicators, smoother transition painting and compressed
restart caches remain polish/optimization work. These are experimental
alternatives, not a switch of the default/demo reader.
All retain applet ID 0xA1B1, and are alternative installations. The table uses
NKJV to match the existing benchmark; ordinary builds still default to KJV.

From the workspace root:

```sh
make -C betawise/applets/BibleReader READER=BibleReader VERSION=NKJV PRUNE=1 PROFILE=0 TEST_FONT=0 NATIVE_STREAM=1 NATIVE_PAGE_TEST=1
# NATIVE_STREAM=2: append on demand; NATIVE_STREAM=3: background completion.
# NATIVE_STREAM=0: existing full-chapter native reader.
```

The generated production images were retired during cleanup. Symbols, source
snapshots and stack-usage files describe the historical run; use the
[reproduction commands](reader-costs.md#reproduction) to rebuild these variants:
* `BibleReader-NativeWindow-NKJV.OS3KApp`
* `BibleReader-NativeDemand-NKJV.OS3KApp`
* `BibleReader-NativeBG-NKJV.OS3KApp`

Use `check-bible-reader.py --native-stream window|demand|background` with
`--profile --system-font --experiment huffman-prune --readthrough line|page`
to reproduce timings, `--feed-features` for selection/search/resume coverage,
`--feed-end-smoke` for lazy Home/End and whole-chapter copying, and
`--vendor-font small --feed-font-smoke` for variable-width font coverage.
Background runs wait for EOF before the first scrolling command by default;
`--background-rapid` measures input during decoding. `measure-reader-builds.py`
rebuilds all production sizes; `summarize-native-streaming.py` joins the accepted
evidence. [JSON results](native-streaming-results.json) preserve all paths,
timings, counters, production hashes and memory sizes.
