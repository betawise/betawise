# Gentler Courier oblique research

[Specimen gallery (archived)](../../../font-archive/README.md#useful-pages-after-extraction), [overview (archived)](../../../font-archive/README.md#useful-pages-after-extraction),
[exact manual corrections (archived)](../../../font-archive/README.md#useful-pages-after-extraction), [report (archived)](../../../font-archive/README.md#useful-pages-after-extraction).

Reproduce from the workspace:

```
python3 betawise/research/bible-reader/font-specimens/courier_gentle.py
```

Uses the existing Courier 4/5-line candidates (12pt at 100/75dpi), and the
aligned 8pt/75dpi six-line candidate. Their prior vertical accent repairs are
retained. The experiment restores original horizontal source bearings before
modifying slant, instead of treating previous overhang padding as artwork.

## Horizontal policy

Target removal is half a nominal 12-degree shear, quantized to integer row
translations. It is a design target, not a claim that every hinted stem has
exactly that angle. Glyphs first receive one constant translation if enough.
Otherwise a constrained row-shift search balances target slant against
row-to-row shift continuity. Glyph-specific adjustments retain a common fixed
advance across R/B/O/BO. No vertical coordinates are changed in this experiment.

Two complete draft sets are exported:

| Lines | +1px width | Columns | Remainder | Small corrections | Strict lossless width | Columns/remainder |
|---|---:|---:|---:|---|---:|---|
| 4 | 11 | 24 | 0 | One BO Euro pixel move | 12 | 22 / 0 |
| 5 | 8 | 33 | 0 | One O W serif-tip deletion | 9 | 29 / 3 |
| 6 | 6 | 44 | 0 | Four moves and one deletion in five symbol glyphs | 7 | 37 / 5 |

The +1px symbol edits are explicit, reviewed draft choices, not hidden clipping:
4-line BO Euro; 5-line O W; 6-line B trademark and BO per-mille, trademark,
oe ligature and three-quarters. Source coordinates and every operation appear
in report.json. Moves preserve pixel count but are not whole-row translations;
therefore only the wider, unpatched sets are described as lossless relative to
the experiment's input bitmaps. Full sequences: five moves and two deletions.

The original-width constrained drafts have 12/89/29 glyph-style failures at
4/5/6 lines. Their failed glyphs are displayed with expanded cells in the
specimens; those columns are explicitly NOT finished fixed-width fonts.
Unedited +1px failures also remain in separate source exception cards.

## Checks and export scope

Every successful transformed row is checked as an exact horizontal translation
of its input row. All candidate glyphs retain input ink count; edited drafts
use the disclosed patched input. All four completed faces have exactly the
same advance width. Every completed BDF is parsed back and its 218 glyph pixel
sets and advances checked exactly. Sources are printable CP1252/Western, not a
finished complete Neo-US mapping. BDFs deliberately have 218 native byte slots,
not invented fillers for device/control slots. They are research exports and
are not installed or added to production builds. Font-generation deployment
must still complete the Neo mapping and perform on-device layout acceptance.

Visual assessment of these source-font diagrams is a design review, not an
LCD screenshot test oracle. No emulator/session data is modified.

## Renderer evidence

Existing ROM disassemblies in workspace
`.research-work/neo-font-rom-compare/glyph-draw-new.dis` and
`glyph-measure-new.dis` establish the width coupling:

* 421B46–421B5E selects width_table[byte] or descriptor max_width into D7.
* 421B7A–421B90 passes that width to RasterOp at 420C20.
* 421BAA–421BC0 passes that width to DrawBitmap at 4205DE.
* 42BEE8–42BF04 returns the same selected width from glyph measurement.

The source packing is column bytes within eight-row bands (bit zero at top),
with the next band after width bytes. There is no independent advance/bearing
field that allows drawing extra columns while advancing less. Extra serialized
bytes would not grant legitimate overhang; they would alter band addressing
or the next glyph's data.

## Lucida Typewriter

Installed ISO10646 X11 Lucida Typewriter source inventories at both 75 and
100dpi contain only medium-r and bold-r. There are no native oblique or
bold-oblique faces to substitute. The reference chart displays actual R/B
strikes at 12pt100dpi, 12pt75dpi and 8pt75dpi, all checked for the 218 Western
characters. Commercial Lucida outline families with oblique are separate
products, not evidence of a freely redistributable bitmap style quartet.

Adobe/DEC notices remain in ../build/FONT-LICENSE.txt. Lucida specimens do not
constitute a redistribution licence grant.
