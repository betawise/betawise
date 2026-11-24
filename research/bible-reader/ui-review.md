# Native reader UI review, 23 November 2026

The proposed controls/dialog changes below were subsequently implemented in
[the unified Find revision](unified-find.md). This document retains the original
vendor evidence and design discussion.

## Implemented in this iteration

1. Verse digits: Small (11 px) moved from y=3 to y=1 within each line;
   Medium (13 px) and Large (16 px) moved from y=3 to y=2. Other height bands
   retain their previous positioning. The sparse font has a separate Small band.
2. Copy feedback is just **Copied**, centered in the ROM system font, inverted,
   with no box/border or footer. It expires cooperatively after 1,000 ms and
   restores the shared native screen snapshot, including selection and cursor.
3. Small matches original AlphaWord: six rows at pitch 11, editor geometry 66,
   last descenders at physical y=64 and only the final blank glyph row clipped.
   The other fonts keep complete rows within 65 pixels, including five Medium rows. Native redraw does not
   clear the unused margin, so explicitly clear that margin when leaving a
   taller viewport or a waiting/input overlay. All 65 physical rows are tested.
4. Waiting feedback: white stipple over the old display, an inverted system-font
   `Working...` label and eight-position spinner. Stipple is applied with one
   264-byte strip at a time, not a whole-screen applet framebuffer. Spinner
   redraws are limited to once per 150 ms at cooperative decode/search checkpoints.
   Blocking native wrap cannot animate until it returns; the waiting image stays
   visible. Native routines may repaint over it as they complete.
5. The primary advertised Find Again shortcut is now Cmd+G (Shift+Cmd+G previous).
   Existing extra aliases remain. No established native cursor/selection keys
   have been reassigned.
6. Removed the unused DrawRectangle SDK helper/declaration and its specific test;
   retained the independently used DrawLine implementation and its passing test.

Dialog layout, the existing Go To line/overlay, the help screen and chapter-key
semantics are deliberately unchanged pending this review. No new boxes were added.

## Original vendor evidence

The pinned NEO 3.21 firmware, original AlphaWord Plus, Small USA spell checker
and Small USA thesaurus were installed in disposable flash/RAM. The reproducible
capture/verification program is [vendor_ui.py](vendor_ui.py). Four full 264x65
screens match explicit expected text and original vendor font glyphs with zero
pixel differences. Cursor geometry is recorded before a normal firmware hide;
its return and restored mode are checked, three identical controller samples
are retained, and guest registers/scratch RAM are preserved. Thesaurus's input
loop can be captured at the verified `rts` instruction 0x437438 as well as the
usual idle entry 0x426758; no extension-word PC is restored.

Private accepted evidence: `.research-work/bible-compression/vendor-ui-original-v3/`.
The earlier conservative idle-only captures are retained as incomplete trials.
Source/manual corroboration: `Ghidra/Alphasmart Neo/SmartApplets/alphawordplus.os3kapp`
and the workspace NEO 2 manual text `.research-work/os3k-clean/neo-manual.txt`,
printed pages 29–36 (Find, Replace, sections, spell check, thesaurus), with the
keyboard summary at printed pages 232 onward.

All four dialogs use a **fixed 6x16 ROM system font**, independent of the reading
font, and clear the screen. They use text prompts and selection markers, not
bordered windows. Captured wording/layout, with blank padding omitted:

```
  Find: [                ]
  Press enter to search in "File 1",
  Option-enter to search in all files,
  Cmd-G to find again, esc to exit.
```

```
          Find:[                         ]
  Replace with:[                         ]
  (*)whole word( )match case( )replace all
   (tab=next field, cmd-H=help, esc=exit)
```

Spell check shows `Select word and enter OR` with the suggestion list, a
font-defined selection arrow, and `I=ignore`, `E=edit`, `C=context`, `A=add` on
the right. Thesaurus input says `Enter a word for the Thesaurus to / look up:`,
a bracketed field, and `(Press esc key to exit)`. The manual specifies arrows
and Enter for category/synonym lists; Clear File clears the lookup text. These
are dictionary data applets invoked by AlphaWord, rather than a separate generic
Dictionary UI on which to base a different convention.

**Notices:** the manual says unsuccessful Find displays a brief message; spell
check reports completion then returns to the document. The original binary has
`Find text not found.` and `File spell check complete.` This establishes brief
feedback precedent, not a measured one-second timeout or a vendor Copied toast.
The chosen one-second Copied treatment is our design.

**Keys:** Find or Cmd+F opens Find; Cmd+G finds again; Ctrl+Find opens Replace;
Cmd+Find is the typing timer. Ctrl+F opens the file selector. Cmd+S opens sections;
Cmd+H/Ctrl+H opens command/help lists. Native Cmd+Up/Down pages, Cmd+Left/Right
moves to line ends, Option+Left/Right moves by word, Ctrl+Up/Down by paragraph.

## Recommended next UI design (not implemented)

- **One Find entry point:** accept either reference or text. Recognize a known
  book/alias plus chapter and optional verse, e.g. `John 3:16`, `1Cor 13`,
  before treating it as text. Validate recognized-but-invalid references rather
  than silently searching for them. A bare `John` should remain a word search.
  Keep G/Ctrl+G as optional old reference aliases, without making users learn them.
