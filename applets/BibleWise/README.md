# BibleWise

BibleWise is a Bible reader for AlphaSmart Neo. It includes a complete translation,
word and phrase search, verse lookup, selectable reading fonts, and copying to
AlphaWord with a citation. KJV is the default translation.

## Getting started

Open BibleWise from the applet menu. Use **Space** to page forward,
**Shift+Space** to page back, and **Find** to search or enter a reference such as
`John 3:16`. Press **F** to choose a reading font or **?** for help.

The right-hand sidebar shows your book and chapter. Loading and searching display
a lightened page; **Esc** cancels a search. Search-result and copy notices disappear
automatically or can be dismissed with a key.

## Controls

| Control | Action |
|---|---|
| Space / Shift+Space | Next / previous page |
| Cmd+Down / Cmd+Up | Next / previous page |
| Arrows, Home, End | Move the reading cursor |
| Shift+movement | Select text |
| `,` / `.` or `[` / `]` or `<` / `>` | Previous / next chapter |
| Option+Left/Right or Option+Up/Down | Previous / next chapter |
| Find | Search or jump to a reference |
| Cmd+Find / Shift+Cmd+Find | Next / previous search match |
| F | Choose a reading font |
| V | Toggle verse numbers |
| I | Toggle italics |
| H | Toggle headings |
| Ctrl+C | Copy selected text, or the current verse if nothing is selected |
| ? | Help |
| Esc | Leave Find or Help, cancel a search, or dismiss a notice |

Ctrl+Find also finds the next match; add Shift for the previous match.
Cmd/Ctrl+G and Shift+Cmd/Ctrl+G are alternatives. Cmd/Ctrl+F and `/` open Find;
N and P repeat the search forward and backward. Ctrl/Cmd+I and Ctrl/Cmd+H also
work for the display toggles. Ctrl+Alt+Cmd+F is an alternative font shortcut.
Option is Alt on a PC keyboard.

The cursor is initially hidden to keep the page uncluttered. Arrow movement
reveals it; paging and jumps hide it again. Chapters are separate pages of text:
use a chapter shortcut to continue beyond a chapter's beginning or end. The first
and last chapters do not wrap around to each other.

## References and search

Find accepts both references and search terms. Enter starts the lookup or search;
Esc returns to reading.

| Example | Result |
|---|---|
| `John 3:16` | Open and select the verse |
| `Ps 119` | Open the beginning of the chapter without selecting a verse |
| `1Cor 13:4` | Use a book abbreviation; `1Co 13 4` also works |
| `hypocrite` | Find that complete word, ignoring case |
| `hypocrit*` | Find words beginning with that prefix |
| `love* world` | Find both words, in either order, within a 20-word span |
| `"so loved"` | Find the exact phrase |

Common abbreviations include `Gen`, `Ps`, `Jn`, `Jdg`, `1Cor`, `1Co`, and `Phlm`.
Unique book-name prefixes also work; an ambiguous reference must be made more
specific. Spaces and periods in the book name are optional, as in `John3:16`.
A book name without a chapter number is treated as search text.

Search begins at the reading cursor and wraps once through the Bible. BibleWise
selects one result at a time; use next/previous match to continue. “Search wrapped”
marks a result beyond the end or beginning, and “Not found” means the whole Bible
has been checked. Nearby matches can cross verses within one chapter. Headings
are searchable and count toward the word distance, even when hidden.

Words match exactly unless they end in `*`; there is no automatic plural, tense,
synonym, or spelling expansion. Punctuation separates words, except apostrophes
inside words. Straight and curly apostrophes match each other. Quoted phrases
cannot contain wildcards or be combined with unquoted terms. Queries may contain
up to eight words and 32 characters.

Find remembers text searches, including a cancelled entry. Open Find and press
Enter on the unchanged query to find the next match, or edit it for a new search.
The input supports typing and Backspace, rather than arrow-key editing or
select-all. Successful references clear the input.

## Fonts and formatting

F opens the reading-font picker. Use Up/Down to choose a family, Left/Right to
choose a size, and Enter to accept. Esc leaves the font unchanged. This choice
only affects BibleWise, not AlphaWord's font.

On first use, BibleWise prefers an installed five-line reading font, followed by
six-, four-, and three-line sizes. Within each size, it prefers Book, Serif, Sans,
then Mono. Without one of these fonts it uses the built-in 6×16 font.

Headings, paragraphs, poetry line breaks, indentation, bold, italics, and small
capitals are shown where supplied by the translation and supported by the font.
The BetaWise Book, Serif, Sans, and Mono packages support the additional styles.
Vendor and Terminal fonts show ordinary letters in place of small capitals.
Unavailable bold or italic faces use the regular face.
Verse numbers use superscript digits; V hides them if preferred. I and H toggle
italics and headings while retaining the current view and selection as closely
as the new line wrapping allows.

## Copying and returning to reading

Select text with Shift+movement and press Ctrl+C, then paste it into AlphaWord.
BibleWise copies plain text followed by a citation, for example
`John 3:16-17 (KJV)`. Verse numbers and formatting commands are omitted.
Visible headings within a selection are included; hidden headings are omitted.
When the selection omits text at the beginning or end of a cited verse, `...` marks that
omission. With no selection, Ctrl+C copies the whole current verse.

Your chapter, reading position, selection, font, and display preferences are
retained while switching applets or sleeping. Returning may briefly lighten the
page while the chapter is recreated. The temporary chapter file is deleted when you
leave BibleWise. A full reset does not guarantee recovery of your position or
preferences.

Notes, bookmarks, footnotes, cross-references, interlinear display, general ebook
loading, and a list of all search results are not available.

## Build and try in MAME

From the workspace root, initialize the pinned sources before building:

```sh
git -C betawise submodule update --init
make -C betawise/applets/BibleWise
make -C betawise/applets/BibleWise VERSION=NKJV
```

The default output is `betawise/applets/BibleWise/build/KJV/BibleWise.OS3KApp`.
NKJV produces `betawise/applets/BibleWise/build/NKJV/BibleWise-NKJV.OS3KApp`.
The pinned upstream data also supports ESV, NIV, NASB, and CSB through `VERSION=`.
Translation builds share applet ID **0xA1B1**, so install one at a time. This bundle
targets Neo; it does not fit the stock AS3000 ROM.

To prepare disposable emulator storage and print a MAME command:

```sh
python3 betawise/tests/mame/asneo/run-biblewise.py --version NKJV --prepare-only
```

The command opens a window at 4× size without smoothing or injected keys. The demo
includes the available BetaWise and vendor fonts.

Compression, RAM usage, validation procedures, firmware findings, and archived
experiments are documented in [reader development and research](../../research/bible-reader/README.md).
See also [font packages](../../fonts/README.md).
