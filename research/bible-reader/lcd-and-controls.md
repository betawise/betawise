# Neo LCD geometry and reader controls

Historical measurements/design below. See the [current UI revision](reader-ui.md)
for the updated repainting renderer and demo.

## 65 physical rows, a 64-row scrolling ring

The user was correct: the Neo panel is **264×65**. Neo 3.21's system-information
height selector returns 65 (`0x426072: moveq #65,d0; move.l d0,(a4)`);
width is 264 at `0x42607A`. Existing typed syscall coverage independently asserts
these returns. MAME's Neo driver had selected a 264×64 screen despite its LCD
device already retaining all nine RAM pages. The driver now exposes 264×65.
No CPU, clock, controller memory or firmware code was changed for this fix.

The emulated controller is ST7565R-compatible; the physical dies remain under
epoxy, so this is a protocol/model identification, not a verified die marking.
The [ST7565R datasheet](https://focuslcds.com/wp-content/uploads/Drivers/ST7565R.pdf)
separates 64 main rows from the final COMS row: pages 0–7 are the main 64-row
ring; page 8 contains one bit per column for COMS. Start-line scrolling and
COM reversal affect the main rows; COMS stays fixed. Duty is selected by
hardware pins. The modeled command set has no arbitrary top/bottom clipping
window. Display-off and all-points commands affect the display globally.

Consequently, changing every `&63` to modulo 65 would be wrong. Full-panel
rendering reads physical y=64 from page 8 bit 0. The generic exact bitmap oracle
now optionally accepts 264×65 while retaining the canonical 264×64 text-region
default for existing 44×8 terminal tests. All nine pages remain preserved in raw
records. New comparator tests assert that COMS survives nonzero start-line and
COM reversal, follows SEG reversal, and remains excluded from the text region.

## What AlphaWord actually does

The original Small font is 11 pixels high with a blank last bitmap row for
printable ASCII. AlphaWord uses pitch 11 and six lines. The sixth line starts at
y=55; its descenders reach **y=64**. The unused blank font row would be y=65,
outside the 65-row panel. It therefore fits six lines without losing descenders.

The previous 64-row capture led to an incorrect claim that AlphaWord cuts the
descenders off. Its retained raw page-8 bytes already contained them. A new
original-AlphaWord MAME run types six explicit `agypq0N` lines using the original
Small font. Independent source/font typesetting matches all 65 physical rows,
including six descender pixels at y=64. The test also checks the actual MAME
screen output against that row, after hiding the native cursor through firmware,
observing its return and obtaining three identical complete RAM/flag samples.
It preserves/restores guest registers and scratch RAM.

Native DrawBitmap (`0x4205DE`) and RasterOp (`0x420C20`) reject rectangles beyond
264×66, and add the ROM roll byte at `0x48C1`. They do not provide a programmable
LCD clipping window. Native text rendering ultimately uses bitmap/raster helpers;
editor geometry and glyph placement determine its bounds. The file-backed
reader's retained single-line scrolling captures keep the controller start line
at zero; the streaming reader explicitly changes it. The ROM also contains a
separate console hardware-roll path at `0x422452`, adding font height modulo 64.
These are different paths; the existence of console rolling does not establish
that the native file editor uses it.

Streaming keeps the 65th row blank, uses a 10-pixel pitch only for the verified
Small font blank row, and fits six complete lines into the main ring. This is a
compact-leading choice; it is **not necessary to save AlphaWord's descenders**.
One-line scrolling keeps the native caret in the longer contiguous segment when
its line crosses the ring boundary. Text/selection are complete. A future 65-row
text layout would need software management of the independent COMS row when
scrolling; it cannot treat the entire panel as one hardware ring. Current unused
main-ring margins are cleared with RasterOp and glyphs are split across the
64-row address boundary. There is no screen-sized applet bitmap.

## Search and reference keys

The [manufacturer's NEO manual](https://uk.renaissance.com/wp-content/uploads/2013/08/NEO2-User-Manual.pdf)
(section “Finding Text”, printed pp. 26–27; keyboard summary pp. 189–190)
specifies Find/Cmd+F for a new search, Cmd+G for Find Again, and Ctrl+Find for
Find/Replace. Cmd+Find is the Typing Timer, not Find Again in AlphaWord.
The Bible reader's Cmd+Find mapping is a new reader-specific convenience.

[Logos's official shortcuts](https://support.logos.com/hc/en-us/articles/360016370932-Keyboard-Shortcuts)
use Ctrl+G on Windows, Cmd+G on macOS, for its reference/navigation box.
[Accordance documents](https://www.accordancebible.com/cant-go-to/) entering
references through its Go To field, which can be reached by two Tab presses.
There is no universal shortcut that overrides Neo's established Find Again key.

Both reader implementations now use:

| Key | Meaning |
| --- | --- |
| Find; Ctrl+F; Cmd+F | New exact word/phrase search |
| Cmd+Find | Next occurrence |
| Shift+Cmd+Find | Previous occurrence in the 32-result history |
| Cmd+G / Shift+Cmd+G | Retained next/previous aliases, consistent with Neo Find Again |
| G / Ctrl+G | Open the reference dialog |

This gives a dedicated Find-key workflow and a recognizable reference shortcut
without changing Cmd+G's existing Neo meaning. Plain F or / also opens search;
N/P pages in streaming, while N/P remains search history in the native reader.
Ctrl+Find is not a replacement operation in this read-only reader.

## Evidence

Private sessions under `.research-work/bible-compression/`:

- `reader7-lcd-device`: 67 parallel-bus/render/reset checks, including physical
  row 64 and its independence from start-line scrolling, plus original-firmware
  drawing/capture/save/restore and all raster operations.
- `reader7-alphaword-65`: original applet/font, exact full-panel source oracle,
  explicit cursor geometry, preserved raw RAM/flags and full-panel pixel hashes.
- `reader7-release`: 51 production streaming checks, including all new key aliases;
  all 65 panel rows are asserted, with a blank COMS margin.
- `reader7-small`, `reader7-medium`: 54 checks each for installed-font selection,
  clipboard, cursor/selection and repeated forward/backward rolling.
- `reader7-native-release`: 40 checks for the equivalent native editor reader.
- `reader7-benchmark`: 35 source/font/state/bitmap checks and operation timers.
- `reader7-repl`: all nine canonical Neo cases, 91 offline assertions, including
  Logo text and exact graphics geometry. All 25 offline oracle unit tests pass.

All use disposable flash/RAM. Font and pixel checks are local and deterministic;
no model vision or screenshots as an oracle are used. Older sessions remain
historical; their displayed 64-row crop omitted COMS even though raw data kept it.
