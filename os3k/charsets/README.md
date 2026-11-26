# Native glyph repertoires

[neo-us.txt](neo-us.txt) records every byte slot using a hexadecimal byte and
Unicode scalar, or `UNMAPPED` when the native artwork's identity is unresolved.
Python readers can use `charsets.load(path)` from `os3k/`.

Neo US printable Western glyph positions match the supplied reader fonts and
Terminal. Additional mappings incorporate the submitted human review and exact
reference-font comparisons. Slot 04 is uppercase Ń (U+0143), correcting the
earlier mistaken Ñ identification and the submitted lowercase ń. Slot 1F is Σ.
Slot 17 uses U+25AF WHITE VERTICAL RECTANGLE, rather than assigning an
unsupported APL meaning to the outline box.
The descriptor maps all 256 slots. Cross-font comparisons support 16 as an
alternate rendering of 0D (U+21B5), and 90 as an alternate rendering of 60
(U+0060). Several supplied Neo fonts have identical bitmaps for these pairs.

Evidence and reproduction are recorded in
`research/bible-reader/font-specimens/charset-review/README.md`.
The byte 81 glyph matches U+2310 ⌐ in four reference fonts. These low-resolution
shape comparisons do not uniquely establish historical Unicode semantics;
several equivalent-looking reference glyphs can share the same pixel pattern.
The user's mappings are retained as glyph correspondences, not new claims about
the scanner/control protocol. In particular, 0D has exact matches for both U+21B2
and U+21B5 in different fonts; the user's U+21B5 choice is retained.

This describes glyph identity, independently of firmware text-editor records.
For example, a byte can have printable font artwork and also serve as an editor
control depending on context. See `research/syscalls/text/token-records.md`.
Unknown slots must not silently become Unicode C0/C1 controls or question marks.

BDF ENCODING remains the native byte. Each file declares NEO/US, and STARTCHAR
uses the mapped Unicode glyph name (with a suffix for duplicate aliases).
Unmapped artwork uses a native-byte glyph name. A missing BDF glyph is separate
from an unknown Unicode mapping; missing glyphs remain absent, and the applet
build's explicit fallback policy supplies `?` where required by its 256-slot table.

## Private small capitals

[neo-smallcaps.json](neo-smallcaps.json) is the authoritative custom glyph charset.
It lists 62 forms × Regular/Italic/Bold (186 letter slots), ten superscript digits,
native lowercase source bytes, canonical decode bytes and reserved slots.

All three letter styles are computed without runtime lookup tables. Regular
maps a known native lowercase byte with the adopted 66-byte algorithm; Italic
is Regular XOR 2B, and Bold is Regular XOR 40. Digits bypass these transforms
and remain 30–39. Ń is omitted because Neo-US has no lowercase ń.

| Form | Native lowercase | Regular | Italic | Bold |
|---|---|---|---|---|
| A | 61 | 4B | 60 | 0B |
| IJ | 05 | 7A | 51 | 3A |
| Ÿ | FF | D5 | FE | 95 |
| SS | DF | 55 | 7E | 15 |

The shared descriptor explicitly records all 196 destinations. The assignment
script computes them from the same arithmetic and rejects reserved/colliding
slots. The ROM research audit separately checks ordinary-glyph classification.
Source bytes and private glyph bytes are distinct namespaces: Regular no longer
preserves native lowercase positions. Spaces/punctuation stay in the body face.

Run `python3 os3k/charsets/assign_smallcaps.py` to regenerate assignments, or
add `--check` to verify them. Then generate [neo-smallcaps.h](neo-smallcaps.h):

```
python3 os3k/charsets/generate_smallcaps.py
python3 os3k/charsets/generate_smallcaps.py --check
```

The C template is [smallcaps_codec.h.in](smallcaps_codec.h.in). The generator
checks the formulas against every descriptor input/style and all 256 decode
slots before emitting it. There are no C data tables.

C consumers include `charsets/neo-smallcaps.h`:

- `NeoSmallCapsRegularFromLowercase(source)` is the fast, known-letter helper
  using the measured 66-byte algorithm. Input must be a supported lowercase
  letter, not a digit or private glyph byte. Inlining may change code size.
- `NeoSmallCapsEncodeByte(source, style, &glyph)` validates native input, accepts
  supported lowercase letters only. Superscript digits are placed directly at
  30–39; decoding returns their ordinary digits.
- `NeoSmallCapsRegularByte(source)` is the checked source-to-Regular wrapper;
  zero indicates unsupported input.
- `NeoSmallCapsStyleRegularByte(regular, style)` accepts a known private Regular
  letter/digit and selects a style with XOR, keeping digits unchanged.
- `NeoSmallCapsDecodeByte(glyph, &source)` reverses any private style to native
  lowercase and rejects unassigned slots. SS returns ß; IJ returns ĳ. Digits
  return their original codes. Exact original capitalization is not recoverable:
  retain original file text and its small-cap flags.

Python `encode()` and `decode()` use the same table-free arithmetic. `tables()`
remains an offline descriptor-validation/research view; it is not needed by the
runtime converters. Unsupported Python input returns `None`; C returns false
and preserves the output byte. BoldItalic small capitals are not allocated.

Art provenance is separate from encoding: same-family Adobe capitals at
x-height or x-height+1, without whole-glyph scaling. Six-line faces copy accepted
uppercase artwork. Reassigning bytes does not alter glyph artwork or metrics.
