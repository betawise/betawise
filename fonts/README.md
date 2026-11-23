# BetaWise Fonts

This is a monospaced font to allow a readable 44x8 terminal on the AlphaSmart Neo.
It is provided as a standard Neo Font so that it may also be used in AlphaWord.

The font is intended to replicate, as much as possible, the font used on the
AlphaSmart 3000, which was driven by an ST7066 or similar LCD controller.

## Console font sizes

The selected faces are X11 Misc Fixed 4×6 (`glyphs-4x6.bdf`), X11 Misc Fixed
5×7 (`glyphs-5x7.bdf`), and the original Terminal 6×8 (`glyphs.bdf`).
With full cells on the Neo's 264×64 LCD, they fit 66×10, 52×9, and 44×8
characters respectively. `make` builds all three applets.

| File | Face |
| --- | --- |
| `BetaWiseTerminal.OS3KApp` | Original Terminal 6×8 |
| `BetaWiseTerminal-Small.OS3KApp` | Small 5×7 |
| `BetaWiseTerminal-Tiny.OS3KApp` | Tiny 4×6 |

Install one font at a time. The variants share applet ID `0xA1F0`.

## Editable sources and conversion

The build now uses `glyphs.bdf`, `glyphs-5x7.bdf`, and `glyphs-4x6.bdf`.
Each BDF preserves all 256 original PNG slots, including control-slot artwork,
cell dimensions, and blank rows. The PNGs in
[`tests/fonts/fixtures/`](../tests/fonts/fixtures/) remain independent reference
inputs for the local reader and equivalence checks. The initial BDF builds produce byte-for-byte
identical OS3KApp images to the original PNG builds.

`fontgen.py INPUT OUTPUT.h` accepts PNG strips, BDF 2.1, PCF, and gzip-compressed
BDF/PCF. BDF `ENCODING` values must be native byte slots 0–255; Unicode BDFs
must be remapped before conversion. PCF uses Pillow's codec mapping, selectable
with `--pcf-encoding` (default `iso8859-1`). These options do not yet implement
the proposed Neo character-set descriptor.

Missing glyphs fail by default. An explicit `--missing-glyph 0x3f` substitutes
the source question-mark slot for missing entries. This is a conversion policy,
not a claim that the source encoding matches Neo's encoding.

Negative left bearings are shifted into the cell; right overhang expands the
advance to preserve ink, as in the Markdown demo. All glyphs share a baseline
and height, retaining declared BDF ascent/descent and any larger glyph bounds.
Uniform-width inputs emit the existing fixed tables. Variable-width inputs emit
width, offset, and bitmap tables consumed by the font applet.

Run offline format, pixel, packing, and failure-policy checks with:

```sh
python3 -m unittest discover -s tests/fonts -p test_fontgen.py -v
```

PCF round-trip checks use `bdftopcf` when installed. No screenshots or model
inference are used for verification.
