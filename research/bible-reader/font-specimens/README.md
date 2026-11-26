# Native ASCII X11 font specimens with local extended repairs

Historical generators and their generated inputs/outputs are now archive-only.
See [the archive instructions](../../font-archive/README.md). Extract the
`betawise/research/bible-reader/font-specimens/` tree before running commands
below; the live tree retains research notes and submitted review inputs only.


Century Schoolbook, Helvetica, Times and Courier candidates for 4, 5, 6 and
7 lines on a 264 × 65 display. No eight-line version, production applet change
or installation is performed.

From the workspace root:

```sh
python3 betawise/research/bible-reader/font-specimens/build.py
```

Open `build/index.html`. It links the regular body overview, per-family size
comparisons, small-cap comparisons, labelled small-cap glyph grids and
**before/after grids for every extended-body repair**. `build/report.json`
records the source paths, selections, exact edited code/style pairs, repair
methods, small-cap metrics and validation results. Generated files are ignored.

## Native source selection

Scan all installed X11 `fonts.dir` indexes for these four Adobe families. The
inventory comprises 384 PCFs: four families × four styles × six point sizes ×
two resolutions × two encoding variants. Each Latin-1 file is compared with its
Unicode companion; all shared glyph bitmaps, bearings and advances agree.
`build/strike-inventory.json` contains every file and its measured metrics;
`build/all-native-strikes.png` shows every native strike at both resolutions.

For each family and line count, select the **largest XLFD pixel size whose
complete ASCII repertoire fits across all four styles at a shared baseline**.
This replaces the earlier coverage-first policy. Search 75dpi and 100dpi; a
point number in the filename is not the pixel size or measured ink height.
No smaller body font is selected merely to accommodate an extended character.

Pitches are 16, 13, 11 and 9px. At six lines, ink must fit in ten rows per cell:
the final logical row of the 66-row layout remains blank, so all ink fits in
65 physical rows. Any slack in the ASCII ink envelope is allocated above the
letters to reduce accent repairs while retaining every native ASCII pixel.

No ASCII bitmap is scaled, cropped or redrawn. Widths use the existing Neo
converter's handling of advance and overhang. Exact source-coordinate pixel
sets and normalized widths are compared for every exported ASCII glyph.
Century, Helvetica and Courier have no seven-line native four-style ASCII fit;
those combinations remain unavailable, rather than changing ASCII artwork.

## Extended glyph repairs

The complete Windows-1252 printable glyph repertoire is retained. “Western” in
historical output meant Windows-1252; Latin-1 means ISO-8859-1. These are source
glyph repertoires, not a claim that native editor-control byte meanings change.
Unicode X11 sources supply Š, Œ, Ž and Ÿ directly.

Every extended glyph already fitting the selected baseline window remains
pixel-for-pixel unchanged. Only overflowing extended glyphs enter the repair
path, retaining their original normalized width/advance:

1. Move the accent/upper band down if it fits without merging pixels or changing
   the base-letter region.
2. If necessary, compress only that upper band vertically into the available
   accent space. Preserve all pixels at and below the base-letter top.
3. When there is no room to preserve the base region, vertically fit that
   **individual extended glyph only**, preserving its width and ink-bottom
   relationship to the baseline when possible. No whole-font scaling occurs.

The latter operations use box-filter coverage with a 25% threshold. They are
explicitly recorded candidate edits for human review, not certified manual
hinting. The before/after grids label upper-band shifts, accent fits and isolated
glyph fits. Ring accents, crossed letters and very tight cells need particular
attention. No character is dropped to make coverage fit.

## Small caps and superscripts

`encoding.json` freezes all 61 letters in regular, bold and italic/oblique.
SS for source ß occupies D7/F7 in regular/bold; all three styles contain the
composite. Ÿ uses actual X11 artwork. Superscripts occupy 30–39. All 23 editor
control slots remain blank in the packed auxiliary face.

Small caps retain the earlier candidate-generation method: choose hinted
capitals near the measured x-height, then rescale the small-cap glyphs when
necessary. Accents and tails are fitted separately and recorded. This custom
small-cap work is separate from the body-font ASCII preservation requirement.
These specimens remain candidates for readability review, especially tiny
small caps, distinct diacritics and superscript numerals.

## Exports and verification

