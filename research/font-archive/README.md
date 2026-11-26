# Bitmap-font research archive

The snapshot `bitmap-research-before-native-policy.tar.xz` preserves the edited
fonts and review tools before the simple native-bitmap selection policy. Extract
it into an empty directory to inspect the old pages and editable BDFs. There is
no new hash manifest.

Byte-identical generated comparison images, BDF copies, galleries and reports
are kept only in this archive, rather than duplicated in the source tree.
Historical source scripts and their template/encoding inputs are archive-only
as well. Research notes and submitted review inputs remain live; current font
generators and review tools are in `research/fonts/`.
Extract the archive into an empty directory to browse the historical output;
restore its `font-specimens/` files to the matching research directory if
rerunning an old script requires its generated inputs.

The archive contains:

* `betawise/fonts/`: the 67 edited BDFs, converter, font applet and build files,
  the glyph picker, vector candidate generator, HTML/JavaScript and the populated
  offline review pages. Generated object files and applet binaries are omitted.
* `betawise/research/bible-reader/font-specimens/`: experiment scripts, reports,
  HTML indexes and their comparison cards. Reports needed by the historical
  scripts are retained as they were; their earlier hashes are not a new archive
  requirement.
* `betawise/tests/fonts/` and `betawise/os3k/charsets/`: format/profile fixtures,
  checks and the reviewed Neo-US character identities.
* `external/`: native Adobe PCFs, Misc Fixed PCFs, the u8g2 BDF references and
  license/readme material, original ttyp0 distribution, and Dylex reference BDFs.
  Commercial vector font binaries are not copied; source paths and versions are
  recorded in `vector-sources.json` and `vector-source-inventory.json`. The
  populated vector HTML already embeds the compared bitmap results.

## Questions researched

* Native sizes at 75/100 dpi, complete ASCII versus complete CP1252 envelopes,
  accents, baselines, cedillas, descenders and the 65-pixel screen boundary.
* Reader candidates at 3/4/5/6 lines; earlier 7-line and larger comparisons;
  native full-repertoire fits versus larger strikes with local accent edits.
* Courier oblique overhang: reduced slant, per-row shift sweeps, serif trimming,
  extra cell width and local repairs. Six-line m was replaced from bold; oblique
  a and its accented forms gained a bottom pixel.
* Small-cap/superscript encoding, editor-reserved slots and available source
  letters. This is exploratory and separate from the ordinary fonts.
* Existing vendor/community font inventory, u8g2/Fixed/ttyp0/Lucida alternatives,
  and the distinction between body-reading and dense-terminal fonts.
* Full Neo-US identity review, vendor source-font comparisons and keyboard uses
  of dot-above/return/grave. Firmware control semantics remain separate.
* Manual flagged glyphs: Book ª; Mono C/G/Ç; Serif Ξ/c/ç; Terminal Small Ń and
  missing capital accents. Serif Regular c/ç widening was accepted. Mono bowl
  widening remained a proposal, particularly because C/G/O/Q share a width.
* Hinted vector comparisons using native instructions and auto-hinting, with
  fixed cells and baselines. The Wine installation supplied Arial, Times New
  Roman, Verdana and Georgia, and only Courier New Italic. Helvetica and Century
  Schoolbook outlines were not found.

## Useful pages after extraction

* `betawise/fonts/glyph-review.html`: all edited source glyphs and human flags.
* `betawise/fonts/vector-review.html`: populated vector-source candidate picker.
* `font-specimens/glyph-fixes-review/reader-source-comparison.png` and
  `terminal-small-source-comparison.png`: flagged glyphs versus original sources.
* `font-specimens/glyph-fixes-review/wider-bowl-proposals.png`: C/G/Ç and c/ç drafts.
* `font-specimens/charset-review/`: Neo-US correspondence and vendor audits.
* `font-specimens/courier-sweep/`, `courier-stock/`, `courier-stock-fit/`,
  `courier-six-touches/`: Courier investigations and their HTML tools.
* `font-specimens/native-fit-comparison/`: original native-size alternatives.

Here `font-specimens/` means the directory under
`betawise/research/bible-reader/`. For regeneration, the scripts normally run in
the original AlphaSmart workspace: its Ghidra firmware resources and research
external paths are documented in each script. Debian X11 font packages can also
supply the standard PCFs; retained copies are under `external/X11/`. The vector
page generator needs FreeType development files and its configured local fonts.

## Original sources and design references

* X.Org bitmap fonts: https://www.x.org/releases/individual/font/
* Misc Fixed provenance: https://www.cl.cam.ac.uk/~mgk25/ucs-fonts.html
* u8g2: https://github.com/olikraus/u8g2/wiki/fntlistall
* ttyp0: https://people.mpi-inf.mpg.de/~uwe/misc/uw-ttyp0/
* Dylex: https://github.com/dylex/fonts
* FreeType monochrome hinting: https://freetype.org/freetype2/docs/reference/ft2-glyph_retrieval.html
* Typeface spacing groups: https://glyphsapp.com/learn/spacing
* Verdana design: https://learn.microsoft.com/en-us/typography/font-list/verdana
* Georgia design: https://learn.microsoft.com/en-us/typography/font-list/georgia
