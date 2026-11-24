# BibleWise

A Neo Bible reader using the native text editor and one app-owned chapter file.
The sole production representation is ASCII phrase-Huffman text with a raw
front-compressed dictionary, an eight-bit Huffman lookup, grammar pruning and the
Full packed word/chapter index. Dictionaries and indexes stay in ROM.

## Build

From the workspace root:

```sh
make -C betawise/applets/BibleWise
make -C betawise/applets/BibleWise VERSION=NKJV
```

KJV is the default and produces `BibleWise.OS3KApp`. The pinned `upstream/`
submodule also supplies NKJV, ESV, NIV, NASB and CSB. Other builds are named
`BibleWise-NKJV.OS3KApp`, etc. All share applet ID **0xA1B1**, so install one
translation at a time. The workspace publishing target selects KJV only.

Conversion happens before compression: known typography becomes ASCII; unsupported
characters fail rather than disappearing. Each translation trains its own phrase
rules and Huffman model. Generated data, checksums, navigation declarations and
objects stay under ignored `build/` directories. A normal build imports no research
modules and offers no codec, index, viewer or profiling alternatives.

## Reading and navigation

| Control | Action |
|---|---|
| Find / Cmd+F / Ctrl+F | Find words or jump to a reference, e.g. `John 3:16`, `1Cor 13:4` |
| Arrows, Home, End | Native caret movement; Shift extends selection |
| Cmd+Up/Down or Space / Shift+Space | Native page backward/forward |
| Option+Up/Down or Option+Left/Right | Previous/next chapter (`[` / `]` remain aliases) |
| Cmd/Ctrl+Find or Cmd/Ctrl+G | Find next; add Shift for previous |
| V | Show or hide superscript verse numbers |
| Ctrl+Alt+Cmd+F | Installed-font selection dialog |
| Ctrl+C | Copy selected text, or current verse with no selection, with citation |
| `?` / H | Show the system-font help screen |
| H / Cmd+H / Ctrl+H | Concise system-font command reference |
| Esc | Cancel input/search or dismiss a notice |

Find uses the ROM `TextBox()` directly in the old four-line 6×16 system-font
console. There is no custom input editor, focus controller or form-field list.
The prompt and brackets leave 32 characters on the 40-column native input row.
Backspace edits the native input; Enter accepts and Esc returns to reading.
The query buffer stays in A5, so opening Find again retains the draft, including
a cancelled query. Successful references clear the entry. Chapter-only references, including
explicit verse zero, open at the chapter beginning without selection. Enter on an
unchanged retained search finds the next match; editing it starts a new search.
The examples are `"so loved"`, `love* world` and `John 3:16`.
The adjacent hints show Enter/Esc and the reading-view Cmd/Ctrl+Find command.
Validation errors remain on the bottom line while TextBox permits correction.

Before a search starts, the chapter is redrawn. Escape cancels search back to
that reading view; Find reopens the retained query. This includes quote/wildcard
syntax and does not allocate a separate query file.

References accept unique canonical prefixes and common abbreviations, including
`1Cor`, `1Co`, `Jdg`, `Jn`, `Ps` and `Phlm`, with spaces/periods ignored in the book
name. `John3:16` also works. A book without chapter numbers, such as `John`, is
searched as text. Recognized but invalid/ambiguous references are rejected.
Numeric book IDs remain undocumented compatibility. The applet includes no spell
checker, thesaurus, or dictionary data; those vendor screens were UI references.

The native editor handles wrapping, caret movement, selection and scrolling.
Wrapping stays anchored at chapter start; jumps place the caret on the target
without inventing a new paragraph layout. Verse references select the whole
verse with the caret at the beginning. Short verses are made wholly visible;
verses longer than a screen open at their beginning. Scrolling does not concatenate chapters
or books. The right sidebar reserves twelve pixels, leaving a 252-pixel native text
viewport. It uses `SYS_INT_GET_SMALL_FONT_PTR`, the ROM 9-pixel small/dialog font;
there is no embedded sidebar font or dependency on an installed Terminal font.
Characters are rotated into a small bitmap strip at draw time. The sidebar shows
book abbreviation and chapter, e.g. `1 Cor 13`. Loading shows the destination
chapter over the stippled body. Search adds a static centered Searching notice and five bouncing geometric
dots (one pixel, 3x3 cross, 3x3 square) updated every 250 ms. The
black sidebar spans all 65 LCD rows independently of body font height.

