# Psalm 119 complete read-through profile

See the [unified native streaming comparison](native-streaming.md) for the new
moving-window/on-demand/background variants and ROM/A5 measurements.

**Follow-up:** [corrected native editor API usage](native-overhead.md) reduces
its page-traversal total from 9.13 to 4.12 seconds, essentially tying LCD-roll
streaming. The table below preserves the original wrapper measurements.

Measured 2026-11-23 in the current Neo MAME model, using NKJV, word/phrase Huffman,
full packed search index/pruning, visible superscript verse numbers, and the same
original system 6×16 font. Psalm 119 contains 176 verses, 12,873 source bytes
(including verse LF delimiters), and 314 wrapped lines in both readers.

Times are emulated foreground service seconds, summed from applet phase-write
taps. They exclude boot, reference entry, user reading/key gaps, and test captures.
Initial display starts at reference acceptance and ends with the first completed
Psalm screen. Traversal visits the last source line, then presses End to establish
source EOF explicitly. An additional pure-decode operation is measured separately
and excluded from read-through totals. No spinner was added.

| Reader | First display | Scroll by lines | Total by lines | Scroll by pages | Total by pages |
|---|---:|---:|---:|---:|---:|
| Native chapter file/editor | 2.050 s | 7.072 s | **9.123 s** | 7.081 s | **9.131 s** |
| Streaming, full repaint | 0.068 s | 23.385 s | **23.453 s** | 5.912 s | **5.980 s** |
| Streaming, restored LCD roll | 0.044 s | 5.959 s | **6.002 s** | 4.033 s | **4.077 s** |

The repainting streaming reader opens about 30 times faster than native, but
native consumes about 39% of its total foreground time for line traversal.
The restored LCD-roll variant is faster than both for a complete traversal:
6.002 seconds by line (66% of native), or 4.077 seconds by page (45% of native).

The native Space command currently calls the firmware's ordinary Down handler
four times; streaming next-page changes the viewport and draws once. Thus the
page result compares the actual current commands, including that implementation
difference. Line traversal uses the same 313 Down commands in both readers.
Native retains four visible rows at EOF; streaming permits its last partial page.
Both include the final End operation: about 251 ms native and a much smaller
streaming operation (see JSON). Native page-down could potentially improve by
moving once and refreshing once; that optimization was not made or benchmarked.

## Restored LCD-roll variant

The pre-UI-revision source survives at
`.research-work/bible-compression/reader9-before/Streaming.c`. Its ring blitter,
rectangle primitive and one-line viewport scrolling were restored behind
`LCD_ROLL=1` in the current Streaming.c, with the current Huffman decoder and
chapter-anchored line wrapping. The benchmark harness accepts `--lcd-roll`.
The default remains `LCD_ROLL=0`.

This comparison build uses four uniform 16-pixel rows in the 64-row scrolling
ring, origin zero, and leaves physical row 65 blank. The current repainting
renderer instead shifts text upward and distributes leading across 65 rows.
Consequently this compares the recovered renderer and geometry together, rather
than isolating only the controller command. Both still have exactly 314 wrapped
lines, identical source/font/word widths, and the same traversal commands.
Page commands repaint a full page in both variants; their speed difference also
reflects the simpler uniform-row drawing path, not LCD roll on page advances.

The line run verifies **310 hardware rolls**, controller start-line values through
wraparound, full visible pixels including the blank last row, and native caret
RAM coordinates separately from logical screen coordinates. The page run verifies
zero hardware rolls. This optional build is validated here for the system-font
read-through workload; modern dialogs, other font geometries and selection
interactions are not newly accepted for LCD-roll mode by these runs.

## Initial native cost

| Stage | Time |
|---|---:|
| File/editor/font setup | 0.306 s |
| Huffman decode, marker formatting, file writes | 0.854 s |
| Native TextEditorRefresh | 0.636 s |
| Position at verse and final native draw | 0.254 s |
| Total | 2.050 s |

