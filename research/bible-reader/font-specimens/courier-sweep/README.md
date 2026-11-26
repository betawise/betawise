# Courier exhaustive one-pixel inflection sweep

[Offline choice picker (archived)](../../../font-archive/README.md#useful-pages-after-extraction), [all static image cards (archived)](../../../font-archive/README.md#useful-pages-after-extraction),
[five-line a/W example (archived)](../../../font-archive/README.md#useful-pages-after-extraction), [source data (archived)](../../../font-archive/README.md#useful-pages-after-extraction),
[scope and exact checks (archived)](../../../font-archive/README.md#useful-pages-after-extraction).

Reproduce from the workspace:

```
python3 betawise/research/bible-reader/font-specimens/courier_sweep.py
```

The picker template is `../courier_sweep_picker.html`; the generated HTML embeds
its data and needs no server or network. Every available printable Western glyph
is presented upright, as the native O/BO reference, and at every possible
one-pixel step location. There are 218 glyphs × two upright bases × four sizes:
1,744 upright samples, 1,744 native oblique references, and 24,852 step candidates.
All 28,340 previews preserve their input pixel count and row shapes exactly.

## Meaning of the choices

Widths are the native source advance plus one pixel: 12/11/8/6px at 3/4/5/6
lines. These are common widths for all four faces, yielding 22/24/33/44 columns
with no remainder across 264 pixels. The R row supplies possible oblique designs;
the B row supplies possible bold-oblique designs.

T is the boundary counted from the font-cell top, between rows T-1 and T.
Every row above it moves right one pixel, every row below remains aligned.
b = baseline - T, the body-row count below the boundary. Thus b=4 is the
bottom-four-body-rows-aligned proposal; a negative b locates the cut below the
baseline in descenders. All boundaries are included, even where blank rows mean
the same visual result. No phase heuristic or best-option score preselects them.

Each candidate may receive one constant horizontal glyph translation to fit
its cell; if impossible, placement minimizes the number of out-of-cell pixels.
Those pixels remain visible in red. No hidden cropping, serif deletion, bridge
addition or previously hand-tuned horizontal patch is applied. The original
selected source includes earlier documented vertical extended-glyph repairs.

Native O/BO references show the original more-slanted artwork with the same
cell-width bounds. This makes it possible to decide whether preserving more
native slant and removing one red serif-tip pixel is better than synthesizing
a gentler step. Red pixels are not necessarily serifs or necessarily on the
right: an individual choice still requires review.

## Recording choices

Select line count and byte block, or search for an exact character / hex byte.
Click any candidate, including upright or native oblique. Choices are stored
in browser local storage where file-origin policy permits it. Download the
selection JSON to preserve/transfer them; it includes glyph, base style,
source style, chosen boundary, placement and the exact proposed overhang pixels.
The preview checkbox hides red ink only for visual comparison. It is recorded
as a preview state, not authorization to silently delete those pixels.
The JSON can be imported to resume selection. R/B choices are independent.

The static gallery has 56 PNG pages, grouped by hexadecimal byte block and line
count. Every source pixel is shown at exactly 4x nearest-neighbour enlargement.
The picker allows 4x/6x/8x. Viewer/page zoom can still change apparent rendering;
there is no generated gray or dithering in glyphs.

## Scope, checks and model references

The source repertoire is 218 printable CP1252-position glyphs, not every Neo
control/device slot. No invented glyphs fill missing mapping positions. Python
checks every candidate's exact ink count and each translated source row. A
separate Node VM check exercised generated JS parsing, all 28,340 pixel counts,
block/glyph filters and step/native selection persistence. That check used
DOM/canvas stubs, not a full browser visual test. Static source cards were also
reviewed for labels, pixel bounds and visible red overhang. No Neo LCD screenshot
or model inference acts as a Neo test oracle.

The installed Courier inventory has Adobe only, with R/O styles (and weights),
not a separately labelled gentler oblique; no alternate gentler Courier bitmap
has been established by the current search. This is not proof that none exists.
The optional `ttyp0-reference.png` shows the author's native 16/18px upright and
italic bitmap drawings at original pen advances/bearings. It is a different
monospace design with native R/B/I at those sizes and no supplied BI, therefore
a drawing reference, not an eligible complete reader-family replacement.

No production candidate or installed applet is replaced. Adobe/DEC notices are
preserved in FONT-LICENSE.txt. The source data and choices are research artifacts.