Each available family/size exports four body BDFs plus a packed auxiliary BDF,
all editable. No OS3KApp package or applet ID is produced. Assertions require:

- Complete ASCII pixel/width equality with the chosen native source.
- Exact equality for every extended glyph not requiring repair.
- Extended repairs confined to overflowing non-ASCII characters, with widths
  unchanged, complete coverage and all ink within the cell budget.
- All 61 letters in each of three small-cap styles, 183 unique destination slots,
  ten superscripts and no glyphs in the 23 red slots of the auxiliary face.
- Pixel, width and height equality on BDF read-back for every export.
- Every preview page within 264 × 65, with no whole-font scaling.

Duplicate small-cap candidate bitmaps are recorded rather than interpreted as
proof of legibility. Generated font-specimen images are human review diagrams,
not emulator screenshots or automated visual test oracles. Source licensing is
copied alongside the exports as `build/FONT-LICENSE.txt`.

`courier_focus.py` can additionally reproduce the earlier requested native
12px/five-line versus 11px/six-line comparison and its source-specific outlier
analysis. The main gallery now follows the ASCII-first selection above.

## Three-line comparison and Helvetica readability review

The body overview has a comparison-only top row at 21px pitch (three lines,
63 occupied logical rows on the 65-row display). It uses the same largest-native-
ASCII selection rule and does not add a fifth distribution size or BDF set.
`report.json` stores its source and repair metrics under `three_line_comparison`.

`build/helv-6-lines-before-after-context.png` shows the untouched source and
locally adjusted letters in words for all four styles, at identical integer 3×.
Both use a common baseline and padded preview canvas so source overshoots remain
visible. Gray marks the target ink window. The full per-glyph grid remains
available as `helv-6-lines-extended-repairs.png`. These diagrams support human
readability review and are not an automated visual test.

## Full-repertoire native comparison (no repairs)

```sh
python3 betawise/research/bible-reader/font-specimens/full_repertoire_comparison.py
```

`regular-body-full-repertoire-overview.png` repeats the three-to-seven-line
comparison, choosing the largest native strike fitting all 218 printable
Windows-1252 glyphs across all four styles. There is no ASCII fallback, local
extended repair or font rescaling. Accented sample strips show actual headroom.
`full-repertoire-report.json` records exact selections and source-pixel checks.
This is a separate comparison; the preceding ASCII-first specimens are retained.
The Neo's low-byte math/device/control drawings do not yet have a complete
verified Unicode mapping and are explicitly outside this repertoire claim.

## 8px Courier six-line alternative

```sh
python3 betawise/research/bible-reader/font-specimens/courier8_candidate.py
```

This separate candidate edits only the regular Š/Ž carons (move down one pixel
into the original blank gap) and shifts bold, oblique and bold-oblique down one
pixel. All 872 printable source glyphs retain their ink counts and normalized
widths. Every row-10 cell bitmap is empty. Six 11-row cells therefore have a
guaranteed blank logical row at index 65, outside the physical 0–64 screen rows.
The original unshifted common envelope has ink on both extreme rows; it cannot
be assumed to have a universally blank top or bottom edge.

Open `build/courier8-6-lines.html` for a comparison with 11px Courier, all four
faces before/after, and a mixed-face line showing the one-pixel baseline
stagger. Four candidate BDFs are exported and exactly read back. This is a
review alternative, not a change to the main selection policy or a firmware
acceptance test. Its printable Windows-1252 scope has the same Neo-symbol
mapping limitation as the other studies.

## Aligned-baseline six-line native 8px alternatives

```sh
python3 betawise/research/bible-reader/font-specimens/aligned_six_line_candidates.py
```

Open `build/aligned6-index.html`. Courier, Century and Helvetica use native 8px
75dpi artwork in all four faces with baseline row 8, ten ink rows and a blank
row 10. No face is shifted and no glyph is rescaled. Only marks extending to
y=-9 move down one pixel. Letter bodies, descenders and widths stay fixed.
Courier's bold/bold-oblique ASCII grave accents also move down one row.

The source's first blank separator row identifies the accent/body boundary.
The no-gap cases are explicitly limited to Helvetica Å and Century bold-italic
Š/Ž; their moved accent tips share existing body pixels. Assertions require
no additional pixels in the original letter-body region and account for every
shared pixel. These six variants are review candidates, not legibility claims.

