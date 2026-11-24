# Unified Find and native navigation UI

This implements the dialog/navigation portion of the user's earlier UI list.
The earlier instruction to inspect vendor dialogs first was interpreted too
broadly as a hold on implementation; the user clarified that these changes
should be present in the revised applet. Spell check/thesaurus remain strictly
layout references. No dictionary data, spelling suggestions or thesaurus feature
was added to the production applet or its interactive launcher's installation.

## Current behavior

- Find/Cmd+F opens a full-screen, four-row ROM system-font form. The old
  partial-screen Go To dialog, overlay lines, G/Ctrl+G jump binding and terminal
  glyph help were removed. Ctrl+F, F and slash remain Find conveniences.
- The same field accepts search text and references. `John 3:16`, `John3:16`,
  `1Cor 13:4`, `1Co 13 4`, `1 Cor. 13:4`, `Jn`, `Jdg`, `Ps`, `Jas`, `Phlm`,
  and unique canonical prefixes work. Book-name spaces/periods are ignored.
  A bare `John` is a word search. Recognized invalid or ambiguous references
  show a full-screen system-font error instead of starting a misleading search.
  Numeric book IDs remain compatibility input, without being advertised.
- Left/Right, Home/End and Backspace edit the field; long text scrolls
  horizontally. Clear File empties it. Down focuses the choices, Left/Right
  selects one and Up returns to input. Enter accepts; Esc cancels. Optional
  Tab/Shift+Tab still cycles modes, without requiring it.
- Verse, Phrase and Nearby remain available for inspection. No quotation-mark
  syntax or change to search semantics was introduced. The mode explanation
  distinguishes all words in one verse, words in order, and an unordered
  20-word window. The user will decide whether a scope should be removed later.
- Cmd+G/Shift+Cmd+G finds next/previous. Cmd+Find is no longer Find Again;
  it follows the Find-key path. Native paging/selection commands are retained.
- Option+Up/Down changes chapters. Brackets remain unadvertised aliases.
- `?` overlays a brief inverted location bar, with the book/chapter centered
  and `Opt-Up` / `Opt-Dn` at the left/right edges. It is not a modal dialog.
  Reference/search navigation includes the target verse. Chapter changes,
  paging, Home/End, and attempts to move beyond a chapter boundary show the bar
  too. It restores the page after 1.5 seconds, or before a subsequent action.
  It uses the system font and a shared screen snapshot, without reserving a
  row or altering native wrapping/page height.
- H/Cmd+H/Ctrl+H provides a short four-row system-font command reference.
  No forced first-run help was added. The Find form and location bar supply
  contextual instructions. One-second Copied feedback and waiting feedback
  from the preceding revision are retained.

Native body fonts, six Small rows, five Medium rows, superscript placement,
selection/citation copying and native saved reading position are retained.
The compression and Full index resources did not change.

## Deterministic acceptance

Private evidence under `.research-work/bible-compression/`:

| Run | Checks |
|---|---:|
| `unified-ui-small-v2` | 50 reader/UI cases with original Small font |
| `unified-ui-medium` | 50 reader/UI cases with original Medium font |
| `unified-ui-search` | 18 source-oracle search cases, all three modes, next/previous and cancellation |
| `unified-ui-references-v2` | 99 host cases against the actual production parser functions |

The reader suites assert every LCD pixel in all 65 physical rows, including
full-screen Find, typed reference text, field editing, arrow-selected modes,
errors, status-bar center/edge text, automatic expiry, native selection, font
switching and AlphaWord resume. They independently check raw input/cursor/mode
state, native caret/viewport geometry and controller flags. The harness hides
and restores the cursor through firmware and retains three identical RAM
samples. Full-screen forms are checked for their reset console cursor; native
screens and transient bars retain independent editor cursor assertions.

Search cancellation remains 0.150 emulated seconds for the injected short Esc
press. Explicit waiting spinner/label regions remain pixel-verified. No model
vision or screenshot inference was used. Disposable flash/RAM protects saved
sessions. Failed initial build/probe setup trials are retained separately.

The host reference test compiles the actual lookup/parser code with the generated
navigation and verse counts. Its independent expected cases cover all 66 full
book names, joined/spaced/punctuated abbreviations, numeric compatibility,
ordinary search phrases, ambiguous names, invalid chapters/verses and overflow.

[Machine-readable results](unified-find-results.json) record the accepted checks
and final KJV image hash/size. The interactive launcher rebuilds this current
image automatically; rerun it to install the updated applet into fresh MAME
storage rather than reopening an old flash image.
