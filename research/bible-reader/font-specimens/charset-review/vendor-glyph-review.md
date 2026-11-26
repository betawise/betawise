# Vendor-only review of Neo-US glyph identities

Source resources: the five original `neofont{small,medium,large,vlarge,xlarge}.os3kapp`
files under `Ghidra/Alphasmart Neo/SmartApplets`, plus Neo 3.21 ROM descriptors
0x44AF8E (system 6×16) and 0x44E336 (dialog). No community font contributes to
these conclusions. The 6×8 Terminal recreation is not an independent vendor source.

Run `python3 research/bible-reader/font-specimens/audit_vendor_charset.py`.
[Manual-identity card (archived)](../../../font-archive/README.md#useful-pages-after-extraction) and
[additional-slot/comparison card (archived)](../../../font-archive/README.md#useful-pages-after-extraction) retain full glyph cells
at 3× nearest-neighbour scale. [Raw evidence (archived)](../../../font-archive/README.md#useful-pages-after-extraction) retains
all rows, advances, exact native aliases and matches to Unicode-labelled X11
reference glyphs. The X11 references help name shapes; they are not vendor fonts.
Normalized reference comparison removes blank margins and consecutive repeated
rows, as in the earlier audit; it is not an unmodified-cell comparison.

All seven resources were inspected for every slot below. The larger vendor
artwork supports the same shapes seen at smaller sizes. These are glyph-identity
judgements, not determinations of text-editor control-byte semantics.

| Slot | Proposed identity | Vendor-only assessment |
|---|---|---|
| 01 | δ U+03B4 | Supported: closed lower bowl and curved upper stroke; clearly lowercase delta at large sizes. |
| 03 | ∫ U+222B | Supported: elongated integral with opposing terminal hooks. |
| 05 | ĳ U+0133 | Supported: two dots, short i and descending j, not uppercase IJ. Dialog/Small have an exact normalized U+0133 reference match. |
| 06 | ⛶ U+26F6 | Supported as a visual correspondence: four inward-facing corner brackets, open sides. Original UI meaning is not established. |
| 07 | ⅔ U+2154 | Supported: 2 over slash and 3; very clear in the largest vendor fonts. |
| 09 | ⇥ U+21E5 | Supported: right arrow ending at a vertical bar. Medium has exact normalized U+21E5 reference matches. |
| 11 | ⅓ U+2153 | Supported: 1 over slash and 3. |
| 17 | ⎕ U+2395 | Outline box confirmed, specific APL identity unproved. U+25AF WHITE VERTICAL RECTANGLE is also plausible (exact normalized match for system/Large); Dialog/Small/Medium match several square/rectangle/quad references. Retain as provisional. |
| 18 | √ U+221A | Not settled. All seven draw a rising tick without a horizontal overbar; larger fonts look check-mark-like. U+2713 CHECK MARK deserves consideration. Radical glyphs can also lack an overbar, so shape alone does not justify automatically replacing the submitted mapping. |
| 19 | ≤ U+2264 | Supported: less-than with a separate underline. Medium/Large have exact normalized U+2264 reference matches. |
| 1A | ≥ U+2265 | Supported: greater-than with a separate underline. Medium/Large have exact normalized U+2265 reference matches. |
| 1B | Θ U+0398 | Supported: capital-height closed outline and horizontal inner bar. Dialog/Small have exact normalized U+0398 reference matches. |
| 1E | β U+03B2 | Supported: lowercase beta, with a descender; not the vendor sharp-s glyph at DF. |
| 04 | Ń U+0143 | Supported: uppercase N with acute, distinct from ordinary N at 4E, lowercase n at 6E and N-tilde at D1. System/Dialog/Small/Medium/Large match the normalized U+0143 reference. |
| 16 | ↵ U+21B5 | Supported as an alias of 0D: exact full-cell equality in vendor Small/Very Large/Extra Large and the built-in dialog font. System/Medium/Large retain stem/cap/vertical-placement variations. |
| 81 | ⌐ U+2310 | Supported by all five vendor fonts and system 6×16. Dialog substitutes its generic outlined box, shared with 8D/8F/90/9D/A0, so is not positive evidence. |
| 90 | grave U+0060 | Supported as a practical alias of 60: exact full-cell equality in vendor Small. Other vendor fonts and system draw a shorter grave than 60. Dialog substitutes its generic outlined box. The vendor images do not uniquely distinguish the Unicode spacing-grave/modifier-grave choices. |

## Exact native pairs

| Source | 16 = 0D, full cell | 90 = 60, full cell |
|---|---|---|
| System 6×16 | No | No |
| Dialog | Yes | No: 90 is the generic box |
| Small | Yes | Yes |
| Medium | No | No |
| Large | No | No |
| Very Large | Yes | No |
| Extra Large | Yes | No |

No mapping or glyph artwork was changed by this review. Slots 17 and 18 remain
explicitly provisional; the earlier manual classification was not a semantic
verification. The vendor evidence independently supports the existing pragmatic
16/0D and 90/60 aliases without relying on community fonts.

## Follow-up: symbol comparison and accent entry

[Large vendor glyphs beside Unicode candidates (archived)](../../../font-archive/README.md#useful-pages-after-extraction)
can be regenerated with `python3 research/bible-reader/font-specimens/compare_vendor_symbols.py`.
The Unicode samples are labelled DejaVu font designs, not canonical outlines.
Slot 17 now uses U+25AF WHITE VERTICAL RECTANGLE following the user's preference;
slot 18 retains the submitted U+221A SQUARE ROOT. The square-root examples show
why a missing long overbar does not establish CHECK MARK. DOS CP437 contains
U+221A at FB; Windows-1252 does not contain it.

U+26F6 is a standalone symbol (category So, combining class 0), not a combining
character. Its Unicode annotation is intersection; it is a visual correspondence
for the four corners, not a claim about the Neo UI's intended meaning.

Neo 3.21 TranslateKeyToChar at 0x423C7C calls the pending-accent helper at
0x4244CA. That helper indexes five descriptors through the table at 0x44B66A.
Their addresses and fallback spacing bytes are:

| Accent | Descriptor | Spacing byte |
|---|---|---|
| Acute | 0x447CD9 | B4 |
| Grave | 0x447CED | 60 |
| Circumflex | 0x447D01 | 5E |
| Diaeresis | 0x447D15 | A8 |
| Tilde | 0x447D2C | 7E |

The helper emits descriptor byte +2 when a pending accent must be emitted alone;
matching letters return one precomposed native byte. Thus the standard grave
entry path uses 60, not 90, and dot above is not one of these five dead accents.
Font widths for 08/90 are respectively System 6/6, Dialog 6/6, Small 6/4,
Medium 3/3, Large 2/3, Very Large 5/4, Extra Large 4/4. Neither slot has a zero
advance in any inspected vendor/built-in descriptor. No evidence found here
supports changing them to Unicode nonspacing combining marks.