Pure decoding into a byte count, without formatting/file/drawing, takes 0.641 s
native and 0.664 s streaming. Streaming enables decoder checkpoint tracking;
native does not. These are the builds as used by their respective readers.
A busy spinner could make the roughly two-second native wait clearer, but would
not eliminate the work. Initial native layout/drawing deserves attention as well
as the decoder if startup is optimized.

## Reproduction and evidence

`profile-readthrough.py` summarizes the twelve preserved output directories and
checks source EOF and independent pure-decoder byte counts. For each reader and
mode run these commands with a distinct output directory, then repeat each with
`--work-profile`:

```sh
python3 betawise/tests/mame/asneo/check-bible-reader.py --version NKJV --profile --system-font --experiment huffman-prune --readthrough line --output OUTPUT
python3 betawise/tests/mame/asneo/check-bible-stream.py --version NKJV --readthrough line --output OUTPUT
# Repeat with --readthrough page.
# Add --lcd-roll to the streaming command for the restored renderer.
```

Use the same MAME executable and firmware for all runs. This measurement used
`mame/neodiag` SHA-256
`94cd79f5df5a0ab8506386a467417abd7b71a12e82e46c40d4f047d3e4fb828b`.
The current model derives CPU speed from the VZ PLL state; absolute timings should
not be mixed with older fixed-clock benchmark reports.

Every captured state is checked against an independent source layout and exact
font bitmap, with separate caret/viewport/selection/controller assertions.
Normal firmware cursor hiding and three stable LCD RAM/flag samples are used;
no screenshot or vision model is the oracle. All sessions use disposable flash,
RAM, configuration and files. Raw captures, metrics, checks, expected bitmaps,
comparison hashes, logs, symbols and staged binaries remain in
`.research-work/bible-compression/readthrough-*`.

## Decoder work and battery interpretation

Work counts come from **separate instrumented runs**; their slower timings are
not used in the timing table above. A wrapper counts successful source bytes,
including repeated bytes emitted to restore a compressed checkpoint. Pure-decode
checks independently returned exactly 12,873 bytes and then EOF in all twelve runs.

| Traversal | Native source bytes | Repainting streaming bytes | LCD-roll streaming bytes |
|---|---:|---:|---:|
| By line, including initial display and final End | 12,873 | 76,869 (5.97×) | 30,940 (2.40×) |
| By page, including initial display and final End | 12,873 | 19,385 (1.51×) | 19,385 (1.51×) |

Native emits all 12,873 bytes initially and none during scrolling. Streaming emits
195 bytes initially and the remainder as traversal proceeds. Repainting streaming performed
1,558 checkpoint restores for line traversal and 395 for page traversal; LCD-roll
streaming performed 628 and 395 respectively. These
are compressed-position restores, **not full chapter decompressions**. The native
formatted file is 14,348 bytes, plus its 512-byte editor gap. The default streaming
viewer repaints its visible text on viewport changes. The optional LCD-roll
comparison build paints only the newly exposed line on a one-line scroll.

The native implementation is more efficient than repainting streaming for a
complete line-by-line read, despite doing all decompression up front. The restored
LCD-roll variant has the lowest total foreground time for both traversal modes.
Streaming is better for opening
briefly or reading only part of a chapter, and its current page command is faster
for the complete traversal. Native page handling remains an optimization lead.

These are foreground service time and decoder-work proxies, not measured joules
or battery life. LCD writes, memory traffic, idle behavior and actual hardware
current matter. No reliable battery percentage follows from this benchmark.

All twelve runs passed **2,400 exact screen/state checks**, including 800 for the
restored LCD-roll variant. Re-verification of the default renderer passed another
83 checks, and the offline test suite passed 27 tests. The default NKJV streaming build was restored with profiling
disabled and compared byte-for-byte equal to the existing reader9 release.
The aggregate [JSON results](readthrough-results.json) retain stage timings,
command counts, medians/maxima, EOF operation time, counters and evidence paths.
