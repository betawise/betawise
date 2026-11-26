# Native bitmap generation

`build_fonts.py` rebuilds all reader BDFs and Terminal Small/Tiny from original
Unicode X11 bitmap files, using `os3k/charsets/neo-us.txt`. Terminal Medium is the
AS3000 exception and is copied unchanged. No old edited reader BDF is an input.

From the repository root:

```
git submodule update --init fonts/upstream/75dpi fonts/upstream/100dpi fonts/upstream/misc
make -C fonts bdfs
make -C fonts -j4
make -C research/fonts review
```

The default inputs are the pinned X.Org source submodules in `fonts/upstream/`.
They retain their original COPYING notices. Distributed generated fonts still
include the consolidated `fonts/LICENSE.md`; source submodules do not replace
the notices accompanying font binaries.

The Makefile runs `build_fonts.py` once per changed input set; every BDF and the
report go under `fonts/build/bdf/`. There is no source-tree `--apply` mode. Use
`--x11-root PATH` for another source tree: `75dpi/`, `100dpi/`, `misc/` containing
original Unicode BDF/PCF files (optionally gzip compressed). Debian packages
`xfonts-75dpi`, `xfonts-100dpi`, `xfonts-base` supply these. The research archive
also preserves the original inputs. `--charset`, `--output` and
`--terminal-medium` can override other inputs.

Selection uses the largest native pixel strike whose CP1252 repertoire fits.
At most four distinct CP1252 slots across styles may lose one pixel on one edge.
Keyboard characters get priority when choosing placement within a strike, but
a single permitted exception does not force a smaller strike. Neo-only extras
are included when available and fitting; absent slots use explicit question-mark
fallback in the applet converter.

Six-line families deliberately retain their previously selected 8px strikes.
Only upper accents overflowing by one row may move down one row. Unicode NFD
identifies the base; a blank row separates the accent when possible. A moved tip
may merge into an existing body pixel, but cannot add ink to the body silhouette.
Letter bodies and descenders are never rescaled. One explicit exception copies
six-line Mono Regular m from Bold m, as requested; no other body is redrawn. Standalone upper
marks may move as a whole. All modifications are recorded.

Mono tries the native advance and advance+1, choosing the extra column only
when it reduces clipping. All glyphs and styles share one cell width. Upright
negative bearings are normalized; obliques retain native coordinates and may
clip horizontally because the Neo cannot overlap cells. Vertical limits still
apply. No real CP1252 glyph may be erased entirely.

`generation-report.json` lists source files, sizes, widths, accent moves,
missing characters and clipped pixel coordinates. Coordinates are baseline
relative, after horizontal bearing normalization. It is a recipe report, not a
hash manifest. `keyboard-characters.json` records the ROM keyboard audit used
for placement priorities; arrow keys do not insert printable arrow characters.

Earlier edited sources, glyph concerns and experiments remain in
[the research archive](../font-archive/README.md). Current review pages load the
build-generated BDFs. [Review tools](review-tools.md) live here; their HTML and
host rasterizer build are generated under ignored `build/` directories.

[Native editor bearings investigation](native-bearings.md) traces the internal
painter, width arithmetic, text tokens and hardware breakpoint feasibility.

[Small-cap encoding and native strike audit](smallcaps/README.md) recovers the
agreed three-style table and compares original smaller strikes with current BDF
x-heights. Reproduce with `python3 research/fonts/smallcaps_sources.py`.

The source recipe also emits sixteen `private/*SmallCaps.bdf` files. For 3/4/5
lines these use smaller native Adobe strikes at body x-height or +1; six-line
faces use the accepted uppercase fallback. All share the three-style encoding
and selected unscaled same-family superior digits, with the TI-83/84 small 3×5
design as fallback. `build_private_fonts.py` can regenerate
those from the current body BDFs and render their specimen separately.

## Generated research output

Font generation/comparison reports, cards and galleries are local build products. From the repository
root, run `make -C research/fonts` with one of these targets:

| Target | Output |
|---|---|
| `review`, `vector-review` | `research/fonts/build/*review.html` |
| `specimens` | `research/fonts/build/specimens/` |
| `smallcaps`, `charset-card`, `private-specimens` | `research/fonts/build/smallcaps/` |
| `italic-spacing` | `research/fonts/build/italic-spacing/` |
| `alternatives`, `lucida` | `research/fonts/build/smallcaps/` |
| `policy` | `research/font-policy/build/` |

Tools generate required BDFs and reports on demand. The alternatives/Lucida and
strict policy studies additionally use the locally installed X11 bitmap fonts.
Tests derive the encoding view from the shared charset and create their BDF
fixtures when needed. `clean` removes research output without removing inputs.
Raw firmware traces and reviewed source/configuration inputs remain committed.
Historical `font-specimens` scripts and their inputs are archive-only; extract
the archive before rerunning those experiments.


`superscript-3x5.json` is the common TI-83/84 small numeral design, retaining a
four-pixel advance and a blank fourth column. Font fallbacks and BibleWise's
ROM-bank generator consume it directly. `import_ti_digits.py /path/to/sdk.pdf`
reproduces it from TI's developer guide, Appendix B, PDF page 181. The importer
checks pixel-grid interiors and orientation against the rendered PDF; builds
need only the checked-in JSON, with no PDF library or network access.
`superscript_samples.py` renders shared/selected cards; `superscript_strikes.py`
audits complete sets and smaller-strike alternatives. Both keep generated
outputs below `build/`.


## Published documentation specimens

`make -C research/fonts documentation` builds the font applets, reads their ELF
load segments and symbol tables to locate descriptors in `.OS3KApp` bytes, and
validates all 21,248 glyphs against the source BDFs before rendering. It publishes
compact Regular cards for all 19 applets, plus four-style cards for the reader
families, in `fonts/specimens/` for the online README. Only these documentation
assets are kept outside `build/`; the verification report stays generated.
The tool uses Pillow and the existing cross-toolchain, with no emulator or
model inference. It preserves advances, cell heights and 264-pixel line bounds.