- **References:** current code accepts unique literal book-name prefixes, so
  `1 Co 13:4` works but `1Co 13:4` and `1Cor 13:4` do not. Normalize spaces and
  add an explicit conventional alias table (including Jdg/Jud to disambiguate
  Judges/Jude). Keep numeric book IDs as undocumented compatibility; do not
  advertise `1 3 15` or prioritize it in the unified field.
- **Full-screen system-font form:** one bracketed input line, one exclusive
  choice row `(*)Verse ( )Phrase ( )Nearby`, one short description/example line,
  and a context-sensitive footer. Down enters the choices, Left/Right changes
  choice, Up returns to text; Tab remains optional. In the text field Left/Right
  edits the cursor, so mode selection must not hijack it. Enter accepts, Esc
  returns, Clear File clears input. For a recognized reference, Enter goes there
  and search mode is irrelevant. No borders, separator lines or box helpers.
- **Inversion:** render normal glyphs, then invert their region with native
  RasterOp/ROP_DSTINVERT. RasterOp also supports source XOR (ROP_SRCINVERT).
  There is no need for another font or an XOR-specific string renderer.
- **Search keys:** advertise Find/Cmd+F and Cmd+G; Shift+Cmd+G is our backward
  extension. Ctrl+F may remain an unadvertised desktop convenience, with the
  explicit understanding that AlphaWord uses it for file selection. Do not
  advertise Cmd+Find as a native Find Again convention.
- **Transient location, not a permanent bar:** briefly invert one existing body
  row for `John 3` after paging/chapter changes and `John 3:16` on a search hit.
  Overlaying it need not alter wrapping or page height. Use shorter book names
  with large fonts; otherwise a whole status line may not fit. Show next/previous
  hints in context, using the system font when necessary for legibility.
- **No speculative match total:** Full postings identify chapters containing
  terms, not occurrence counts, same-verse hits, or verified phrase/proximity
  hits. Summing candidate verses produces a loose, misleading upper bound.
  An ordinal is only meaningful along a maintained result traversal; a manual
  jump/revised query invalidates it. Prefer location and `Cmd-G next` /
  `Shift-Cmd-G previous`, shown briefly after search, without eager enumeration.
- **Chapters:** Option+Up/Down is available without taking AlphaWord's paging,
  word, sentence or paragraph keys. Advertise it; retain brackets only as legacy
  shortcuts. On Up/Down at a boundary, show `End of chapter — Option-Down: next`
  (ASCII wording in the actual UI). Avoid double-tap navigation: key repeat can
  make an accidental chapter jump. Keep the caret/selection within the current
  chapter until an explicit chapter command.
- **Help:** no forced first-run help screen. Use a brief initial location/key
  hint and the above contextual footers. If command reference help remains,
  put it on `?`, Cmd+H and Ctrl+H, in the system font; H can remain an alias.
  Remove the current dense terminal-glyph help once those hints exist.

## Search scope usefulness

Same verse is not forced by the index: **all three modes use the same chapter
postings**, with decoded verification. A verse is a useful citation/concordance
unit, whereas a 20-word window can cross verse boundaries and miss more distant
words in a long verse. The default all-words mode is not an exact phrase.
Use the labels **All words in one verse**, **Exact phrase**, **Nearby (20 words)**,
with a one-line description of the selected mode.

KJV source-oracle experiment, case-insensitive exact terms:

| Query | Same-verse results | Nearby windows |
|---|---:|---:|
| faith works | 15 | 20 |
| kingdom God | 95 | 106 |
| mercy truth | 22 | 24 |
| Jesus Christ | 256 | 282 |
| in the beginning | 36 | 49 |

These counts use different result units: one result per verse versus nonoverlapping
nearby windows, so neither column is a subset count. `faith works` illustrates
why both help: Nearby finds the relation across Ephesians 2:8–9; same-verse finds
Revelation 2:13, where the terms are farther apart than 20 words. Exact phrase is
best for a remembered quotation; Nearby helps when the user remembers related
words but not their order or exact verse boundary. Full results and examples are
in `.research-work/bible-compression/ui-search-usefulness.json`.

## Reader acceptance artifacts

All paths under private `.research-work/bible-compression/`:

- `ui-small-six-lines`: initial 42-case geometry run, verified across 65 rows.
- `ui-reader-small-accepted`: 43 reader cases, including automatic notice expiry.
- `ui-reader-medium-accepted`: 43 reader cases, five Medium rows, and exact spinner/label checks.
- `ui-feedback-large`: original vendor Large font, same reader suite.
- `ui-feedback-search-accepted`: search modes, next/previous and active cancellation.
- `ui-feedback-timer`: five focused cases for expiry, recopy and navigation dismissal.

The first Medium feedback trial exposed leftover stipple/dialog pixels below its
then-52-pixel native viewport. The final code explicitly clears that unused margin;
no expected pixels were relaxed. Raw failed trials remain available. Early search
trials also exposed a test-observation regression when waiting feedback replaced
ShowNotice: the search-active probe needed its normal observation call. The final
call is test-only in release and does not change search behavior.

Timed-notice testing also caught modifier-key press notifications dismissing a
fresh Ctrl+C notice. Modifier-only events are now ignored for dismissal; a normal
navigation/action key restores the snapshot before acting. Opening a chapter or
font-driven rerender cancels any pending restoration, so a stale snapshot cannot
replace the new display later.
