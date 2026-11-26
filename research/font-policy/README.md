# Native-bitmap policy evaluation

This is the historical strict preview. The applied recipe now lives in
[research/fonts](../fonts/README.md), including six-line accent translation.
The prior research and editable font snapshot are described in
[the archive index](../font-archive/README.md).

Reproduce the stock BDF candidates from the repository root:

```
python3 research/fonts/native.py
python3 research/font-policy/audit_current.py
```

Run `make -C research/fonts policy` to generate current audit reports and cards
under `research/font-policy/build/`. Native BDFs and the selection report are
written to `research/fonts/build/native-preview/`.
[Selection results (generated on demand)](../fonts/README.md#generated-research-output), [current six-line edits (generated on demand)](../fonts/README.md#generated-research-output),
and [comparison gallery (generated on demand)](../fonts/README.md#generated-research-output) preserve the evaluation. The gallery's left
side is the current edited font; right is the policy preview. Source font images
are deterministic specimens, not emulator screenshots.

## Interpretation

* CP1252's 218 printable slots determine size. Missing/oversized Neo-only glyphs
  do not shrink the font and remain explicitly missing. Fitting extras are added.
* Four means four distinct CP1252 byte slots across all styles, not four
  individual style/glyph cells. Only a one-pixel excess beyond one edge is allowed.
* Mono uses the native upright advance plus one column in every style. Upright
  negative bearings are normalized into the cell, as in the standard converter.
  Italic and bold italic use native placement and may lose substantial ink at
  either horizontal edge; those losses are recorded separately. No slant changes
  or serif/accent repairs are performed.
* All styles share a baseline. Pitches remain 21/16/13/11 rows at 3/4/5/6 lines.
  Six lines at pitch 11 have only ten usable ink rows: the final logical row
  beyond the 65-pixel display must remain blank.
* Keyboard-entered characters receive priority over a larger strike that would
  clip them. This includes direct ROM outputs and dead-key composition results.
  Thus the preferred 3-line Serif/Mono choices stay at 17px. The less conservative
  20px Serif alternative would trim Å and remove its one-row underscore; 20px
  Mono has an upright Euro-width exception. These are keyboard-entered glyphs.
* Terminal Medium is excluded entirely. The stock 5×7 and 4×6 Fixed sources keep
  the established Small/Tiny column and line counts. No custom Terminal glyphs
  have been overwritten by this preview.

## Preferred selections under these assumptions

| Lines | Serif | Sans | Book | Mono |
|---:|---|---|---|---|
| 3 | 17px / 100 dpi | 17px / 100 dpi | 17px / 100 dpi | 17px / 100 dpi |
| 4 | 12px / 75 dpi | 12px / 75 dpi | 12px / 75 dpi | 14px / 100 dpi |
| 5 | 11px / 100 dpi | 11px / 100 dpi | 11px / 100 dpi | 11px / 100 dpi |
| 6 | 8px / 75 dpi | unavailable | unavailable | unavailable |

These preferred available choices have no ordinary CP1252 clipping. Mono has
separately listed italic horizontal clipping: 91 style/glyph cells at three
lines, 38 at four and 38 at five, including Neo-only entries when present.

The closest unavailable six-line native strikes are all 8px / 75 dpi:

* **Sans:** 24 distinct CP1252 slots need one-pixel clipping at the closest
  placement, including many keyboard-entered accented capitals.
* **Book:** 5 slots: 88/8A/8E/9A/9E, i.e. modifier circumflex and Š/Ž/š/ž.
* **Mono:** 6 slots: 60/88/8A/8E/98/99, i.e. grave, modifier circumflex, Š/Ž,
  small tilde and trademark. This includes the regular/bold horizontal allowance;
  italic horizontal clipping remains a separate exception.

There is no smaller installed native Adobe strike for those families. Applying
the strict rule therefore requires omitting these sizes, choosing another source
family, or retaining the existing edited six-line fonts as explicit exceptions.
No omission or relaxation has been silently applied.

## How the current six-line fonts were obtained

Earlier work chose native ASCII sizes and permitted local extended-glyph
repairs. The six-line set retained those repairs when the larger sizes were
subsequently switched to unchanged full-Western strikes. It also included
explicit cedilla/body alignment, Mono m/a repairs and horizontal overhang work.

An independent CP1252 source read confirms these current per-style differences
from the original 8px/75dpi glyph pixels:

| Family | Regular | Bold | Italic | Bold italic |
|---|---:|---:|---:|---:|
| Serif | 2 | 0 | 0 | 1 |
| Sans | 26 | 26 | 27 | 26 |
| Book | 0 | 3 | 1 | 7 |
| Mono | 4 | 6 | 11 | 14 |

Different glyph counts are not clipping counts: edits include added pixels,
translations and redrawing. Larger current Mono faces also have variable cell
widths for overhang; the new advance-plus-one policy is a different constraint.
The audit verifies that the ordinary Pillow CP1252 reader and explicit Unicode
remapping agree pixel-for-pixel, ruling out a remapping bug in this comparison.

## Keyboard priority

The Neo ROM character table, including dead-key descriptor results, establishes
what can be entered directly. The printable Neo-only outputs are:

| Slot | Glyph | Key |
|---|---|---|
| 08 | dot above | Option-H |
| 11 | ⅓ | Ctrl-Option-3 |
| 1C | ∞ | Option-5 |
| 1D | Ω | Option-Z |
| 1F | Σ | Option-W |
| 8F | Π | Option-P |

Tab and Return retain their control meanings. The four physical arrow keys have
zero character-table entries; they do not type the arrow glyphs. Some source
families lack the keyboard-entered Neo-only symbols; the selection report lists
those omissions rather than inventing replacement artwork.

A stock-source limitation also survives this rule: Fixed 5×7 already omits many
capital accents in its original artwork. Those glyphs have valid Unicode slots
but can look identical to plain capitals. This is not conversion clipping, and
a simple geometric fit rule cannot detect or repair it.
