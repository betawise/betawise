# Prewrapped native Bible reader

Measured 2026-11-23 on the same pinned Neo 3.21 / dynamic-clock MAME as the
previous comparisons. NKJV Psalm 119, numbered ASCII text, identical Huffman
resource and packed exact search index. No normal reader default changed.

## Result

**Supplying native wrap-cache bytes works.** An initial prefix can be decoded,
wrapped by our C code, and painted by the OS; later prefixes are prepared during
idle without calling either TextScanInsert or private ROM layout 0x42B5D0.
The lookahead prototype passes normal scrolling, long selection, copying with
citations, jumps/search and six font fixtures. It remains an experiment with the
hard-wrap limitation below, not a generic rich-text editing engine.

| Reader | First screen | Entire chapter by page | Entire chapter by line | App ROM KiB | A5 bytes | File peak bytes |
|---|---:|---:|---:|---:|---:|---:|
| Native optimized full chapter | 1.414 s | 4.123 s | 8.487 s | 19.66 | 3,122 | 14,860 |
| Native TextScanInsert lookahead | 0.350 s | 11.657 s | 16.157 s | 23.03 | 3,546 | 14,860 |
| Private viewport-layout prototype | 0.346 s | 5.155 s | 11.308 s | 23.19 | 3,546 | 14,860 |
| **Prewrapped native lookahead** | **0.345 s** | **4.162 s** | **8.528 s** | **23.50** | **3,566** | **14,860** |
| Prewrapped native full chapter | 1.440 s | 4.152 s | not measured | 23.38 | 3,558 | 14,860 |
| Custom LCD roll | 0.044 s | 4.077 s | 6.002 s | 20.20 | 3,834 | 0 |

App ROM excludes 1,311,826 common Bible/navigation bytes and includes the native
3,584-byte superscript asset. A5/file figures exclude stack, clipboard contents,
file bookkeeping and shared OS workspace. Times are emulated service, including
all idle decoding/wrapping work and final End-to-EOF; reading time, keyboard gaps,
firmware idle scheduling delays and captures are excluded. No battery estimate.
The private viewport prototype has a known long-selection failure; its row is
reading-only comparison, not feature parity. Unchanged older rows reuse their
previous accepted runs. The normal first-page build still retains the decoded
prefix, so its peak chapter-file RAM is unchanged.

The new lookahead run has 55 idle slices, **1.105 s total idle service**, maximum
**21.892 ms**. Every slice has **zero LCD data writes**. TextScanInsert's previous
maximum was 266.683 ms. Whole-chapter prewrapping gives no meaningful startup
speed gain: the approximately 0.2-second native wrapping pass is replaced by our
own work, while decode, formatting/file fill and chapter setup remain.

The final paint interval is **19.049 ms** for both a 257-byte initial prefix and
the complete 14,348-byte formatted chapter. There is no hidden full reflow in
that draw-only path. Timing runs preceded a bottom-margin clearing fix; the
6x16 benchmark occupies all 64 rows, so that fix's raster operation is not taken.

## Implementation

`NATIVE_STREAM=6` builds `BibleReader-NativePrewrap[-NKJV].OS3KApp`; `7` builds
`BibleReader-NativePrewrapFull[-NKJV].OS3KApp`. All share the existing 0xA1B1 ID
and are alternatives, not simultaneous installations. KJV remains the default.

`NativePrewrap.h` is a small append-time pass over newly decoded encoded bytes:

* Measure glyph widths using the installed font descriptors. The private verse
  face contributes four pixels per digit; native B1/B2 formatting tokens do not
  advance the line.
* Track the latest fitting space/hyphen. Replace a wrapping space with **0x81**
  or hyphen with **0xAD**, leaving its plain-text meaning unchanged.
* Keep 20 bytes of wrap state across decode batches. Revisit only the last break
  candidate when a later word makes the line overflow; never rescan the prefix.
* Modify the current RAM file in place, through a pointer obtained after file
  writes are complete. No allocation occurs while that pointer is in use.
  No bytes are inserted or deleted, so verse and selection offsets remain valid.

This is a pass per decoded batch, rather than buffering the whole chapter in a
second RAM array. A 512-byte existing formatting buffer coalesces file writes.
The full-chapter variant repeats these batches before its first paint.

Initialize the native editor and install fonts while the file is empty. For
initial display at chapter start, send native repaint message **0x1B, parameter
zero** through TextEditorHandleMessage. That paints cached text without invoking
layout. Initial editor geometry/caret state comes from the empty initialization.
Raw appends get no refresh or SetScanPosition call; ordinary native movement
uses the prepared wrap markers. Other existing commands (arbitrary jumps, font
changes, applet-return reconciliation, Home/End) may still request full reflow.

