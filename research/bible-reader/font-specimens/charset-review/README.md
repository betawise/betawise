# Neo-US user mapping review

The submitted `betawise-font-fixes.json` is retained as
[submitted-review.json](submitted-review.json). It supplies 34 nonempty proposals,
confirmation of Sigma, and confirmation to leave byte 90 unmapped.

[verification.json (archived)](../../../font-archive/README.md#useful-pages-after-extraction) records accepted identities and evidence.
[exact-reference-matches.json (archived)](../../../font-archive/README.md#useful-pages-after-extraction) lists all candidate
matches, including ambiguous alternatives. [native-bitmaps.json (archived)](../../../font-archive/README.md#useful-pages-after-extraction)
retains exact Neo-system and Terminal source rows for the 38 reviewed slots.
[Source-glyph card (archived)](../../../font-archive/README.md#useful-pages-after-extraction) shows the correction and the
three slots left unassigned by the submitted file.

## Method

Run from the repository root:

```
python3 research/bible-reader/font-specimens/verify_charset_review.py \
  research/bible-reader/font-specimens/charset-review/submitted-review.json
```

The script reads the saved Neo ROM font audit and verifies every Terminal glyph
against its retained pixel rows. It reads Unicode PCF encoding tables directly
for sampled X11 Misc Fixed fonts, preserving their actual Unicode assignments.
It crops blank margins and collapses consecutive identical rows, then compares
boolean pixel tuples exactly. It does not rescale or use model/vision scoring.
These are source-font diagrams, not Neo LCD screenshots or editor acceptance.

Of the 35 submitted nonempty identities, 22 have exact normalized reference
matches after correcting byte 04's case. The other 13 retain the user's manual
identification; the sampled reference fonts do not give an exact pattern match.
Matching a tiny bitmap is not always a unique semantic identification: 0D matches
both U+21B2 and U+21B5 in different fonts, and 8F matches both Pi cases in some
fonts. The user's selections are retained unless there is clear contrary evidence.

## Correction and remaining identities

* **04:** U+0143 **Ń**, capital N with acute. It matches the Unicode 6x10 reference
  exactly after normalization. The earlier audit's Ñ and the submitted lowercase
  ń are corrected. The two dots and descender in 05 support the submitted lowercase ĳ.
* **81:** U+2310 **⌐**, reversed not sign. Exact matches occur in 6x12, 6x13,
  7x13 and 7x14. One larger font's U+231C corner shares the same pattern, so this
  remains a glyph correspondence rather than proof of the firmware author's intent.
* **16:** now mapped to U+21B5 **↵**, the same Unicode correspondence as 0D.
  The pair is byte-for-byte identical in Atto, Bold, Femto, Solo, Tech1, Tech6
  and the Neo dialog font. Medium adds stem/cap details, and Nano/Micro lengthen
  the stem; this does not establish a separate Unicode character. This supersedes
  the earlier tentative U+23CE suggestion.
* **90:** now mapped to U+0060, aliasing the existing ASCII grave at 60. The pair
  is byte-for-byte identical in Bold, Micro, Nano, Solo, Tech1 and Tech6. In
  Terminal Medium, 60 has pixels (1,1), (2,2), (3,3), whereas 90 has only (1,1),
  (2,2), both with a 6px advance. The Neo dialog font substitutes the same box
  for 81/8D/8F/90/9D/A0, so it supplies no useful grave-specific evidence.

[Cross-font source diagram (archived)](../../../font-archive/README.md#useful-pages-after-extraction) and
[cross-font exact rows/metrics (archived)](../../../font-archive/README.md#useful-pages-after-extraction) are regenerated with:

```
python3 research/bible-reader/font-specimens/compare_neo_aliases.py
```

The two entries are pragmatic glyph correspondences supported by the alternate
font resources, not claims that identical low-resolution pictures prove the
historical author's intended Unicode semantics. All 256 slots now have entries.

The shared mapping and implemented BDF names have been updated; bitmap pixels,
byte slots and font advances are unchanged. No missing glyphs were fabricated.

## Primary Unicode references

* [Latin Extended-A](https://www.unicode.org/Public/UCD/latest/charts/nameslist/0100/)
  distinguishes U+0143 from U+0144 and defines U+0133.
* [Miscellaneous Technical](https://www.unicode.org/Public/UCD/latest/charts/nameslist/2300/)
  defines U+2310 and U+23CE. The latter may use hollow or filled artwork.
* [Arrows](https://www.unicode.org/Public/UCD/latest/charts/nameslist/2190/)
  defines the related return-arrow forms.

Image search was used to find candidate symbols, followed by the official names
and the exact local comparisons above; search-result captions are not evidence
of a native byte's identity.

## Vendor-only follow-up

[Vendor-only review](vendor-glyph-review.md) examines all 17 requested slots in
all five original Neo vendor fonts and both built-in fonts. It supersedes the
community-font rationale above as the basis for the two alias recommendations.
Vendor Small equates 90/60 exactly; Small/Very Large/Extra Large and the built-in
dialog equate 16/0D exactly. The review also flags 17's specific APL designation
and 18's radical-versus-check-mark identification as provisional. No mapping
entries were changed during this follow-up.

[Vendor usage audit](vendor-glyph-usage.md) confirms direct Option-H entry and
AlphaWord help for 08; no verified text/glyph consumer for 16 or 90 was found
beyond the font resources. Its scope and static-search limitations are explicit.
