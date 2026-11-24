# Eleven-pixel reader test fonts

Run `python3 betawise/research/bible-reader/reader-fonts/build.py` from the
workspace root. Generated applets remain under ignored `build/`. The disposable
MAME BibleWise launcher installs them alongside all five vendor font applets.

Sources are installed X11 75dpi 10-point PCF families New Century Schoolbook,
Helvetica and Times, each with regular/bold/italic/bold-italic faces. Font IDs
are A1F5, A1F6 and A1F7. License notices are preserved in FONT-LICENSE.txt.
These are ASCII test fonts: slots 32–126 preserve source ink; others use a
question-mark fallback.

Every source cell is thirteen pixels high. All ASCII faces of Century
Schoolbook and Times have two empty top rows, asserted before removing them,
leaving eleven rows of original ink. Helvetica has three blank top rows;
removing those and adding one blank bottom row gives an eleven-pixel cell.
Century Schoolbook then moves up one pixel as requested, leaving its last
row blank. This clips the top pixel of the dollar sign in all four ASCII faces;
other supported glyphs keep their complete ink. Helvetica and Times are unchanged.

The native editor uses six eleven-pixel rows, a 66-pixel viewport on the
65-pixel LCD. For Helvetica the invisible last row is blank. For Times the final line's bottom pixel can clip descenders; Century
Schoolbook now has a blank last row. This is a physical
height limit, not a conversion failure; five rows or ten-row ink would avoid it.

Compared with the eight-point versions, regular Century Schoolbook capitals
grow from six to eight pixels, Helvetica six to eight, and Times five to seven.
X-heights grow from four to five, five to six and four to five respectively.

Tests compare native wrapping, glyph pixels, superscript placement, paging,
verse-number toggling and Find against local source references. Raw LCD RAM,
font descriptors, source hashes and assertions are retained in workspace
.research-work/bible-compression/large-schoolbook-v3, large-times-v3 and
large-helvetica-final.