Copy/search-result notices retain their centered inverted 6×16 presentation on
a stippled text view. Chapter-navigation hints remain in Help for now.

The caret is hidden on load, chapter/reference/search jumps and applet resume.
Ordinary arrow movement exposes it. Space/Shift+Space and Neo Cmd+Up/Down paging
hide it again. Search selects the complete matching word/phrase or the nearby
span, including intervening text. Its native caret stays at the selection end
and remains hidden until arrow navigation. Next uses the selection start; previous uses its final word and compares
match endpoints. The current selection is excluded even after wrapping. Nearby
search retains its rolling match context to preserve overlaps and suppresses
larger repeated spans beginning at the same word.

Body text uses the selected installed Neo font. Verse numbers use a sparse,
unregistered private fourth face, without changing installed fonts. No space is
inserted after the number. Tiny/dense fonts remain selectable; V hides numbers
if their relative size is distracting. Small uses AlphaWord's six 11-pixel rows: the sixth descenders reach physical row
65, and the final blank glyph row is clipped. Other fonts use complete rows
within 65 pixels, including five 13-pixel Medium rows. Verse-number placement is raised for Small, Medium and Large.

## Search

Find/Cmd+F opens the unified form. Ctrl+F, F and `/` are convenience aliases.
Unquoted words are matched in any order within a span of at most 20 words,
including across verse boundaries within a chapter. A trailing `*` expands a word
prefix: `faith work*`. Put double quotes around the entire query for an exact
phrase: `"faith works"`. Quoted phrases do not allow wildcards; mixing quoted
and unquoted terms is not supported in this prototype. The former same-verse
mode and mode/distance controls are no longer exposed by the applet.

Search ignores case. Terms are exact unless suffixed with `*`: `show*` includes
archaic endings; `show` does not. This applies independently to each of up to eight
terms. The native one-line query field is limited to 32 input characters; the search
backend still supports up to eight terms. Punctuation separates words;
internal apostrophes are retained. Leading/infix stars are rejected. Repeated
terms require distinct occurrences; a single word cannot satisfy both `be*` and
`bel*`. There is no automatic stemming, synonym expansion or typo correction.

Enter searches from the reading cursor, including its current word.
**Cmd+G / Shift+Cmd+G** searches next/previous. N/P remain convenience aliases.
Cmd+Find opens Find rather than finding again; AlphaWord itself assigns it to its typing timer. Searches respect manual cursor movement and chapter jumps, wrap once across
Bible boundaries, and stop after one result. A wrapped result briefly displays
“Search wrapped” in a centered notice. An unsuccessful search stops after one
complete pass. Previous rescans
candidate chapters forwards and retains the last qualifying match; it has no
32-result history limit. Work is cooperative and Esc can cancel it.

The Full index filters candidate chapters; phrase/proximity verification still
requires decoding. The backend iterator can continue yielding results, but there
is no all-results list or matching-book/chapter menu in the UI.

## Clipboard and saved position

An explicit selection copies the selected Bible text without verse-number/font
control bytes, then appends its verse or verse-range citation. ASCII `...` is
added at the beginning/end only when text has been omitted from the first/last
cited verse. Without a selection, Copy retains the whole-current-verse fallback.
A centered inverted 6×16 “Copied” notice lasts two seconds; notices preserve the
sidebar and restore the page/selection. “Not found” and “Search wrapped” retain
the same presentation.
Chapter decoding, verse-number rerendering and search display a white stipple
and animate the sidebar bullet at cooperative checkpoints; blocking native
wrapping retains a static indicator.

The chapter file is managed with an editable native descriptor because font
replacement requires it. The applet only forwards movement keys, so typing,
deleting, cutting and pasting cannot edit Bible text. There is one chapter file,
no second full-chapter buffer and no separate position/status file. The in-RAM
verse-offset table speeds same-chapter jumps. `TextEditorSavePosition` preserves
the viewport when switching applets; chapter, fonts, number visibility and query
state remain in A5. A full reset does not promise position recovery.