The study checks 2,616 source glyphs, exactly round-trips twelve separate BDFs,
and asserts no changes to ordinary letter pixels/positions or descenders and
a guaranteed empty final cell row. `aligned6-report.json` records every code,
face, source path and edit. Before/after context and individual-glyph grids are
linked for each family. These alternatives do not alter the main selection
policy or overwrite the previous staggered candidate.

## Source advances versus normalized Neo cell widths

The exact glyph tests preserve source ink and **normalized cell widths**, not
necessarily the original X11 pen advance. The existing converter allocates
negative bearings and right overhangs within each independent bitmap cell.
That can increase advances and alter the source word spacing, especially in
italic/oblique text. Earlier user-facing claims of unchanged source advances
were too broad. This distinction must remain explicit in font acceptance.

`source_spacing_diagnostic.py` renders Courier m, Helvetica i/j and the word
déjà from actual source bearings/advances versus the current aligned 8px Neo
cells. At oblique weight, déjà advances 14px in the source but 17px after
normalization; bold-oblique advances 17px versus 19px. The PCF already supplies
a one-pixel stem for bold i/j. Oblique and bold-oblique i have identical bitmaps
and metrics at this strike. The native regular Courier m bitmap is also
unmodified in the candidate. These source design choices should be separated
from conversion-induced spacing changes.

## Family-role comparison

`family_roles.py` compares ASCII source glyphs in the ROM system font, original
vendor Small/Medium/Large, BetaWise Terminal and all four X11 families at 12px.
Vendor glyph/width/offset bytes are checked against their original applet
images; historical captures are used only as retained font-resource bytes, not
LCD screenshots or a visual oracle. The chart enlarges native glyph shapes
3× and uses the existing normalized Neo-cell spacing for X11 resources. It is
a family-selection specimen, not a source-advance fidelity claim.

At native 8px Courier, i/j largely retain one-pixel stems even in bold; m/w
occupy five-column advances and four-row letter bodies. These shapes exist in
the PCF sources and are not introduced by the six-line accent repairs.

## Filtered u8g2 substitute evaluation

Run `python3 research/bible-reader/font-specimens/evaluate_substitutes.py`
from the betawise repository. Output: `build/substitutes/index.html`, paired
PNG cards, overview and machine-readable coverage/geometry report.

Sources are the local sparse u8g2 checkout at
`../../.research-work/u8g2-review/upstream` (commit
`8d8be1800732fecaa37c0dd02774396ae18c4ec8`) and the author's original
UW ttyp0 2.1 source tarball extracted alongside it. The script expects those
research downloads; they are not build dependencies of shipped fonts.

Eligibility requires all 218 printable CP1252 characters in every used face,
and native regular/bold/italic or oblique for Adobe-family replacements.
Only Terminal substitutes may be regular-only. This Western coverage check
is not certification of the complete Neo control/device charset. No source
pixels are resized or trimmed; Neo cell bearing normalization may expand
advances. Every normalized glyph is checked against the exact source pixels.

The 17 paired cards put the current Adobe selection/actual Terminal BDF on
the left and the candidate on the right, including all available styles.
The Adobe originals use the main ASCII-first selections and existing local
extended repairs, not the later alternative aligned-eight-pixel specimens.
Three-line samples are comparison-only. Lucida licence clearance remains
outstanding; its inclusion is visual research, not permission to ship.
Fixed and ttyp0 have R/B/I but no combined bold-italic in these sources.

Tiny 4x6 and Small 5x7 Terminal match the corresponding Fixed sources exactly
for all 95 printable ASCII cells. Fixed 5x8 is a narrower Standard alternative;
6x9 and 6x10 change the target height. No qualifying styled six-/seven-line
replacement was found in the evaluated shortlist. ProFont and Spleen are
excluded rather than presented with incomplete or unverified Western coverage.

## Existing community NeoFonts

