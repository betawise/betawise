# Reader UI revision: chapter layout, fonts and centered panels

Current NKJV demo, from `/home/kirk/Projects/Alphasmart`:

```sh
bash .research-work/bible-compression/reader9-release/launch.sh
```

The launcher uses a new disposable copy of the tested ROM/config/NVRAM.
Choose BibleReader-Stream-NKJV using Applets (host F9) if needed.
Ctrl+Alt+Cmd+F opens the installed-font picker. All five original vendor fonts
and the 8 px terminal font are installed together. The demo finishes in Small.

## Drawing and fonts

Viewport changes now repaint instead of using the LCD start-line register.
Both start lines remain zero, including while the native font picker is open.
This avoids the native dialog's rolled-coordinate mismatch and allows ordinary
use of the full 264×65 panel, including its independent COMS row. Scrolling
continues to stream/decode visible lines from bounded checkpoints; no screen
bitmap or chapter file has been added.

| Selected face | Visible rows |
| --- | ---: |
| Original system 16 px | 4 |
| Terminal 8 px | 8 |
| Vendor Small 11 px | 6 |
| Vendor Medium 13 px | 5 |
| Vendor Large 16 px | 4 |
| Vendor VLarge 21 px | 3 |
| Vendor XLarge 32 px | 2 |
| Tiny 6 px, tested separately | 10 |

Small uses its original 11-pixel line pitch, with the blank font row providing
the requested one-pixel spacing. Remaining vertical space is distributed between
rows for other sizes. For fonts whose capital letters have a top inset, text
starts one pixel higher; pixels above y=0 are clipped by the viewport. Fonts
already drawing capitals at y=0, including Tiny, keep their original top origin.

Verse digits align with the cap top rather than the old bitmap-band-derived
offset. Their baseline is above the body baseline. Fonts below 8 px use a
3×4 numeral design; larger fonts use 3×5. Digits still have no inserted space
before verse text.

## Selection and overlays

Selection computes the symmetric difference of its old/new spans. Existing
highlight remains untouched; only added/removed pixels are inverted. Empty and
fully selected rows use cached line bounds without decoding. Partial boundary
rows are scanned without painting. Cursor updates use the firmware caret.

Go To and Find now share a centered 252×36 white panel with a one-pixel black
border. Notices such as Copied, invalid references and search status use the
same style. All panel text uses the original built-in ROM system face, not a
Betawise font. Input supports insertion, Backspace, Clear File, Home/End and
left/right. The visible field follows the cursor for long input.

Opening a panel leaves the underlying text in place. Closing it repaints only
the covered horizontal band, with selection restored correctly. Esc without an
overlay removes selection by changing highlight pixels, without a full repaint.
The native font picker also stays at scroll offset zero.

The shared graphics API now has:

```c
void DrawRectangle(uint16_t x, uint16_t y, uint16_t width, uint16_t height,
                   bool center_black, bool border_black);
```

True selects black, false selects white. Matching colors produce a solid fill;
different colors add an inclusive one-pixel border. Zero extents do nothing.
Coordinates must lie inside the display. Horizontal/vertical DrawLine calls now
use one RasterOp rather than one syscall per pixel; diagonals retain the existing
algorithm. Full-panel source/font tests validate the actual widget pixels, and
host raster tests cover all fill/border color combinations, degenerate sizes,
display edges and both axis directions against independent Pillow geometry.

## Stable chapter wrapping

Every view is laid out from chapter start. A reference jump or word-search hit
finds its source offset during that layout scan, then displays its natural line
and positions the caret. Earlier verse text can therefore appear on the same
line. Scrolling upward does not introduce the old forced break and short line.
Font and number changes reflow around the current source offset rather than
returning to the last requested reference. The cache still holds 32 compressed
line points; evicted positions replay chapter layout.

## Measurements and tradeoff

NKJV, original Neo 3.21 firmware and original system 6×16 font, private MAME
sessions. Operation timers exclude boot, menus and reference typing.

| Operation | Current repainting renderer |
| --- | ---: |
| Fresh Matthew 2 first screen | 70 ms |
| Cached full redraw | 69 ms |
| Page forward / backward | 75 / 76 ms |
| One-line viewport movement down / up | 77 / 76 ms |
| Cursor movement within the viewport | 6–7 ms |
| Extend/shrink selection by one character | 7 ms |
| Clear selection | 1 ms |
| Open Go To panel | 12 ms |
| Psalm 119:176 with chapter-anchored layout | 1,703 ms |

The old hardware-roll renderer updated a line in about 19 ms and used different
jump-anchored wrapping. Current viewport movement repaints the screen, trading
that speed for full-height fonts and simpler dialog/display state. Initial and
cached redraws also reflect the new top origin/spacing and unaligned bitmap
positions. Long verse jumps now include chapter-prefix layout, not just prefix
decoding. These changes do not imply lower physical energy use; that remains
unmeasured.

A glyph-batching experiment reused existing copy scratch rather than adding a
buffer, but increased a normal redraw from about 68 to 85 ms. It was removed;
the final build uses direct glyph drawing. Retained experiment records remain
private under `reader9-batched` / `reader9-demo` for diagnosis, not as release
measurements. One experiment's harness stopped during applet-menu navigation;
that harness routing predicate was corrected before final acceptance.

| Production NKJV applet | Bytes |
| --- | ---: |
| Complete ROM | 1,332,322 |
| Common Bible text/index/pruning/count resources | 1,309,978 |
| Remaining code/runtime/navigation/resources | 22,344 |
| Static applet RAM | 3,862 |
| Private files | 0 |

Firmware stack, native dialogs and shared clipboard allocations are additional.
The initial-model/common resource bytes are unchanged. RAM is 46 bytes above
the previous 3,816-byte release. Neither a screen buffer nor decoded chapter is
retained. Selection spans use bounded automatic scratch while being updated.

## Acceptance

All checks use independent source/font geometry and exact full-panel pixels,
including the 65th row. They verify cursor coordinates and height before hiding
it through firmware, observe the return, capture three identical full RAM/flag
samples and restore registers/scratch/cursor state. Font menus are checked to
have zero start-line offset throughout opening, interaction and closing. No
screenshots or model vision serve as the oracle; sessions are disposable.

Private records under `.research-work/bible-compression/`:

- `reader9-release`: 83 production NKJV checks, all five original vendor
  fonts identified by exact original bitmap bytes; system and terminal faces;
  repeated scrolling, source-anchored jumps/search, font changes, clipboard,
  centered panels, input correction and invalid-reference notice. It also checks
  searching a hyphenated name, the exhausted-search notice, returning to earlier
  matches from that notice, and leaving/returning while a Copied notice is open.
- `reader9-tiny-release`: 71 checks with the original 6 px Tiny provider and its
  native font-picker selection. A first test run sent keys faster than the
  repaint could consume them; final tests wait for each reader operation to
  finish before sending the next navigation key.
- `reader9-no-font-final`: 10 targeted production checks with no Betawise font
  applet installed, including the original-system-font Copied panel.
- `reader9-kjv-final`: 10 production KJV checks of the updated layout/UI.
- `reader9-benchmark-final`: 35 NKJV source/font/bitmap/state benchmark checks,
  including checkpoint eviction and chapter-anchored Psalm 119:176.
- `reader9-repl`: all nine canonical Neo cases, 91 assertions, including Logo
  text and independently reviewed graphics geometry.
- All 27 offline oracle/graphics unit tests pass.

The built production NKJV binary was restored and compared byte-for-byte with
the passing demo artifact. Notes and persistent bookmarks remain deferred.