Only plain Bible text and generated verse numbers are included. Source italics,
small caps, headings, footnotes, annotations and cross-references are not rendered.
Notes, bookmarks, interlinear views, EPUB/general-book loading, and all-results
menus are not implemented. Stock AS3000 ROM capacity is insufficient for this
bundle; this targets Neo.

## Validation and archived experiments

```sh
python3 betawise/tests/biblewise/check.py --output /tmp/bible-host-check
python3 betawise/tests/mame/asneo/check-biblewise.py --case reader --output /tmp/bible-reader-check
python3 betawise/tests/mame/asneo/check-biblewise.py --version NKJV --case search --output /tmp/bible-search-check
```

MAME tests use disposable flash/RAM and deterministic local source/font/cursor/
controller assertions. `TESTING=1` builds a separate image under `build/` with
read-only RAM probes for the harness. Production contains no probe records,
benchmark loops, experimental hotkeys or test font selection. Forms and help use 6×16 ROM system-font glyphs directly, independently of
the selected reading font or installed BetaWise fonts.

[Cleanup results and size comparison](../simplification.md)
record the accepted builds. [Archived implementations and regeneration instructions](../prototype/REPRODUCE.md)
preserve streaming, alternate codecs/indexes, lookahead, private layout calls and
all earlier measurements outside production.

To prepare disposable MAME storage and print a command without starting MAME or sending keys:

```sh
python3 betawise/tests/mame/asneo/run-biblewise.py --prepare-only
```

The printed MAME command has no autoboot script or injected keys. It uses a
792x195 window, integer 3x scaling and no bilinear filtering.

The app-owned chapter file is closed, not deleted, on focus loss;
`TextEditorSavePosition` preserves its native cursor/viewport metadata. It is
erased/repopulated for a different chapter or verse-number representation. The
256-byte staging buffers are stack locals in chapter decoding, word-position
scans and clipboard copying. Decode helpers borrow the local buffer; there is
no permanent A5 scratch buffer. They batch file syscalls and hold no state
between operations. Loading is
whole-chapter and foreground; there is no background page-lookahead loader.

The native TextBox has append/backspace editing, not insertion-caret movement
or selection. There is no select-all/type-to-replace flag. Any such initial
replacement policy would need an applet wrapper; full arrow editing would need
a different input implementation. Native behavior is retained for now. Find retains text queries and clears successful verse references. Cmd/Ctrl+Find
and Cmd/Ctrl+G use the last accepted search through its separate search context.

The current state audit removes another 894 bytes of persistent A5 storage.
Decoders, form length/mode, font lookups and notice text are operation-local;
book-name tables are inline ROM arrays rather than relocated pointer arrays.
Chapter loading stipples the body and shows the destination in the sidebar.
Only search animates: five simple bitmap dots bounce through eight phases,
with 1-pixel, 3x3 cross and 3x3 square sizes. Animation does
not rotate glyphs. Numeric constants use defines; key dispatch uses switches.

The disposable launcher additionally installs six-row ASCII test versions of
Century Schoolbook, Helvetica and Times. See
[font provenance and coverage](../reader-fonts/README.md).

The sidebar covers all 65 LCD rows regardless of the native editor's rounded
viewport height or selected font. Stippling captures the 252x65 text area into
a 2,268-byte stack bitmap and draws it in one call; it does not allocate A5 RAM.

Not found and Search wrapped replace Searching directly in its fixed notice
rectangle. They do not restore, clear, restipple or redraw the chapter first.
When the notice expires or a key dismisses it, Not found restores the reading
view; Search wrapped opens and selects the deferred match. Copy or app switching
also resolves the deferred result before using/saving the reading position.

Explicit verse-zero syntax was subsequently rejected: the zero value is only
an internal sentinel for a chapter-only reference. Host reference coverage
passes 102 cases, and the updated 15-check notice suite rejects Ps 119:0 while
retaining unselected chapter-only navigation. Formatting experiments are host
research under ../formatting; production rendering remains plain.
