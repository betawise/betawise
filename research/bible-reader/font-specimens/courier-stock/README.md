# Eight stock Courier oblique cards

[All eight cards (archived)](../../../font-archive/README.md#useful-pages-after-extraction), [source hashes and red-pixel inventory (archived)](../../../font-archive/README.md#useful-pages-after-extraction).

Reproduce from the workspace:

```
python3 betawise/research/bible-reader/font-specimens/courier_stock_cards.py
```

Original PCF O/BO glyphs at the four currently selected strikes: Courier
14pt100dpi at three lines, 12pt100dpi at four, 12pt75dpi at five, 8pt75dpi
at six. Common cell widths remain 12/11/8/6 pixels. Each card uses a 32x8
byte-position grid; all 218 Western printable source glyphs are drawn.
Gray slots do not fabricate a complete Neo device/control mapping.

Unlike the earlier sweep references, these read raw PCF ink before any vertical
accent repairs. Red includes both horizontal overhang and vertical overflow at
the existing shared baseline. Six-line ink budget is ten rows in an eleven-row
cell; its last row is reserved blank. No shear, glyph pixel correction,
resampling or clipping is applied. Constant horizontal placement follows the
same minimum-overhang policy as the sweep. Exact original pen bearings remain
available from the recorded PCF source and are not claimed to be unchanged.

All 1,744 glyphs are checked for exact original row shapes/ink counts after the
single horizontal placement, and every black/red source pixel is asserted to
lie inside its diagnostic panel. All eight PNGs decode successfully. These are
source-font research cards, not Neo LCD screenshots or model-based acceptance
oracles. No production fonts or applets are changed. Adobe/DEC notices are
preserved in FONT-LICENSE.txt.
