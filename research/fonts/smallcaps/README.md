# Recovered small-cap assignment and native source audit

All generated cards, galleries and JSON reports live under
`research/fonts/build/smallcaps/`; this directory contains notes only.

Run `python3 research/fonts/smallcaps_sources.py` from the repository root.
This reads current accepted body BDFs and original Unicode X11 strikes. It does
not change shipping artwork or generate rescaled small capitals.

`encoding.json` is a generated research view of the authoritative
[shared charset](../../../os3k/charsets/neo-smallcaps.json).
The adopted encoding computes Regular from native lowercase source bits using
the 66-byte selector algorithm. Italic is Regular XOR 2B; Bold is Regular XOR 40.
There are 62 forms across three styles plus ten superscript digits at 30–39:
**196 distinct ordinary-glyph slots**. Ń is omitted because Neo-US lacks lowercase
ń. IJ is the small-cap counterpart of native lowercase ĳ. Both directions are
table-free; decode returns native lowercase and rejects unassigned slots.
See the [codec API](../../../os3k/charsets/README.md#private-small-capitals).

This private encoding is separate from ordinary Neo-US. Keep body spaces and
punctuation outside private letter runs. Superscript digit slots remain 30–39.
The descriptor and generated C converters are the source for encode/decode rules;
older archived specimen encodings are historical.

## Smaller native strikes

The audit considers all same-family 75dpi and 100dpi Unicode Adobe strikes
smaller than the accepted body strike, in Regular/Italic/Bold. Target x-height
comes from the current body x, not the old eleven-pixel prototype readers.
Native small-cap height is measured from H. It checks all 62 forms, including
accents and SS source S, aligned to the bottom of the body's x. No rescaling,
accent movement or clipping is applied in this audit.

`sources.json` contains every candidate, per-style
heights, source paths, missing glyphs and overflow cases. `closest` retains ties
so a smaller source is not presented as the only possible choice. Every selected
3–5-line candidate contains the source glyphs and fits vertically for all 62
forms in all three styles. SS requires composing two native S glyphs; it is not
claimed to be a separately designed ligature.

| Lines | Serif target → native H | Sans | Book | Mono |
|---|---|---|---|---|
| 3 | 8 → 7 or 9 | 9 → 9 | 8 → 8 | 8/9/8 → 8 or 9 |
| 4 | 6 → 5 or 7 | 7 → 6 or 8 | 6 → 6 | 7 → 6 or 8 |
| 5 | 5 → 5 | 6 → 6 | 5 → 6 | 5 → 5 |
| 6 | No smaller same-family strike | None | None | None |

Mono's 3-line body Italic x is one pixel taller than Regular/Bold. Neither one
common native cap height matches all three exactly. The comparison PNGs show
the smaller of tied native-height choices; the JSON also records larger choices.
For six-line bodies, the smallest source is already 8px: native capitals are
5px (Serif/Mono) or 6px (Sans/Book), against x-heights 4/4/5/4 respectively.
Using those same capitals would not produce a smaller uppercase design.

The `*-in-context.png` cards show 3/4/5-line bodies in Regular, Italic and Bold.
Each option has a body-only reference, the same sentence with LORD in small caps,
and extended/composite forms between body x glyphs. All share the body baseline.
All equally close height alternatives are shown, deduplicating strikes with the
same per-style cap heights. Ink is displayed at 3× nearest-neighbour enlargement;
source glyphs are never rescaled or clipped. Body spaces are used between runs.
Open [index.html (generated on demand)](../README.md#generated-research-output) to compare the cards at full size.
These are source studies, not accepted or installed small-cap fonts.

## Updated height preference and alternatives

The preferred native cap height is now body x-height through x-height+1;
shorter candidates remain in the historical comparison but are not preferred.
`sources.json` has a `preferred` list applying this criterion to each style.

Run `python3 research/fonts/audit_smallcap_alternatives.py` for the local
non-Adobe and Unicode small-cap inventory in `alternative-sources.json`.
Lucida provides 6/7/8px caps with real Italic and Bold; Lucida Bright has 6/8px
caps with Demibold and Bold. These can fill same-family Adobe height gaps,
but change the design. Lucida Typewriter lacks Bold in these installed strikes.
Fixed 4x6 has **5px**, not 4px, native capitals, with Regular only. Smaller ttyp0
strikes have 8px capitals in Regular/Italic and no Bold.

All 192 installed Adobe Unicode strikes were checked for the Latin small-cap
letters named in the local Unicode database: none contain them. Lucida likewise
has none in the audited strikes. Fixed and ttyp0 have partial phonetic subsets
(11–12 characters), not a complete small-cap alphabet and accented repertoire.
These are explicit encoded glyph checks, not fallback renders.

## Lucida in context

Run `python3 research/fonts/compare_lucida_smallcaps.py` and open
[lucida-comparison/index.html (generated on demand)](../README.md#generated-research-output). Every Lucida/Bright
column exactly matches the corresponding body x-height, including Mono 3-line
where separate sizes are used for its 8/9/8px targets. All 62 allocated forms
are checked for source availability and vertical fit in each candidate.
Adobe comparisons follow the x-height through x-height+1 criterion.
Lucida Bright supplies Demibold in the Italic column. No shipping fonts change.

## Six-line private faces

`python3 research/fonts/build_private_fonts.py` writes all sixteen combined
private BDFs under the families' `private/` directories. Each contains 186
Regular/Italic/Bold letter slots and ten superscript digits, using the shared
`neo-smallcaps.json` encoding. `make -C fonts bdfs` emits the same files as
part of the full source recipe. All 62 forms, including IJ, are required.

For 3/4/5 lines, the generator searches original same-family Adobe strikes and
requires native H height equal to body x-height or x-height+1 in every style.
It chooses the closest height, then smaller pixel size and dpi to resolve ties,
and rejects any missing or vertically clipped letter. Source artwork and
advances are translated to the body x baseline without rescaling. For six lines,
letters copy the accepted native uppercase cells exactly. SS/IJ concatenate two
capitals. Unassigned BDF slots remain absent; the applet converter explicitly
maps those to blank one-pixel cells, not to a letter or digit.

The eight-pixel X11 strikes supply only a partial superior-number repertoire.
All ten private digit slots therefore use the existing BibleWise default 3×5
pattern, placed at row zero in the 11-row cell with advance four. The artwork
recipe is `research/fonts/superscript-3x5.json`; it does not depend on importing
an applet module during font generation.

The BDFs declare NEO-SMALLCAPS/1. All 16 reader providers expose their fifth
descriptor through `MSG_FONT_GET_PRIVATE` (0x01000007), while the four standard
style getters and IDs are unchanged. Viewer code uses the shared charset lookup
to translate letters; body spaces and punctuation stay outside private runs.

[six-line.png (generated on demand)](../README.md#generated-research-output) shows body text, uppercase fallback text, accented
forms/composites and all ten superscript digits in Regular/Italic/Bold.

## Current assignment card

Run `python3 research/fonts/render_smallcaps_charset.py` to generate
[the 32×8 card (generated on demand)](../README.md#generated-research-output) from the shared descriptor and actual Book Medium
private BDF. Black is Regular, green Italic, purple Bold, blue superscript digits,
red reserved editor slots and gray unused slots. The renderer asserts that all
196 assigned slots have artwork and none overlap reserved slots.

## Encoding research summary

The adopted encoding maps 62 native lowercase forms to three disjoint styles,
avoiding editor controls. Regular uses the 66-byte arithmetic helper in the
[generated codec](../../../os3k/charsets/neo-smallcaps.h); Italic XORs 2B and
Bold XORs 40. The AC immediate selects a Boolean predicate, not a memory table.
Incoming conversion accepts letters only. Superscript digits retain slots 30–39
and are placed directly; reverse decoding returns lowercase letters or digits.

We compared 66-, 70- and 82-byte implementations. Nominal MC68000 ASCII means
were 127.46, 138.46 and 214.69 cycles respectively, including callee overhead
but excluding caller setup and style selection (zero wait states). The 66-byte
version was both smallest and fastest on average. Moving the consecutive digit
run did not simplify the tested construction. ABCD/SBCD/NBCD offered no useful
simplification; the 68000 has no DAA. This was a bounded search, not proof of
optimality. Production tests exhaustively check all byte inputs and styles,
reverse decoding, reserved slots and execution on m68000 QEMU. Experimental
search scripts and alternative codec implementations are no longer retained.
