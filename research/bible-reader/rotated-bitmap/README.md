# Rotated bitmap code-size probes

These are compiled research implementations, not enabled or performance-tested
in the applet. Build from betawise with:

```sh
m68k-linux-gnu-gcc -m68000 -msoft-float -msep-data -fomit-frame-pointer -fshort-enums -fno-store-merging -Os -Ios3k -ffunction-sections -fdata-sections -c research/bible-reader/rotated-bitmap/RotatedBitmap.c -o /tmp/RotatedBitmap.o
m68k-linux-gnu-nm -S --size-sort /tmp/RotatedBitmap.o
```

| Routine | Compiled code bytes | Drawing work |
|---|---:|---|
| Extracted current rotation loop | 116 | Packs into caller bitmap |
| Scratch-free rotated pixels | 174 | Background plus one RasterOp per ink pixel |
| Rotated output columns | 202 | One DrawBitmap per source row, nine-byte scratch |

The two-byte DrawBitmap trap is already linked by the reader and cannot rotate
source data itself. A named rotated helper can encapsulate the packing but
still needs scratch or many small LCD updates. Direct controller writes would
need additional alignment, edge masking, roll and shadow-invalidation logic;
these probes do not measure such a driver. The current whole-label bitmap is
99 stack bytes, not embedded ROM data. No production change is made here.

## Direct controller follow-up

DirectRotated.h implements an opaque, inverted clockwise blit through the LCD
ports, without a destination bitmap or per-pixel syscall. It handles partial
pages with the same dummy-read/read-modify-write sequence as the ROM. It accepts
physical coordinates in normal Neo orientation; it does not translate firmware
scroll or mirror settings and is not a general replacement for DrawBitmap.
The test sidebar first clears its full background through RasterOp, then draws
each glyph directly. No production display routine is changed.

The original Neo 3.21 A048 target is 0x4205DE. It checks bounds, adds the firmware
roll byte at 0x48C1, and splits at controller column 132. Left/right helpers are
0x4206F4 and 0x420986. The left helper programs page/column and E0 read-modify-write
mode, reads a dummy byte and real byte (0x42077E), masks/merges and writes.

Ten deterministic MAME font cases passed against the unchanged source/font pixel
oracle: workspace .research-work/bible-compression/rotation-direct-mame. Compared
with eleven-times, median full label draw was 4.485 ms versus 4.445 ms, essentially
a tie. Direct drawing adds 128 net applet bytes (614 versus 486 bytes for the
inlined DrawSidebar function) and reduces its compiler-reported frame from 220
to 140 bytes. It removes the 99-byte bitmap but needs more controller addressing
and read-modify-write traffic. These tests do not establish physical LCD timing
or behavior under nonzero roll/mirrored controllers.
