# Native editor glyph bearings: Neo 3.21

The native editor can in principle keep measuring ordinary advances while a
replacement internal glyph painter supplies negative bearings. There is no
font-descriptor or text-token mechanism that does this by itself. The plausible
hardware interception point is a single execution breakpoint on the internal
painter. This is a traced design, **not an installed or hardware-validated hook**.

## Actual ROM path

All addresses are for the inventoried original Neo 3.21 image; do not use them
on another ROM without resolving the corresponding routines again.

| Routine | Behaviour |
|---|---|
| `0x42A0F8` | Native editor repaint: scans tokens, selects font, paints and advances |
| `0x421A82` | Internal single-glyph painter; no callback/function pointer |
| `0x42BECE` | Width/height measurement helper, also used by layout and scanning |
| `0x4205DE` | Bitmap rectangle writer, normal glyphs |
| `0x420C20` | Raster rectangle operation, selected glyphs and clearing |
| `0x4206F4` / `0x420986` | Left/right controller bitmap column loops |
| `0x420D82` / `0x421290` | Left/right controller raster column loops |
| `0x42C120` / `0x42C2A4` | Forward/reverse text scanner and coordinate updates |
| `0x42B5D0` | Layout/reflow; uses the same width helper |

For ordinary characters, repaint calls the painter at **0x42A40C**, then the
width helper at **0x42A422**, then `ADD.W D0,D7` at **0x42A42C**. Other branches
(tab marks, hyphen at wrap, control marks, escaped literal) call the same painter.
These are direct absolute JSRs, not A-line syscalls or an indirect RAM callback.
Changing the public PutChar/DrawBitmap syscall dispatch misses them. Replacing
DrawBitmap's underlying ROM implementation would catch normal drawing, but
selection uses the raster implementation, and that lower layer no longer knows
the character code or its intended advance. The glyph painter is the better site.

The painter reads:

* font+0: unsigned byte height;
* font+1 or `width_table[character]`: unsigned byte drawing width;
* `offset_table[character]`: unsigned 16-bit bitmap offset, or character times
  font+2 when the table is absent;
* font+12: bitmap base pointer.

It passes exactly that width to the rectangle writer. Measurement reads the
same width byte independently. The pointer to an offset table does not encode
a bearing; changing an offset only changes which source bytes are read.
The reserved alignment byte at font+3 is not consulted on these paths.

The painter also updates the ROM cursor font/position/busy state, and handles
an already visible cursor. A replacement must retain those behaviours, rather
than treating it as a pure bitmap blit.

Instruction evidence: [editor](native-bearing-evidence/editor-paint.asm),
[painter](native-bearing-evidence/glyph-paint.asm),
[measurement/tab](native-bearing-evidence/width-tab.asm).
The text/decompilation files alongside them include the scanners, layout and
controller loops. Some Ghidra function bodies miss jump-table instructions;
the linear disassembly preserves the actual call sites quoted above.

## Width and wraparound tricks

Width bytes are zero-extended, so `0xFD` means **253**, not -3. Both fixed width
and proportional width paths do this. The painter zero-extends the width again
before calling the rectangle writer. A zero width has zero column iterations;
it does not expose the rest of a bitmap or a 256-column underflow.

The rectangle entry points zero-extend x, y, width and height and require
`x + width <= 264` and `y + height <= 66` using wider arithmetic. Thus negative
x encoded as 65533 is rejected rather than wrapping to the left edge. The
controller column loops do not draw columns outside the passed width.

Coordinates themselves use 16-bit additions: a deliberately invalid scanner
state can wrap 65530+10 to 4, or 32760+10 to 32770. This is **not** a negative
advance available at an ordinary on-screen position. Legal widths are 0–255;
normal layout wraps text around the editor's width. Accumulating tens of
thousands of pixels in malformed state does not paint a useful overhanging
character: its intermediate rectangles are off-screen/rejected.

There is no measured/drawn width discrepancy to exploit in the inspected paths.

## File control records and invisible advance

The classification table at `0x44C7E0` is included in
[native-bearing-evidence/references.txt](native-bearing-evidence/references.txt).

