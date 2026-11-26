# Existing community NeoFonts inventory

Source: `Ghidra/Alphasmart Neo/NeoFonts/` in the workspace, including the
Alquanto readme version 1.5. These are existing third-party resources, not newly
licensed or modified fonts. Reproduce from the workspace with:

```
python3 betawise/research/bible-reader/font-specimens/inventory_neo_fonts.py
```

The script verifies the initializer's PC-relative reference to the descriptor,
decodes every one of the 256 width/offset entries, and bounds-checks every
bitmap access. The original applet SHA-256 hashes, metrics, blank slots,
solid rectangles, duplicate cells, and bottom-line clipping slots are in
[inventory.json (archived)](../../../font-archive/README.md#useful-pages-after-extraction). No applets are installed or altered. No LCD
capture, emulator session or model inference is used for validation.

| Font | ID | Advertised lines | Cell height | ASCII widths | Coverage/role |
|---|---|---:|---:|---|---|
| Solo | 7151 | 1 | 66 | 3–11 | Complete populated table; 11px ink centered vertically; focused writing |
| Tech1 | 715E | 1 | 66 | 3–11 | Stylized one-line writing; populated table |
| Bold | 7156 | 6 | 11 | 3–11 | Populated Neo byte table; bold appearance, not a style quartet |
| Tech6 | 715F | 6 | 11 | 3–11 | Stylized six-line alternative; populated table |
| Mirror | 715D | 6 | 11 | 3–11 | Intentionally mirrored Tech6; unsuitable as ordinary Latin reading font |
| Micro | 7107 | 7 | 9 | 2–8 | Populated Neo byte table; proportional dense text |
| Nano | 7108 | 8 | 8 | 2–8 | Populated Neo byte table; proportional dense text |
| Femto | 7109 | 9 | 7 | 2–6, @=13 | C3 (Ã) is a solid 5×5 rectangle; not complete usable Western coverage |
| Atto | 710B | 11 | 6 | 2–6, @=13 | Same C3 defect; 11th-line clipping; extreme density |
| Neuropol | 7123 | 3 | 21 | 3–17 | Incomplete Neo charset; decorative face |
| Klingon | 7162 | 2 | 33 | 3–33 | Intentional different script, incomplete Neo byte table |

All eleven fonts are proportional by their actual ASCII width tables. None
provides separate bold, italic or bold-italic getters: the message handler
recognizes name, regular font, and height. The label "Bold" names one standalone
font, not an accompanying style set.

## Charset findings and limits

The Neo ROM system font at 0x44AF8E is the mapping reference, including low-byte
math/device glyphs and Neo-specific extended positions. CP1252 alone is not a
complete Neo charset descriptor. Some bytes are editor controls in text streams
but still have glyph bitmaps in these fonts; bitmap presence does not authorize
treating such bytes as literal editor text.

Solo, Tech1, Bold, Tech6, Mirror, Micro, Nano, Femto and Atto all have exactly two
blank glyphs: 20 and A0, as does the ROM reference. All other 254 slots have ink.
That verifies table occupancy, not semantic correctness or distinguishability.
The Atto/Femto C3 rectangle is a concrete counterexample to equating nonblank
coverage with a correct glyph. The generated source/ROM cards allow per-byte
review without guessing from names or Unicode casing rules. Micro/Nano and the
six-line Latin fonts have no detected blank holes or solid-block substitutions
apart from the intentional 00 block, but are not claimed to have passed a
complete human semantic review of every glyph.

Neuropol has blank 01–1F and 7F–9F, as well as spaces 20/A0; it has 190 nonblank
slots. Klingon additionally blanks 00, D7 and FD: 187 nonblank slots. Neither
qualifies as a complete Neo-US Latin font.

Atto and Femto share identical width tables; their first six bitmap rows are
identical for 248/256 slots. Differences: 61, 67, 6A, 70, 71, 74, 79, BF. Femto's
seventh row is blank for every glyph, but the eight differing characters mean
Atto is not simply Femto with a row discarded.

## Display boundaries

The advertised 11×6 and 6×11 arrangements span 66 rows. At 264×65, the final row
of the bottom line falls outside the display. Atto has last-row ink in 40 (@),
83 (ƒ), and A1 (¡); Bold/Tech6/Mirror have it in 00, B8 (cedilla), C7 (Ç), and
E7 (ç). This is computed from source geometry, not an on-device behavior claim.
Solo/Tech1's 66px cell has ink only at rows 27–37, so its oversized blank margins
are intentional and its visible single line fits. Klingon's second 33px cell
also has a blank final row.

## Consequences for new font selection

Keep two distinct purposes:

* **Terminal:** maximize a fixed-column grid, accepting baseline/readability
  compromises and no style quartet. Fixed and ttyp0 remain candidates here.
* **Reading/typing families:** useful baselines and spacing, full Western/Neo
  coverage, and all four styles when offering a new complete styled family.

Micro, Nano, Femto and Atto already cover much of the dense proportional-text
range, with the defects above. New small fonts should demonstrate an advantage
in mono versus proportional layout, accent correctness, baseline consistency,
letter distinction or emphasis, rather than merely a different family name.
The existing fonts do not eliminate a need for a fully styled small family,
but they are the right baseline for deciding whether it is worth adding one.
