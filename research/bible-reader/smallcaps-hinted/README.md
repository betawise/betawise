# Smaller hinted small capitals — research only

This prototype changes no applet, installed font, production generator, or
BibleWise resource. It reads installed X11 PCF sources and writes only its own
ignored `build/` directory. No font provider or applet ID is created.

## Compare

From the workspace root:

```sh
python3 betawise/research/bible-reader/smallcaps-hinted/compare.py
```

Outputs include:

* `build/comparison-regular.png`: all three current 11-pixel reading faces.
* `build/Times-styles.png`, `CenturySchoolbook-styles.png`, `Helvetica-styles.png`:
  regular, bold and italic/oblique comparisons.
* `build/comparison-latin1.png`: an accented Latin-1 extension, using 13-pixel
  cells so the original full-size uppercase accents are not cropped.
* Thirty-six editable BDFs with matching generated Neo-layout `.h` tables.
* `build/report.json`: source hashes, metrics, inventory, export sizes, validation
  results and hashes of the unchanged production inputs.

All specimens use integer 4× enlargement without smoothing. Gold marks the
target lowercase x-height top; blue marks the baseline boundary. Uppercase
initials come from the body face. Lowercase characters select the small-cap
face. The alphabet rows show every ASCII small capital.

## Current versus hinted

The left side reconstructs the current BibleWise nearest-sample algorithm,
including its actual H/x metrics and per-letter ink bounds. The body faces use
the same 75dpi 10-point sources and the same 11-pixel crops/Schoolbook shift as
the existing reader-font prototypes. Every supported ASCII body glyph is
checked against the existing generated reader font C tables when present.

The right side uses the same family's 75dpi 8-point uppercase glyphs, retaining
their pixels and advances. It only translates them to align the capital H's
ink bottom with the body's lowercase x ink bottom. It does not resize them.
Q tails and other original glyph extensions are retained below that line.

| Family | Target x-height | Hinted capital height | Result |
|---|---:|---:|---|
| Times | 5 | 5 | Exact height match |
| Century Schoolbook | 5 | 6 | One pixel taller; no available exact match |
| Helvetica | 6 | 6 | Exact height match |

The same height relationship holds for the bold and italic/oblique variants.
Schoolbook is deliberately shown taller: shrinking its hinted six-row glyphs
again would not be an unscaled hinted alternative. A five-row version needs
manual/specialized hinting, or a different source. Choosing the taller version
would be a design change, not an automatic drop-in replacement.

Advances differ too. In the regular ASCII small-cap alphabet, current/hinted
totals are Times 138/146 pixels, Schoolbook 132/158, Helvetica 149/150. Actual
Bible words contain only some of these letters; these totals are not chapter
size estimates. Adoption would require fresh native wrapping/paging tests.

The inventory covers all three families/styles at 8, 10, 12, 14, 18 and 24
points. Eight points is the smallest supplied 75dpi strike, so a reader already
using that source has no smaller strike here. Hand tuning, another source, or
the existing resizing fallback would still be necessary for that case.

## Accents and exported faces

The 11-pixel exports intentionally cover ASCII only. Other slots are blank;
these are comparison resources, not complete production fonts. Full uppercase
accent coverage should not be claimed for the current tightly cropped reader
cells.

The `*-latin1.bdf` exports use the original 13-pixel cell and cover ASCII 32–126
plus printable Latin-1 160–255. They preserve the original non-lowercase glyphs.
Lowercase Latin letters select the corresponding smaller uppercase glyphs,
including the source-hinted diacritics. Sharp s uses an explicit SS ligature;
y-diaeresis uses Y plus the source A-diaeresis accent because uppercase
y-diaeresis is outside Latin-1. These compositions are recorded in the report.
Micro signs and ordinal indicators are preserved rather than case-converted.

The accent comparison's left side applies the current resize rule to Latin-1
as an experiment. Production BibleWise does not currently render accented
small capitals: its text conversion remains ASCII. The right side preserves
the smaller glyph's entire ink, including its accent. Assertions reject clipping.

Latin-1 byte positions are **not** a verified Neo charset mapping. In particular,
native text control bytes need an explicit encoding/escaping policy before any
integration. The three style resources are separate; no fourth-face packing
contract is implemented by this study.

## Superscripts remain separate

ASCII `0`–`9` are copied unchanged from the body face in every exported resource,
and asserted equal. No BibleWise verse digits or private bold/italic small-cap
code ranges are inserted. Original Latin-1 characters such as superscript two
remain normal source characters, independently of a future BibleWise overlay.

The generated resources are suitable inputs to further font-package research;
they are not installed and are not used by the current reader. A later
BibleWise-specific overlay/packing step must be evaluated separately.

## Validation

The initial study also compared all 234 current ASCII small-cap glyphs
(26 letters × 3 styles × 3 families) to accepted MAME binary captures, without
using screenshots or model vision. To repeat that optional check, provide a
JSON map of family names to capture directories:

```sh
python3 betawise/research/bible-reader/smallcaps-hinted/compare.py \
  --accepted-captures /tmp/smallcaps-accepted-captures.json
```

Every BDF is read back by the existing font loader and compared pixel-for-pixel,
including advances and cell dimensions. All 36 BDF round trips pass. All 191
printable Latin-1 source positions must exist; controls are blank, not guessed.
Unscaled hinted placements reject loss of source ink. Digits must remain normal.
Protected production-source hashes must remain unchanged.

These are deterministic offline font studies, not MAME screen benchmarks and
not an automated legibility score. The images are provided for human comparison.
Source notices are copied alongside the generated assets as `FONT-LICENSE.txt`.
