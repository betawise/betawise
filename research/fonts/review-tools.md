# Font review tools

The HTML pages are generated locally and ignored by Git. Their Python,
JavaScript, templates and outline-source configuration live here in research.
Run `make -C fonts bdfs` before calling a generator directly.

## Glyph review

Run `make -C research/fonts review`, then open `research/fonts/build/glyph-review.html` in a browser.
It embeds every current BDF, works offline, and does not edit the sources.
Click a glyph to flag it; ASCII letters also flag their accented forms in the
same face; Unicode aliases are also grouped. Shift-click toggles only one glyph. Missing artwork is shown separately.
Flags persist in browser storage and can be exported/imported as JSON.

The mapping-review view shows only Neo-specific additions and unresolved native
slots beyond printable CP1252, with source Neo system-font and Terminal bitmaps.
Confirm mappings or suggest a character/U+ value; exports contain proposals only.
The complete CP1252 portion does not need reviewing again.

The Neo-specific import is recorded in
[the import report (archived)](../font-archive/README.md#useful-pages-after-extraction).
It added 466 glyphs across the reader faces while preserving all 14,720 existing
source glyphs exactly. Ten source glyphs did not fit the existing vertical bounds;
these and unavailable source characters remain visibly missing in the review.

## Bitmap versus vector review

Generate the offline comparison picker with:

```
make -C research/fonts vector-review
```

Open `research/fonts/build/vector-review.html`. The current generated page includes
all 67 faces and the 32 glyphs from the latest manual review. To seed a new set
of flags, use `make -C research/fonts vector-review REVIEW_FLAGS=/absolute/path/to/fixes.json`,
or import that JSON in the browser. The original glyph picker also links to this
page. A family-only generation is available through
`python3 research/fonts/vector_review.py --family Mono`.

Select a family, size, style and character. Compare C/G/O/Q or another related
shape group, then click a candidate or **Keep current bitmap**. Hover/focus previews
it in a 264×65 text specimen. Choices and notes persist locally; **Export choices**
writes `betawise-vector-choices.json` for the subsequent font update. Importing
saved choices rejects changed original cells, changed candidates and mismatched
source metadata. Export includes keep-current decisions, exact original and
proposed bitmaps, unchanged dimensions/baseline, notes and source provenance.
The picker itself never writes BDFs or installs applets.

The generator uses FreeType monochrome rasterization with embedded bitmaps
disabled, comparing the source's native hinter against the auto-hinter. It
calibrates nearby sizes against each bitmap face's A and x ink heights, tries
whole- and half-pixel horizontal phases, and allows at most a one-pixel horizontal
translation. The baseline and existing per-glyph advance are fixed. Missing slots
use the existing question-mark fallback's cell width. Every source ink pixel must
fit; overflowing candidates are rejected, never cropped or rescaled. Up to six
different shapes are retained per outline source per cell, deduplicating equivalent
translated renderings within that source. Use the outline-source filter to compare
fonts independently; the candidate budget for one source cannot crowd out another. Nearest metric matches are ordering aids, not legibility scores.
Ink width, pixel count, eight-connected ink parts and four-connected enclosed
counters are shown as diagnostics. Related styles are reviewed independently.

[vector-sources.json](vector-sources.json) selects local outline references:
Liberation Serif/Sans/Mono and TeX Gyre Schola. Terminal uses Liberation Mono as a
reference, not an exact outline counterpart. Optional local Microsoft references add Times New Roman for Serif, Arial/Verdana
for Sans, Georgia for Book, and Courier New for Mono. The installed Wine directory
is read directly; no font installation or downloads are performed. Only Courier
New Italic was found locally. An additional Georgia 2.11 Regular reference lives
in the user font directory. Missing styles are listed explicitly and are never
filled with synthesized styles or another font. Native TrueType instructions were
verified in the added files; bytecode presence alone does not establish manual
hint authorship. No Helvetica or Century Schoolbook outline was found in the
checked installed directories.

Configure additional sources with
`--sources /path/to/config.json`; each family entry supplies Regular/Bold/Italic/
BoldItalic files, provenance and license information. A null file means that style
is unavailable; optional sources can be absent on other machines. `~` in source
directories expands to the current user’s home directory. The fonts are not bundled;
the generator reads installed outlines and embeds the candidate rasters. Exported
choices retain source/license metadata for any subsequent imported artwork.

On Debian the additional dependencies are `build-essential`, `pkg-config`,
`libfreetype-dev`, `fonts-liberation2` and `fonts-texgyre`; Python/Pillow are already
used by the ordinary converter. The tiny host FreeType bridge is built under
`research/fonts/build/vector-review/` and is ignored by Git.

Checks:

```
python3 -m unittest discover -s tests/fonts -p 'test_*.py'
python3 tests/fonts/check_vector_review.py
```

The raster test additionally needs `python3-fonttools` and uses an independently
authored rectangular TrueType fixture to
verify actual FreeType ink/metrics and clipping rejection. The isolated browser
check exercises exact canvas pixels, C/G/O/Q context, 264×65 specimen geometry,
per-style choices, flag navigation, persistence, and atomic JSON import/export.
There is no screen capture or model-based legibility judgement in these checks.