| Mechanism | Advance and drawing |
|---|---|
| Ordinary space or custom blank glyph | Positive width, blank cell; normal copy can clear existing pixels there |
| Tab `09` | Forward to the next tab stop, based on five M widths; rectangle fill between positions |
| Hidden region `B1 01 B1` … `B2 01 B2` | Renderer skips the content; scanner suppresses both x and y updates, so no reserved width |
| Protected region bit 02 | Does not make glyphs invisible or change advance |
| Bold/italic region bits 04/08 | Select descriptor; its ordinary nonnegative width is used |
| Literal `B0 byte B0` | Draws and advances as that glyph; not a motion escape |
| `B3/B4/B7 payload marker` | Opaque fixed three-byte records; no drawing or advance |
| `B8/B9/BA/BB/BE/BF length … length marker` | Entire framed record skipped, no payload measurement or advance |
| Inline form envelope A8…9D | Separate form/scanner mechanism, not a negative spacing command |
| Cached wrap markers 81/8D/8F/AD | Space/tab/hyphen/line transitions, not arbitrary horizontal motion |

There are old indentation-related arms (classes 0B/0C) in the switch, but **no
byte maps to them** in this ROM's classification table. They are not an
available file encoding. Likewise, backspace `08` and LF `0A` classify as ordinary
glyphs here. No active token means “measure the contained text but don't draw it,”
and no active token supplies a signed pixel displacement.

A deliberately blank glyph with any advance 0–255 can supply a spacer, but
positive spacers cannot recover the three columns added before j. An overlap
needs either a negative displacement or separate drawing and advance widths.

## Hardware hook feasibility

The local `Ghidra/Alphasmart Neo/MC68VZ328UM.pdf`, chapter 16, specifies:

* one 32-bit address comparator, with a mask/control comparator;
* software enable `ICEMCR.SWEN` in normal operation;
* execution-breakpoint insertion of A000 at the matched instruction fetch,
  followed by the A-line/level-7 debugger mechanism;
* address/mask/control registers at FFFFFD00…FFFFFD0E.

Sections 16.1.2–16.1.5 and 16.2.3 distinguish execution and bus breakpoints and
normal operation from external emulation-monitor mapping. Multiple separate
hardware breakpoint addresses require external comparator hardware. This
facility is not implemented in the current `neo_vz_core.h`/M68000-based emulator;
an emulator debugger breakpoint does not prove its real trap behaviour.

One entry breakpoint at `0x421A82` should suffice **in design**:

1. Recognize registered BetaWise descriptors and look up per-glyph bearing,
   drawing width and bitmap; let the native descriptor retain the true advance.
2. Dispatch managed glyphs to resident RAM/flash code, leaving the native editor,
   reflow, caret measurement and file encoding in place.
3. For other fonts, execute the displaced entry instruction in a trampoline and
   resume after it, avoiding a second hit on the entry comparator. Alternatively,
   explicitly manage disable/single-step/re-enable, which is more complicated.
4. Chain unrelated A-line/IRQ7 handling. The injected A000 collides with the
   existing syscall mechanism unless the debugger event is distinguished.
   Exact exception stacking/acknowledgement and resumption remain to be tested
   on real hardware or an accurate ICE implementation.

This need not take over the entire editor display. However, just drawing an
8px-wide j at x-3 using replacement copying would erase portions of the previous
letter with the white background of j. A correct painter must replace the normal
advance cell and merge the overhanging ink separately, or compose the union.
The existing raster operation 7 supports OR for normal black ink. Selected text
uses inverted-source operation 4, so highlights, mixed selection boundaries,
clipping at the editor's left edge, cursor, scrolling and redraw ordering all
need explicit handling and deterministic tests. A renderer must clip/crop a
negative destination before calling the stock rectangle writer, which rejects
negative x rather than doing that clipping itself.

The handler must also survive applet/A5 changes and remain resident for as long
as the breakpoint is enabled. Trapping once per glyph has a runtime cost that
has not been benchmarked. No hardware hook was installed by this investigation.

## Reproduction and validation

`InspectNativeBearings.java` emits the classification table and known xrefs,
and can dump the ROM memory window for objdump. Run with Ghidra headless on the
existing, correctly based Neo 3.21 project, `-noanalysis -readOnly`. Use
`research/syscalls/text/InspectReaderPath.java` with the routine addresses above
for instruction listings and decompilation. The memory dump is an investigation
intermediate, not committed to this evidence folder.

CPU/RAM checks use the actual ROM in disposable MAME flash/RAM:

```
python3 research/fonts/probe_native_bearings.py /tmp/neo-native-bearings
```

The completed run passed **307 assertions in 292 native calls**; the
[results](native-bearing-evidence/cpu-results.json) and
[execution log](native-bearing-evidence/cpu-mame.log) are retained.
They exercise every unsigned width byte, fixed-width extremes, ordinary scanner
advances, deliberate 16-bit coordinate wrap, all individual region flag bits,
opaque record lengths/zero advance, and ordinary low/reserved byte glyphs.
There is no screenshot/model oracle and no saved user session is mutated.
These checks do not certify the proposed hook, compositing or real ICE hardware.
