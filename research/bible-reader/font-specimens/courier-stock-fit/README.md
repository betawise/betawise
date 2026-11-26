# Stock-slant Courier fitted to +1px cells

[All four styles at all sizes (archived)](../../../font-archive/README.md#useful-pages-after-extraction), [combined text overview (archived)](../../../font-archive/README.md#useful-pages-after-extraction),
[original lowercase-a source proof (archived)](../../../font-archive/README.md#useful-pages-after-extraction), [exact edits (archived)](../../../font-archive/README.md#useful-pages-after-extraction).

Reproduce from the workspace:

```
python3 betawise/research/bible-reader/font-specimens/courier_stock_fit.py
```

## Candidate set

Stock R/B/O/BO at 3/4/5/6 lines, widths 12/11/8/6px: 22/24/33/44 columns, no
unused horizontal pixels. Native oblique slant is retained. No inverse shear,
new oblique generation, whole-glyph scaling or raster resampling occurs.

Each size has a complete 32x8 byte-position card with all four styles stacked
inside each slot, a four-style text specimen, native source-page PNGs and four
source/candidate edit audit cards. Blue corners identify glyphs with pixel changes
beyond constant horizontal placement. Source overflow is red in audit cards;
fitted additions are blue. Gray slots are outside the 218 printable Western
source repertoire, not invented Neo device/control glyphs.

## Repairs

Start with the original PCF glyph at the shared baseline. Standalone accents
move vertically if necessary. Top accent bands are isolated at a native gap or
base-letter top and translated downward, retaining the letter body. Cedillas
and other lower mark bands move upward, sometimes sharing a tip with the body.
The fallback discrete mark-row fold is implemented but was not required by this
set; no whole glyph is vertically compressed.

Horizontal placement is selected to retain native counters/components where
possible, then minimize edge removals. Left/right overflow tips are trimmed.
Where trimming would open a closed outline, offending points may fold onto the
nearest edge if this better preserves source topology. Every relocation, removed
pixel and added pixel is recorded; this is not labelled lossless.

The six-line BO oe ligature needs two additional local moves: (1,-3)->(0,-3)
and (1,-2)->(0,-2), after placement. They restore its left o counter following
edge trimming. The original o counter had two diagonally split white pockets;
the fitted o has one continuous counter and the e counter remains. This explains
the one remaining graph-topology difference; it is explicitly recorded, not an
unresolved overflow. Final glyph semantics/readability still require user review.

## Lowercase a verification

Six-line native Courier O 0x61 is really a four-row, nine-pixel design:

```
.##.
..##
###.
#.#.
```

The installed Unicode PCF and ISO8859-1 PCF agree. It was independently matched
against NetBSD's original font-adobe-75dpi courO08.bdf, cached in workspace
`.research-work/u8g2-review/courO08-upstream.bdf`. Source URL:
https://raw.githubusercontent.com/NetBSD/xsrc/trunk/external/mit/font-adobe-75dpi/dist/courO08.bdf

Its SHA-256 and exact source-row evidence for all four sizes/styles are retained
in report.json. The unfamiliar a is not a lower-row cropping bug and is kept in
this stock-slant trial; no silent ASCII redesign is introduced.

## Checks and scope

All sixteen BDF faces are parsed back: 3,488 exact glyph pixel/advance round
trips. Every glyph fits its common width and ink budget; all six-line cells end
in a blank row. The four complete glyph cards and all source/candidate audits
retain original baseline placement. These are deterministic source-font research
specimens, not Neo LCD captures or a model-based test oracle. Pixel geometry
checks do not establish physical LCD readability or native-editor acceptance.

The BDFs contain 218 printable Western native-byte slots; completing Neo-US
device/control mapping remains separate. Existing combined candidates and
production applets are not replaced. Adobe/DEC notices are in FONT-LICENSE.txt.

## User-selected six-line m

Regular 6D now copies native bold m exactly, yielding separate stems at columns
0/2/4 and no right foot serif. This is an explicit user-requested ASCII hint
change; other m styles and stock oblique a remain unchanged. See
[the m/a comparison (archived)](../../../font-archive/README.md#useful-pages-after-extraction).

## One-pixel oblique a trial

Per the user’s next instruction, six-line O 61 adds exactly (2,-1), filling
the gap between the bottom-row pixels. Width, baseline, stock slant and all
other source points remain unchanged. The earlier source-a discussion above
describes the original unmodified glyph; this explicit repair is now applied.
See [before/after (archived)](../../../font-archive/README.md#useful-pages-after-extraction).

The one-pixel oblique-a repair also applies to E0–E5 (à á â ã ä å), per user
instruction. Each bottom row is exactly columns 1/2/3. Diacritics, baseline,
width and other style faces are unchanged by this addition.