`NativePrewrap.h` adds no shared-library dependency. Its C code is statically
linked only for modes 6/7. No absolute private layout address is called in these
builds. This still relies on observed Neo encoded-text/cache and notification
semantics; it is not a portable EPUB/CSS renderer.

### Limits

Input is controlled ASCII Bible text plus verse-number font tokens. Hidden
regions, arbitrary forms and a full rich-text document grammar are not handled.
An overwide unbreakable word currently returns error 21 rather than inserting
native **0x8F** hard-break bytes. Adding those bytes needs consistent verse,
search and selection offset handling. That case was not encountered in the
accepted fixtures; the experiment must not silently claim support for every
possible installed font/document. Font changes rebuild the temporary chapter
from source, invalidating the old cache.

## Can another syscall request layout mode zero?

The layout entry is **0x42B5D0**, not 0x4285D0. All direct call sites in the pinned
ROM were inspected. Ordinary character insertion through TextEditorHandleMessage
reaches a zero-argument push at **0x4290DA**, then calls layout at **0x4290DE**.
Some single-character deletion/deferred-typing helpers also use mode zero.
These perform editing; they are not a harmless standalone layout request.

The examined TextScanInsert, TextEditorRefresh, TextEditorSetScanPosition and
font-setting paths use mode **one**. TextScanInsert has no suppression argument.
Passing false to SetScanPosition does not suppress reflow. No standalone public
syscall selector for mode-zero/no-draw layout was found. Native repaint **0x1B/0**
is useful here because it calls **neither** layout mode: we already prepared the
cache, so it only needs to draw.

## Does AlphaWord reuse cached wrapping when opening?

It does reuse the native cache for drawing and ordinary navigation. But that
does not imply every open skips layout. In the original Neo AlphaWord image
(SHA-256 `a8ae516734a0e0b2e19d51ffb7dff3893074ca733fa40207cbff7ead1433f29e`),
the examined file-switch helper at offset **0x606C** calls TextEditorInit at
**0x6352**, via stub **0x12ED0** (verified opcode A2BC). It passes flags **0x10**,
not deferred-layout flag 2. This reaches normal editable preparation and a full
layout pass. A retained live editor/repaint route is different from initializing
another file. Do not generalize that one file-switch path to every focus event.

Full layout mode one still measures through the file even when cached markers
are present. Incremental mode zero can stop at stable cached breaks, which is
why the cache helps edits/scrolling. Our new path avoids the full-pass entry
points for initial paint and idle append, rather than hoping that prewrapping
makes a full-pass call free. See [the ROM trace](native-layout-disassembly.md).

## Validation

All checks use disposable flash/RAM, independently source-derived expected
bitmaps and original font assets, cursor geometry before hiding, three identical
LCD RAM samples and firmware cursor restoration. No screenshots/model inference
as an oracle. Normalized file contents and final source EOF are independent checks.

Artifacts under `.research-work/bible-compression/`:

* `native-prewrap-page-v1`: 83 passed states, timings and append audit.
* `native-prewrap-line-v1`: 317 passed states, timings and append audit.
* `native-prewrap-full-page-v1`: 83 passed states, full-file first paint.
* `native-prewrap-features-v1`: 49 passed states, including 16 selection-page
  extensions, exact clipboard/citation, backward motion, jumps/search and return.
* `native-prewrap-{small,medium,vlarge,tiny}-final`: 17 passed states each.
* `native-prewrap-{large,xlarge}-v1`: 17 passed states each.
* `native-prewrap-production-margin` and `native-prewrap-full-production-margin`:
  production binaries, ELF/maps, source snapshots, AST metrics and stack records.

Total **634 passed states**. The earlier small/medium/vlarge/tiny v1 runs are
rejected, even though key delivery completed: exact bitmap comparison found Go-to
prompt residue below the complete native text rows. Wrap positions matched the
independent typesetter. The fix clears only that unused bottom margin before
initial drawing, without changing expected images/typesetting or idle behavior.
Rejected captures and logs are retained. See [machine-readable results](native-prewrap-results.json).

```sh
python3 betawise/tests/mame/asneo/check-bible-reader.py --version NKJV --native-stream prewrap --system-font --profile --readthrough page --experiment huffman-prune --output OUTPUT
python3 betawise/research/bible-reader/profile-readthrough.py OUTPUT --output SUMMARY.json
python3 betawise/research/bible-reader/check-native-lookahead.py OUTPUT --viewport --output AUDIT.json
```

Use `--readthrough line` for line traversal; `--native-stream prewrap-full` for
whole-chapter-first. Optional production build:

```sh
make -C betawise/applets/BibleReader READER=BibleReader NATIVE_STREAM=6 NATIVE_PAGE_TEST=1 VERSION=NKJV PRUNE=1 PROFILE=0 TEST_FONT=0
```
