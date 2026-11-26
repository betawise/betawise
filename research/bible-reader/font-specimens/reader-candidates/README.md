# Selected reader fonts

[Combined specimen (archived)](../../../font-archive/README.md#useful-pages-after-extraction), [gallery (archived)](../../../font-archive/README.md#useful-pages-after-extraction),
[manifest and BDF hashes (archived)](../../../font-archive/README.md#useful-pages-after-extraction).

Regenerate from the workspace root:

```
python3 betawise/research/bible-reader/font-specimens/reader_candidates.py
```

Three/four/five-line selections use the largest untouched native Adobe strike
whose complete 218-character Western printable repertoire fits across all four
styles. No accent, descender, cedilla, slant or cell-width edits are applied to
these 48 faces. All installed 75/100dpi strikes are considered. Native glyph
pixels and normalized advances match the preceding native-fit comparison.

| Family | 3 lines | 4 lines | 5 lines | 6 lines |
|---|---:|---:|---:|---|
| Times | 17px | 12px | 11px | Reviewed 8px |
| Helvetica | 17px | 12px | 11px | Reviewed 8px |
| Schoolbook | 17px | 12px | 11px | Reviewed 8px |
| Courier | 20px | 14px | 11px | Reviewed 8px |

The sixteen six-line style faces are retained byte-for-byte from the reviewed
selection, including local extended-glyph repairs, Helvetica cedilla placement,
and Courier's m and oblique a corrections. Courier six-line cells remain 6px,
44 columns. The larger native Courier selections do not inherit the custom
extra column or edge repairs from earlier experiments.

| Family | 3 lines | 4 lines | 5 lines | 6 lines |
|---|---|---|---|---|
| Times | AFF0 | AFF1 | AFF2 | AFF3 |
| Helvetica | AFF4 | AFF5 | AFF6 | AFF7 |
| Schoolbook | AFF8 | AFF9 | AFFA | AFFB |
| Courier | AFFC | AFFD | AFFE | AFFF |

IDs remain reservations. The 64 BDFs round-trip all 13,952 pixels/advance glyph
records exactly. The 48 untouched faces additionally match native source
pixels. Previous accent/cedilla comparison files are historical and are not
linked as the selected set.

The repertoire is 218 CP1252 printable entries, not a verified complete Neo-US
control/device mapping. Provider builds and native editor acceptance remain
before shipping. Cards are offline source-font specimens, not Neo screen
captures. Adobe/DEC licensing is retained in FONT-LICENSE.txt.
