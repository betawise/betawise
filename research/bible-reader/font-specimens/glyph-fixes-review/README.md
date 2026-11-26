# First manual glyph review

The submitted [review JSON](submitted-review.json) flags 32 glyph cells: seven
reader cells and 25 Terminal Small cells. It also contains earlier mapping
proposals for 04→ń and 17→APL quad. Those proposals are not applied: later
conversation established global Ń and vertical rectangle respectively.

Run `python3 research/bible-reader/font-specimens/review_flagged_glyphs.py`.
The [exact source audit (archived)](../../../font-archive/README.md#useful-pages-after-extraction) retains pixel differences and source
paths. These are font-resource comparisons, not LCD screenshots or automated
visual acceptance. No editable BDFs were changed for this review.

## Clipping and selected sizes

* Terminal Small's 24 flagged Latin-1 characters are exact stock Misc Fixed
  5×7 artwork under a common vertical translation. No original pixels were
  clipped by the PNG-to-BDF conversion. Numerous capital accents are simply
  absent in the upstream 5×7 font, sometimes leaving À/Á/Â identical to A.
  The 5×8 strike restores most accents at the same five-column advance, but
  would fit eight rather than nine display lines (52 columns in either case).
* Terminal 04 is custom artwork, not an exact copy of stock 5×7 Ń. Its current
  seven-row cell contains an awkward vertical accent above a crowded capital N.
  The seven-row BDF matches the retained PNG fixture, so no new conversion loss
  was introduced. A clearer local drawing is reasonable; changing the global
  character map to lowercase ń would contradict the vendor/system evidence.
* Book Small ª, Mono Small C/G, Serif Small Ξ and c are exact native X11
  artwork, including all available corresponding styles. No source pixels lie
  outside the current vertical cells. Their odd shapes do not result from
  choosing a strike too tall and clipping it.
* The flagged Serif Ξ exists only in Regular in the original selected strike;
  Bold/Italic/BoldItalic source glyphs are unavailable, not clipped.
* Mono Small Ç has the same body as C in all four current styles. Earlier
  cedilla alignment added two pixels in Regular and one in BoldItalic; it
  removed none. Bold and Italic match their sources exactly.
* Serif Small ç has the same body as c in all four current styles. Its Regular
  body moved left one column and its cedilla moved relative to it. BoldItalic
  lost one leftmost pixel in the last body row during the earlier body-alignment
  edit, so it now matches the corresponding plain c. The pixel was within the
  cell: this was an explicit prior edit, not a bounds-clipping failure. Bold and
  Italic match their original artwork.

## Recommendations pending clarification

* Book ª: a local ordinal-a redraw is reasonable; its three-row upper shape is
  hard to recognise. Check all four styles, rather than enlarging the whole font.
* Mono C/G/Ç: no size change is indicated. The plain C body already agrees with
  Ç. Clarify whether the concern is the narrow bowl, right-hand terminals or G's
  internal bar before changing these deliberate stock shapes. If C changes,
  propagate its body to Ç in each affected style.
* Serif Ξ: the U-shaped lower bar is stock artwork. Three straightforward
  horizontal bars are a reasonable local alternative; source coverage of its
  other styles is a separate issue.
* Serif c/ç: the two-column Regular c is narrow/angular. A wider bowl may read
  better but consumes spacing and needs comparison in text. Keep each style's
  c and ç bodies paired; heavier styles have different artwork and should be
  assessed individually rather than copying Regular pixels wholesale.
* Terminal Small: choose whether nine-line density is worth drawing compressed
  accented capitals, or whether to start from the more complete eight-row font.
  The current source is adequate for dense ASCII terminal output but loses
  important distinctions in accented capitals.

[All-style reader comparison (archived)](../../../font-archive/README.md#useful-pages-after-extraction) shows original on
the left and current on the right in each style. Added pixels are blue; removed
pixels are shown red over the current drawing. Deltas are measured after the
best common translation, stated below the pair. Missing glyphs are labelled.
[Terminal comparison (archived)](../../../font-archive/README.md#useful-pages-after-extraction) shows current, stock
5×7 and stock 5×8 for every flagged Terminal character.

## Clarified bowl issues and nine-line requirement

The user clarified that Mono C/G are too narrow and G's bar hits the left stem;
Serif Regular c's two-column bowl is also too narrow. Terminal Small must remain
nine lines. [Draft wider bowls (archived)](../../../font-archive/README.md#useful-pages-after-extraction) keeps all existing
advances and baselines. It explores Mono C/G/Ç in all four styles, keeping the
cedillas untouched, and widens Serif Regular c/ç from two to three ink columns.
The other Serif styles are already wider and are not changed by this proposal.
Generate it with `python3 research/bible-reader/font-specimens/glyph_fix_candidates.py`.
No shipping BDFs are changed by that script.

The local Unicode Fixed strike inventory gives the following full-Western ink
envelopes (common baseline across the repertoire, not each glyph independently):

| Strike | Full-Western ink rows | Fits 7-row pitch unchanged? |
|---|---:|---|
| 4×6 | 6 | Yes; this is the Tiny base |
| 5×7 | 7 | Yes; this is the current Small base, but some accents are omitted upstream |
| 5×8 | 8 | No |
| 6×9 | 9 | No |

There is no additional intermediate native Fixed strike in the local X11/u8g2
sources. The 5×8 font does not have one globally empty row that can be dropped:
its Western ink spans all eight rows. Ttyp0's smallest size is 6×11 per the
[author's inventory](https://people.mpi-inf.mpg.de/~uwe/misc/uw-ttyp0/).
Spleen's smallest size is likewise 5×8, and is not a seven-row solution.

Recommendation: retain the nine-line 5×7 base and locally redraw affected
accented capitals, using the 5×8 artwork as a model. Several will need a shorter
capital body to leave room for a distinct mark within the same baseline/cell;
there is no claim this is a lossless empty-row crop of an existing complete font.

The user approved the Serif Regular c/ç widening, which is now applied to the
shipping BDF and regenerated applet/review page. The Mono proposal was revised
to add exactly one ink column to C/G in each style; its advances remain six
columns. Mono artwork is still a draft.
