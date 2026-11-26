# Courier: bottom-three-row step trial

[Three-way comparisons (archived)](../../../font-archive/README.md#useful-pages-after-extraction), [all sizes (archived)](../../../font-archive/README.md#useful-pages-after-extraction),
[every extra edge trim (archived)](../../../font-archive/README.md#useful-pages-after-extraction), [exact report (archived)](../../../font-archive/README.md#useful-pages-after-extraction).

Reproduce from the workspace:

```
python3 betawise/research/bible-reader/font-specimens/courier_step.py
```

This trial implements the user's exact two-band rule, without slope/phase
optimization. Relative to the shared baseline y=0, normal body rows -3, -2,
-1 stay aligned. Descenders y>=0 remain with that lower band. All rows y<=-4
shift right one pixel. The threshold is baseline-relative for every glyph,
not independently anchored to each glyph's bottom or bounding box. A constant
horizontal placement per glyph fits its existing fixed cell where possible.
R/B and the prior explicit upright symbol patches are retained.

Widths remain 12/11/8/6px for 3/4/5/6 lines: 22/24/33/44 columns, no unused
pixels. The previous combined reader-candidates set remains unchanged.

## Explicit extra edge corrections

Some glyphs cannot fit the exact two-band rule in these cells losslessly.
The experimental correction chooses a constant glyph placement minimizing
out-of-cell ink, then records every removed edge pixel. This is disclosed
clipping of draft artwork at generation time, not a renderer workaround or
an assertion that these corrections are accepted for production.

| Lines | Glyph/style cases | Extra edge pixels removed |
|---|---:|---:|
| 3 | 2 | 2 |
| 4 | 0 | 0 |
| 5 | 12 | 12 |
| 6 | 8 | 12 |

Three-line BI Ø/ø each lose their bottom diagonal tip. Five-line cases are I
fractions ¼/½/¾ and BI H/M/N/X/Ñ/Ø plus those fractions: one top edge pixel each.
Six-line cases are I per-mille/Œ/œ/¼/¾ and BI Œ/œ/ž, with one or two pixels each.
All source-coordinate locations and glyph placements are recorded in report.json.
The audit card shows the upright input, exact expanded step, and trimmed result.
These variants must not be described as fully lossless.

## Checks and specimens

All sixteen BDF faces (218 printable Western slots each) are parsed back and
checked for exact pixel positions and advances: 3,488 glyph round trips. The
step transform has exactly two bands; constant horizontal placement is allowed,
and only recorded edge removals can change its pixel set. Vertical positions
and fixed widths are retained. No synthetic grayscale, antialiasing or dithering
is generated. Four-times specimens use nearest-neighbour enlargement. Native
PNGs are exactly 264×65 pixels, but a viewer's zoom and display density can still
change their apparent size and contrast. These are source-font design diagrams,
not Neo screenshots or an automated model-based test oracle.

Full Neo device/control mapping and native-editor acceptance remain outside this
research export. The source Adobe/DEC notice is retained in the adjacent
reader-candidates/FONT-LICENSE.txt. Previous combined candidates remain available
for visual selection rather than being silently replaced by this experiment.
