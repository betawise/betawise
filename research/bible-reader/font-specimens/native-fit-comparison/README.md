# Current sizes versus native full-repertoire fits

[Gallery (archived)](../../../font-archive/README.md#useful-pages-after-extraction), [manifest (archived)](../../../font-archive/README.md#useful-pages-after-extraction).

Run `python3 betawise/research/bible-reader/font-specimens/compare_native_fit.py`.
Regenerate the selected set first with `reader_candidates.py`.

All four families at 3/4/5/6 lines, all four styles. Left is the current set,
with the baseline/descender changes withdrawn. The independent Schoolbook
one-row umlaut and Helvetica six-line cedilla placement fixes remain.
Right is the largest native Adobe XLFD pixel size fitting the common ink
height of all 218 printable CP1252 characters and all four styles, considering
all installed 75/100dpi strikes. Exported native-side BDFs round-trip every
pixel and advance exactly. No scaling, accent edits or fallback glyphs.
Unavailable cells mean there is no native strike meeting these constraints.
The six-line choice allows 10 ink rows at 11px pitch, fitting the final row
inside 65 pixels. Other budgets are 21/16/13 rows.

The 218-glyph set is not a verified full Neo-US mapping: Neo control/device
symbols are absent from these X11 sources. No full 256-slot coverage claim is
made. Cards are offline bitmap design specimens, not Neo screen captures.
