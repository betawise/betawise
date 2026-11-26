# Five-row Century and size inventory (research only)

Run from the workspace root:

```
python3 betawise/research/bible-reader/smallcaps-hinted/tune_and_sizes.py
```

Outputs are under ignored `build/tuned/`. No applet, provider font or SDK changes.
The script verifies unchanged production source hashes, all 256 BDF slots by exact
pixel/advance round trip, preservation of ordinary ASCII digits and lossless
translation of every selected source glyph. Deliberate hand edits remove ink;
“no clipping” means no accidental loss at the cell boundary, not unchanged shapes.
These are offline glyph experiments, not firmware or readability acceptance tests.

## Century experiment

The 8pt hinted six-row capitals retain their advances. Explicit per-letter row
choices reduce their cap height to five rows; S has separately drawn regular and
bold patterns. Q retains its tail. Accented lowercase letters use these bases and
explicit acute/grave/circumflex/tilde/diaeresis/ring/cedilla bitmaps. The ring uses
all three rows above the five-row capital and touches it: this is a dense design,
not a claim of equal quality to the larger original. Three faces each cover the
191 printable Latin-1 characters in an 11-row cell. Superscript overlay absent.

The 10pt full-size uppercase accented glyphs do NOT fit unchanged at the current
baseline. This complete candidate falls back to unscaled 8pt glyphs for the 25
uppercase accented letters that would clip, plus dollar. Consequently an accented
capital is smaller than its unaccented full-size counterpart. This is an explicit
tradeoff; a uniformly sized full-cap alphabet with accents needs more height or
another hand-drawing pass. Lowercase small capitals do not have that inconsistency.

Regular a–z advances total 158px (previous runtime resize: 132px). Five rows does
not make the hinted design as narrow as the runtime resize. Regular/bold/italic
bitmap payloads are 2400/2590/2456 bytes, each plus 768 bytes width/offset tables
and a 16-byte descriptor; these include all 256 slots, including blank controls.
Latin-1 coverage is not proof of the Neo character mapping or safe control codes.

Comparison columns: current resized design, unscaled six-row hinted design,
hand-tuned five-row design. Extended characters in the first column illustrate
the cropped approach, not an approved font. The two right columns use smaller
full-size accented capitals where necessary. Magnification is nearest-neighbor.

## Size recommendations

Required ink envelope across normal, bold, italic and bold italic, aligned to H's
bottom. Each entry is ASCII / full printable Latin-1, in pixels:

| Source strike | Times | Century | Helvetica |
|---|---:|---:|---:|
| 8pt | 9 / 10 | 10 / 10 | 10 / 11 |
| 10pt | 11 / 13 | 11 / 13 | 10 / 13 |
| 12pt | 13 / 15 | 13 / 15 | 13 / 15 |
| 14pt | 15 / 18 | 15 / 18 | 15 / 17 |
| 18pt | 19 / 22 | 20 / 23 | 18 / 23 |
| 24pt | 25 / 29 | 25 / 29 | 24 / 29 |

These are ink requirements, before adding interline whitespace. The size sheet
shows the largest installed ASCII strike fitting each pitch without clipping;
wraps are illustrative character wraps, not the native editor's word layout.
The 6-line/11px panel actually fits only five complete cells in 65px. An app may
fit six only with an explicitly blank final row or another spacing policy.

Suggested distro:

* Core: 10pt at 11px compact ASCII pitch (nominal six lines, final-row policy
  required), 10pt at 13px Latin-1 pitch (five lines), 12pt at 16px pitch (four).
  The 11px and 13px 10pt entries are the same body ink, different cell spacing.
* Additional comfortable large choices: 18pt at 23px (two complete lines, or use
  18pt ASCII at 21px for three), and 24pt at 32px (two). For three full-Latin-1
  lines choose 14pt at 21px; its ink needs 17–18px.
* Compact option: 8pt at 10px for Times/Century or 11px for Helvetica. These are
  roughly six lines, not seven or eight. Seven 9px rows work for Times ASCII
  only among these unmodified strikes. Tight spacing is a human preference.
* Eight through eleven rows need pitches 8,7,6,5px respectively to fit complete
  cells. None of these X11 family strikes fits losslessly. Do not downsample
  serif body text just to offer every line count. A separate 5x7/6x8 terminal
  family is the better compact option. Five-row cells are a specialist tiny
  display, not a recommended book-reading default.

Practical family range: 8pt through 24pt; ship 10/12pt as the core, 8/14/18/24pt
as optional sizes. Two-line type is large but useful for accessibility, not absurd.
At the smallest strike, use ordinary capitals for small caps. At larger strikes,
next-smaller hinted capitals are a starting point, not automatically an x-height
match; the accompanying size comparison exposes that jump. Century 10pt uses this
study's tuned five-row alternative. These are design recommendations, not measured
human legibility scores. Full Latin-1 and all faces must pass envelope checks.

## Extra-face protocol proposal (not implemented)

`FontHeader_t` is a 16-byte descriptor: height/max width/max bytes/padding, then
width-table, offset-table and bitmap-data pointers. A variable-width glyph does
not occupy one pointer-sized slot. Adding 256 to any existing font pointer is
not a valid way to get another face. Even an explicit descriptor array would
advance by 16 bytes per face; legacy/vendor resources need not be arrays.

Use an explicit versioned extra-face query or a versioned font-set resource with
normal/bold/italic/bold-italic and optional small-caps regular/bold/italic pointers.
Absent capability returns no face. Keep ordinary getters unchanged; do not assume
bytes after a legacy descriptor exist. A pointer to ROM data costs no bitmap A5
RAM; a relocated descriptor may still need 16 bytes. This does not give the native
editor more than four simultaneous slots: BibleWise must compose a fourth face
using the extras or choose a fallback.

26 ASCII small capitals times three styles plus ten superscript digits is only
88 shapes. But preserving a whole charset changes the accounting:

* 191 printable Latin-1 slots with regular small caps replacing lowercase, plus
  two additional ASCII alphabets and ten extra digits: 253 slots. Replacing the
  ordinary digit slots for the Bible overlay makes that 243.
* Supporting all 58 Latin-1 lowercase mappings in all three small-cap styles:
  191 + 116 + 10 = 317; digit replacement gives 307. That cannot fit one 256-slot
  face while retaining the original printable mappings.
* Preserving all 128 upper-byte characters, rather than Latin-1's 96 printable
  upper-byte characters, also invalidates the apparent 253-slot fit.

Slot count alone does not establish usability: Neo character codes and formatting
controls must be audited. The Bible's actual styled small-cap subset is much
smaller, so a sparse Bible-specific packed face is feasible. Use a forward mapping
for styled glyph selection and reverse mapping for clipboard extraction when codes
are repurposed. Regular lowercase small-cap bytes need no letter translation.
Superscript ASCII digits can be a Bible-only overlay, omitted by verse metadata
when copying; generic small-cap resources should retain ordinary digits. Separate
explicit auxiliary faces avoid forcing general font consumers into this encoding.