`inventory_neo_fonts.py` decodes all eleven original applets from the workspace
`Ghidra/Alphasmart Neo/NeoFonts/` directory. See [the inventory](neo-fonts/README.md)
for metrics, 256-slot coverage limits, Atto/Femto’s C3 solid-block defect and
66-row boundary clipping. [The gallery (archived)](../../font-archive/README.md#useful-pages-after-extraction) contains exact
source glyph specimens and per-byte comparisons to the ROM font. Fixed/ttyp0
remain eligible for Terminal replacements without a style quartet requirement.

## Gentler Courier oblique

`courier_gentle.py` compares original normalized cells, constrained gentler
obliques at original width, +1px cells with seven explicit glyph corrections,
and minimum fully lossless widths. See [the experiment](courier-gentle/README.md)
and [specimens (archived)](../../font-archive/README.md#useful-pages-after-extraction). Completed four/five/six-line drafts
use 11/8/6px cells: exactly 24/33/44 columns across 264 pixels. They remain
research exports pending full Neo mapping and acceptance.

## Selected reader set

`reader_candidates.py` assembles Times, Helvetica, Schoolbook and Courier at
3/4/5/6 lines, four styles each. The current decision uses untouched native
full-Western fits for 3/4/5 lines and retains all previously reviewed six-line
faces exactly. Larger repaired strikes and baseline/descender experiments below
are historical, not the current selection.
See [selections and reproduction](reader-candidates/README.md),
[gallery (archived)](../../font-archive/README.md#useful-pages-after-extraction) and [manifest (archived)](../../font-archive/README.md#useful-pages-after-extraction).
AFF0–AFFF are provider reservations, not production installation. Complete
Neo-US control/device mapping remains separate from the 218 Western text glyphs.

## Courier bottom-three-row step

`courier_step.py` trials the exact baseline-anchored bottom-three-straight rule
without widening. See [comparisons and explicit edge trims](courier-step/README.md).
The prior combined candidate set is preserved. Native 264×65 source previews
and nearest-neighbour enlargements are provided; no gray/dither pixels are
generated. This is a design trial, not a production replacement.

## Courier per-glyph inflections

`courier_inflection.py` compares bottom-three, bottom-four and glyph-specific
step obliques without widening. Explicit a/W cut choices and W junction edits
are layered over a deterministic source-stroke continuity heuristic; accented
a forms inherit a’s cut. See [the design trial](courier-inflection/README.md)
and [comparison gallery (archived)](../../font-archive/README.md#useful-pages-after-extraction). The previous combined
reader candidate set is preserved pending visual selection.

## Exhaustive Courier choice cards

`courier_sweep.py` and its picker template produce every one-pixel transition
for all 218 printable Western glyphs, from both R/B bases at all four sizes.
[The offline picker (archived)](../../font-archive/README.md#useful-pages-after-extraction) records per-glyph choices;
[static image cards (archived)](../../font-archive/README.md#useful-pages-after-extraction) show the same sweep plus native
O/BO references. All overhang remains visible in red; no pixels are deleted.
See [scope and usage](courier-sweep/README.md).

## Stock oblique cards

`courier_stock_cards.py` produces [eight complete stock O/BO cards (archived)](../../font-archive/README.md#useful-pages-after-extraction)
for 3/4/5/6 lines. Original PCF ink is retained, with width and vertical-budget
overhang marked red; see [scope](courier-stock/README.md).

## Stock-slant Courier in fixed +1px cells

`courier_stock_fit.py` produces [the stock-slant four-style set (archived)](../../font-archive/README.md#useful-pages-after-extraction)
at 3/4/5/6 lines. Local serif-tip/edge repairs and accent/cedilla translations
replace slant generation; every edit is inventoried with paired source glyphs.
The surprising six-line oblique a is independently verified against upstream
BDF and retained. See [scope and checks](courier-stock-fit/README.md).

## Six-line m and italic a

`courier_stock_fit.py` now applies the user-selected native-bold m to regular
six-line Courier. `courier_six_touches.py` provides [before/after and a alternatives (archived)](../../font-archive/README.md#useful-pages-after-extraction),
plus an actual six-pixel, four-style Dylex 6x10 reference. Stock oblique a is
retained pending choice; alternatives are separate research BDFs.

## Current versus unmodified native fits

Baseline and descender shifts are withdrawn. `compare_native_fit.py` compares
the current 3/4/5/6-line selections against the largest native Adobe strikes
fitting all four styles and 218 Western printable glyphs without any edits.
See the [comparison gallery (archived)](../../font-archive/README.md#useful-pages-after-extraction) and
[scope and reproduction](native-fit-comparison/README.md). This is not a
verified complete Neo-US control/device mapping.
