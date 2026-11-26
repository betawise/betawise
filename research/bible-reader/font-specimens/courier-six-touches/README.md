# Six-line Courier m correction and italic a models

[Comparisons and references (archived)](../../../font-archive/README.md#useful-pages-after-extraction), [m/a close-ups (archived)](../../../font-archive/README.md#useful-pages-after-extraction),
[Dylex native four-style specimen (archived)](../../../font-archive/README.md#useful-pages-after-extraction), [exact data (archived)](../../../font-archive/README.md#useful-pages-after-extraction).

Reproduce from the workspace after building the stock-fit set:

```
python3 betawise/research/bible-reader/font-specimens/courier_stock_fit.py
python3 betawise/research/bible-reader/font-specimens/courier_six_touches.py
```

## Applied m change

Per the user's instruction, regular six-line 0x6D is an exact copy of native
Courier Bold 8px m, fitted to the same six-column cell. Its lower three body
rows are exactly columns 0, 2, 4: three separate stems, without the regular
source's right foot serif. The regular stock-fit BDF, full card, text preview,
edit audit, combined overview and report are regenerated. Other m styles retain
their stock drawings. The previous native regular m is retained in the close-up
for comparison; the generator verifies the new m exactly equals the bold source.

## Italic a options, not applied

The source 8px oblique a remains in courier-stock-fit. Its four-row unusual
shape was independently verified against original upstream BDF previously.

* **A4:** a newly drawn, four-row single-storey a with a closed counter and
  right foot. Same x-height, baseline and six-column advance. It is an original
  local alternative, not a copied glyph from an outside font.
* **A5:** the native 12px Courier Oblique a has two identical lower stem rows.
  Remove one and move the upper rows down one: five ink rows instead of six,
  with baseline fixed. Its source ink already fits six columns; no horizontal
  resampling is needed. It is one row taller than the current four-row body.

Each option has a complete 218-glyph O BDF differing only at 0x61. They are
research alternates, not newly selected variants. Applying either would also
require reviewing accented a forms and the corresponding bold-oblique design.
The unchanged-stock option is exported for direct comparison.

## Native references and findings

Author source: https://github.com/dylex/fonts
Pinned local clone: workspace `.research-work/courier-a-references/dylex`
Commit: `9d7bd67177436a6fef6178a9001d7368c5ae4df3`.

Dylex has native 6x10 R/B/O/BO. Variants contain delta glyphs; as explicitly
documented by the author, they require fallback to the regular base. After
merging, all four faces contain all 218 Western printable characters, each
advance is six pixels, and every required glyph's ink fits x=0..5/y=-8..1.
Thus it genuinely supplies 44 columns/six lines at our dimensions without
source-glyph repairs. This is a coverage/geometry result, not native-editor or
physical LCD acceptance. The author marks fonts CC0 public domain; code is BSD.
Dylex's native oblique a has five ink rows and a visible bottom. It is a useful
actual same-width model, although its letter body is one row taller than ours.
The comparison also shows public-domain X11 Fixed 6x13O a, which is taller still.

Dina's author documentation lists six-point regular only; native italic starts
at eight points, so its smallest face is not the requested six-pixel reference.
Scientifica has native italics at five-column/11px metrics and is another possible
model, but it is not imported here. No discussion specifically diagnosing the
Adobe 75dpi eight-pixel oblique 0x61 was found in targeted web searches. That is
not evidence that no such discussion exists.

## Verification

Applied m: exact bold-source pixel comparison and three-stem assertions.
Three alternative O BDFs: 654 exact pixel/advance round trips. Dylex: 872 source
glyph width/ink-bound checks after proper variant fallback. A4: one foreground
component and a closed counter. These are source-font design checks, not a
model-driven LCD screenshot oracle. No actual Neo session is modified. Existing
font repertoire limits remain: printable Western slots, not a complete Neo
control/device map.
