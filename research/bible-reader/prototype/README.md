# BibleReader for Neo

A ROM-resident Bible reader using the native Neo editor for word wrapping,
font selection, caret movement and selection. Default output:
**BibleReader.OS3KApp**, KJV, applet ID **0xA1B1**.

The applet decodes one chapter into its own file, then reuses it for movement
and jumps within that chapter. There is no second full-chapter RAM buffer.
The production decoder needs **236 bytes**; the complete applet requests about
**2,874 bytes** of static RAM, with file storage and firmware stack additional.
The longest current KJV plain chapter is 12,992 bytes. Verse markers and the
native editor's 512-byte gap add to file storage.

The KJV text resource is 1,007,155 bytes and the chapter search filter is
368,039 bytes. Including indexes, local superscript fonts and native code, the
applet is about **1,432,390 bytes**. This targets Neo: the stock AS3000 has only 736 KiB
of shared applet ROM space. Physical-device power/current measurements remain
outstanding; current acceptance testing uses original Neo 3.21 firmware in MAME.

## Controls

| Key | Action |
| --- | --- |
| G or Ctrl+G | Reference entry: `John 3:16`, `John 3 16`, or `43 3 16`; unique book-name prefixes work |
| Find, Ctrl+F, Cmd+F, F or / | Search; Tab selects Same verse / Exact phrase / Nearby; * expands a word |
| Cmd+Find / Shift+Cmd+Find; Cmd+G / Shift+Cmd+G (also N / P in the native reader) | Next / previous search result |
| Arrows, Home, End | Native editor movement; hold Shift to select |
| Space / Shift+Space | Page forward / backward |
| [ / ] | Previous / next chapter |
| V | Show / hide superscript verse numbers |
| Ctrl+C | Copy the current verse or whole verses touched by the selection, with citation |
| ? | Show book, chapter, verse and translation on demand |
| H | Help |
| Esc | Dismiss an overlay or cancel entry/search |
| Ctrl+Alt+Cmd+F | Native installed-font selection dialog |

Wrapping is anchored at chapter start. A reference jump preserves that layout,
so its verse number may appear within a line. The target caret is kept visible;
it is not forced onto a new first line. Font changes retain a verse anchor and
reflow the chapter. There is no permanent status bar or timed flashing overlay.
Normal arrows move the native caret; they scroll when it reaches the viewport
edge. Page commands are convenient for continuous reading.

Superscripts use an **unregistered local fourth face**, with digits in unused
character slots. Each selected body-font height has properly padded bitmap slots;
this does not alter installed fonts or register a new AlphaWord font. Body text
uses the selected installed font through the firmware editor. Numbers have a
lower baseline and no inserted space after them. The chapter file is initialized
empty and its font faces installed before text is inserted, avoiding a transient
display of marker characters. Whole rows are used and unused bottom pixels cleared.

The five vendor proportional fonts (11, 13, 16, 21 and 32 pixels high) and the
6-pixel Tiny font each pass 36 deterministic screen/state checks. Dense fonts
remain available: their verse numbers are relatively large; V hides them.

On extended Neo firmware, G uses the native partial-screen input dialog along
the bottom edge. Type a reference, use Backspace or Clear File to correct it,
and press Enter. Left/right do not edit within this native field. Older firmware
falls back to the applet reference overlay.

Ctrl+C snaps selection to verse boundaries. Clipboard data is ordinary ASCII
text followed by a citation such as `John 3:16 (KJV)`, or a verse range. Superscript
glyph codes and native formatting markers are excluded. Paste normally into
AlphaWord. Typing, deleting, cutting and pasting into the Bible are blocked by
the applet's message whitelist; its private chapter is managed with an editable
native descriptor because the firmware rejects font replacement on a read-only
descriptor. Chapter, number visibility, search and editor state stay in A5 globals.
On leaving, `TextEditorSavePosition` saves the viewport in the chapter file;
returning reopens that file without decoding the chapter again. There is no
second status file. Ordinary applet switching is supported; `MSG_INIT` resets
A5 state. Notes and bookmarks are deferred.

## Search behavior

Search is case insensitive. **Same verse** (default) requires every query word,
in any order, in one verse. **Exact phrase** requires adjacency and query order.
**Nearby** requires every term in a 20-word span, in any order, and can cross verse
boundaries within a chapter. Punctuation separates words; apostrophes are retained.
There is no stemming, fuzzy matching, synonym expansion or typo correction.
Words are exact unless suffixed with `*`: `believe*` also matches `believed`
and `believeth`. Leading/infix wildcards are rejected. Repeated terms require
distinct occurrences. Same verse emits once per verse; Nearby emits nonoverlapping
windows; Exact phrase preserves overlapping occurrences.

A ROM word-to-chapter filter intersects candidate chapters before decoding.
Search compares normalized dictionary IDs directly, avoiding spelling each word,
and advances in up to 200 ms per native idle callback, checking for queued keys every 64 search
steps. It places
the caret at each matching word, including repeated matches within the same verse.
New queries start at the reading cursor, including its current word. Cmd+Find
(or Cmd+G) finds the next occurrence; Shift+Cmd+Find (or Shift+Cmd+G) finds
the previous one, including after manual movement/jumps. There is no 32-result
history limit. Searches stop at Bible boundaries without wrapping. Backward
search scans candidate chapters forward, retaining their last qualifying match.
There is no up-front full-Bible scan or precomputed global match count. Esc can
cancel an active search. Long/common searches can still require substantial
work: a full no-hit scan of `Jesus Jesus` takes about 18.6 CPU seconds in MAME,
with additional idle scheduling time. The index is a chapter filter, not a
verse-level positional concordance. A tested verse Bloom filter cost more ROM
and ran slower, so it is not shipped.

## Sources and translation builds

Initialize the requested source submodule from the workspace root:

```sh
git -C betawise submodule update --init --depth 1 applets/BibleReader/upstream
make -C betawise/os3k
make -C betawise/applets/BibleReader
```

The builder converts typography/ligatures and explicitly supported fractions
and accents to ASCII **before compression and model training**. Unmapped
characters fail. The runtime then adds native formatting tokens, rather than
UTF-8. Source verse numbering is preserved, including empty omitted slots and
translation-specific additional slots. Split source verse parts are joined with
one space. Section headings, footnotes, cross-references and per-word source
styling are not currently rendered; the body is plain text with optional verse
markers. These are conversion limits, not an OCR-correction claim.

The default now uses the repo's KJV source, rather than the older research JSON.
Every translation trains its own dictionary, phrase grammar, Huffman model and
search filter. Optional builds:

```sh
make -C betawise/applets/BibleReader VERSION=NKJV
make -C betawise/applets/BibleReader VERSION=ESV
# Also supported: NIV, NASB, CSB
make -C betawise/applets/BibleReader   # return to the default KJV profile
```

Other outputs are named `BibleReader-NKJV.OS3KApp`, etc. **All use 0xA1B1** and
are alternative installations, rather than separately identified applets. The
root applet build and publication list default to KJV only. The profile stamp
rebuilds shared objects/resources when translation or reader settings change.
Unchanged source resources reuse the existing verified phrase container;
`build_data.py --retrain` forces model training again. Generated text/resources stay under `.research-work/bible-compression/reader/`;
source/codec hashes and size reports are recorded there. The submodule's README
provides source attribution and edition terms.

## Run the tested production build in MAME

From this workspace root, copy the passing streaming production session into disposable
storage, preserving the test evidence:

```sh
bible_session=$(mktemp -d /tmp/neo-bible.XXXXXX)
cp -a .research-work/bible-compression/reader7-release/{roms,cfg,nvram} "$bible_session/"
./mame/neodiag asneo -rompath "$bible_session/roms" \
  -cfg_directory "$bible_session/cfg" -nvram_directory "$bible_session/nvram" \
  -window -skip_gameinfo
```

Press Applets (host F9) and choose BibleReader-Stream if needed. This modifies only the
private copy. On a fresh checkout, first create the production session below.

## Verification and prior experiments

From the workspace root, use new output directories:

```sh
python3 betawise/research/bible-reader/check-native.py \
  --container .research-work/bible-compression/reader/kjv/container.bin \
  --source .research-work/bible-compression/reader/kjv/source.json \
  --output /tmp/bible-native-new
python3 betawise/research/bible-reader/check-search.py
python3 betawise/tests/mame/asneo/check-bible-reader.py \
  --output /tmp/bible-reader-new
python3 betawise/tests/mame/asneo/check-bible-reader.py --system-font \
  --output /tmp/bible-reader-production-new
python3 betawise/tests/mame/asneo/check-bible-reader.py --verify-only \
  --output /tmp/bible-reader-production-new
```

The native verifier reconstructs all 1,189 chapters byte-for-byte. Search tests
compare every matching word occurrence with an independent source tokenizer, including
phrase overlap and exact inflection distinctions. Both MAME profiles check
reference jumps, largest chapters, number toggling, search results, native
selection, clipboard citations, partial overlays and the real font picker.

Screen checks use independent source/font typesetting and exact full bitmap
comparisons, including superscripts and verified original-ROM system glyphs.
Cursor geometry is checked independently before the real firmware cursor-hide
call; three identical controller RAM/flag samples follow its return, then the
original mode/registers/scratch RAM are restored. Unknown/unsupported profiles,
incomplete samples and timeouts fail. Records, decoded expectations, hashes,
logs and assertion results are retained. No model inference or screenshot oracle
is used; tests stage private flash/RAM, never a user's session.

`Benchmark.c`, `READER=Benchmark`, and `check-bible.py` retain the earlier streaming
codec benchmark. See [Huffman measurements](../huffman-speed.md)
and [the original arithmetic prototype](../mame-prototype.md).
Those timings and RAM totals describe their retained artifacts, not the complete
native-editor reader with search indexes. The newer source text also differs.


## Streaming reader with cursor and selection

Streaming is the preferred reader implementation after the measured comparisons;
`READER=BibleReader` retains the native-editor implementation for comparison.
The roughly 3.8 KiB figure is static RAM for the complete reader, including its
Bible decoder/search and UI state. Firmware stack, native dialog and shared
clipboard allocations are additional. Code/navigation/runtime resources beyond
the bundled text/indexes occupy about 22.3 KB of ROM; this is not a measured
standalone layout-library size. A reusable book/Markdown renderer could share
layout, drawing, cursor and selection while omitting Bible-specific services.


```sh
make -C betawise/applets/BibleReader READER=Streaming
```

`BibleReader-Stream.OS3KApp` is an alternative installation using the same ID
0xA1B1. It uses the full packed exact chapter index and grammar pruning by
default. It requests zero files and draws original installed glyphs directly
using OS DrawBitmap/RasterOp. The current renderer repaints on viewport changes
and keeps both LCD start lines at zero, including before firmware dialogs.
It uses all 65 physical rows. There is no screen bitmap or chapter buffer.

Arrows/Home/End move the caret; Shift extends selection, Ctrl+Left/Right moves
by words, Ctrl+Home/End goes to chapter boundaries, Ctrl+A selects the chapter,
and Ctrl+C copies the exact selected text with a citation (or the current verse
when nothing is selected). Space/Shift+Space and N/P change pages. G or Ctrl+G
opens Go To; Find opens search (Tab or Shift+Tab changes its mode). Both use a centered bordered input panel
with the original ROM system font. Backspace, Clear File, Home/End and left/right
edit the field. Copied/error/location notices use the same panel style.
Cmd+Find / Shift+Cmd+Find search forwards/backwards from the reading cursor;
Cmd+G / Shift+Cmd+G remain AlphaWord-compatible aliases. V toggles superscript
numbers. Ctrl+Alt+Cmd+F opens the installed-font picker. Returning from AlphaWord
retains A5 state and reconstructs the visible page.

Wrapping is anchored at chapter start for scrolling, verse jumps and search.
The target caret appears in its natural line, which can contain preceding verse
text. Going upward does not introduce a forced short line. Font/number changes
retain the current source position. A bounded cache holds 32 compressed line
checkpoints (640 bytes plus validity flags); evicted lines replay chapter layout.
No chapter-sized file or buffer is retained.

Small now shows six rows at its original 11-pixel pitch; Medium shows five.
Remaining vertical space is distributed between lines. Fonts with a capital-letter
top inset use a one-pixel upward text origin; the display clips above y=0.
Superscripts align near the cap top and use a four-pixel-high digit design below
8 px. The 8 px terminal font and 6 px Tiny font are tested; Tiny shows ten lines.
Selection changes invert only changed spans, preserving their common highlight.
Go To/Find open without repainting the underlying text; closing restores only the
covered horizontal band. UI panels use the built-in system font even without the
Betawise font installed.

Production static RAM is 3,862 bytes with no private files. Current redraw and
UI measurements are in [reader UI revision](../reader-ui.md).
The [earlier streaming measurements](../streaming-viewer.md)
describe the historical hardware-roll prototype, not this repainting revision.

Run deterministic acceptance against private emulator storage:

```sh
python3 betawise/tests/mame/asneo/check-bible-stream.py --production \
  --output /tmp/bible-stream-new
python3 betawise/tests/mame/asneo/check-bible-stream.py --vendor-font small \
  --output /tmp/bible-stream-small-new
```

The source/font oracle checks full text pixels, selection, native caret geometry,
clipboard citations, installed-font changes, LCD start lines and flags. Tests
preserve native registers/scratch, hide the cursor through firmware, observe its
return and capture three identical raw samples. No screenshot/model inference
is used. Profile builds additionally provide benchmark shortcuts; production
builds omit them. Notes, editing and persistent bookmarks remain deferred.

## NKJV demo with every vendor font

The tested demo includes original Small, Medium, Large, VLarge and XLarge font
applets together, plus the system and terminal fonts. They remain shared installed
fonts rather than being copied into BibleReader. Start the disposable demo from
the workspace root:

```sh
bash .research-work/bible-compression/reader9-release/launch.sh
```

Choose BibleReader-Stream-NKJV from Applets (host F9) if necessary.
Ctrl+Alt+Cmd+F opens the real font picker. The test leaves Small selected.

Rebuild the applet, or create a new fully tested session:

```sh
make -C betawise/applets/BibleReader READER=Streaming VERSION=NKJV
python3 betawise/tests/mame/asneo/check-bible-stream.py \
  --version NKJV --all-vendor-fonts --production --output /tmp/bible-nkjv-new
bash /tmp/bible-nkjv-new/launch.sh
```

Output is `BibleReader-Stream-NKJV.OS3KApp`, sharing alternative-installation ID
0xA1B1. KJV remains the default translation. The NKJV model is trained for NKJV;
the source is ASCII-normalized before compression, as with KJV. This build uses
the full packed exact chapter index and grammar pruning. All 1,189 NKJV chapters
match source decoding, including reverse chapter order. The demo passes 83
source/font/LCD/cursor/selection/clipboard checks, including selecting and scrolling
with each of the five original vendor fonts in one installation. See
[current UI measurements](../reader-ui.md).

An optional `LCD_ROLL=1` comparison build restores the earlier controller-ring
scrolling primitives. It is currently accepted for the system 6×16 Psalm 119
read-through workload via `check-bible-stream.py --lcd-roll --readthrough line`
(or `page`). Normal builds default to `LCD_ROLL=0`. See the
[complete read-through comparison](../readthrough.md)
for timings, geometry differences and validation scope.

Native comparison builds accept `NATIVE_OPEN_TEST=1` (omit preliminary file
reconciliation) and `NATIVE_PAGE_TEST=1` (native Command+Up/Down paging). Both
default to zero; see [native API usage measurements](../native-overhead.md)
for accepted workload and remaining coverage.


## Native incremental-file prototypes

The existing native frontend now has four optional file-residency policies.
`NATIVE_STREAM=1` keeps a moving window, `2` appends on demand and retains the
prefix, and `3` shows a prefix then finishes it in cooperative idle slices.
`4` uses `TextScanInsert` for page-sized idle lookahead, retaining the prefix
without explicitly refreshing or repositioning the editor after each insert.
Its output is `BibleReader-NativeLookahead.OS3KApp`. See the
[lookahead measurements](../native-lookahead.md):
appends do not paint, but insertion cost still grows with the prefix.
All use native wrapping/drawing/cursor/selection. Chapter-global selections can
outlive eviction; clipboard export decodes the span and includes its citation.
Native Home/End apply to the whole chapter, not merely the current prefix.
The default `NATIVE_STREAM=0` remains the whole-chapter native reader.

```sh
make -C betawise/applets/BibleReader READER=BibleReader NATIVE_STREAM=1 NATIVE_PAGE_TEST=1 PRUNE=1 PROFILE=0 TEST_FONT=0
```

KJV remains the default. Outputs are `BibleReader-NativeWindow.OS3KApp`,
`BibleReader-NativeDemand.OS3KApp`, and `BibleReader-NativeBG.OS3KApp`; setting
`VERSION=NKJV` adds `-NKJV`. All share ID 0xA1B1 as alternative installations.
The [native streaming report](../native-streaming.md)
contains the comparison table, production NKJV images, test commands and limits.
The normal existing NKJV streaming demo is restored unchanged after profiling.


Native superscripts now use sparse indexed glyphs: unused characters are
zero-width, and all eight height bands share the width/offset maps. Storage is
3,584 bytes instead of 36,864, without changing digit pixels or native codes.
`generate_superscript.py` maintains the generated data. See the
[application-only ROM and maintenance table](../reader-costs.md)
for code/asset breakdowns and reproducible active-C complexity metrics.


`NATIVE_STREAM=5` is a **Neo 3.21 research-only** private viewport-layout
experiment, output `BibleReader-NativeViewport.OS3KApp`. It improves append-only
reading time, but the final long-selection test fails; it is not a replacement
for the normal reader. [Disassembly, measurements and limits](../native-layout-disassembly.md).


`NATIVE_STREAM=6` experiments with C-prepared native wrap-cache bytes and page
lookahead; `7` prepares the entire chapter before its first draw. Neither calls
the private viewport-layout helper. Outputs are `BibleReader-NativePrewrap` and
`BibleReader-NativePrewrapFull` (plus the translation suffix), ID 0xA1B1.
They retain decoded text in the native file; arbitrary overwide words needing
inserted hard-wrap bytes are not yet supported. See [prewrap measurements and
634 deterministic checks](../native-prewrap.md).


## Prefix search and index choices

Words now match exactly by default, with case ignored. A trailing `*` explicitly
requests a prefix: `Methus*` finds Methusael/Methuselah and `believ*` finds the
various endings. This applies independently to each term in all three modes.
`SearchBegin(..., SEARCH_SAME_VERSE|SEARCH_PHRASE|SEARCH_NEARBY)` selects the mode;
these are alternative enum values, not bit flags. `SearchStart` defaults to Same
verse. Legacy `SearchStartMode(..., 0|1)` retains exact/all-prefix phrase semantics
for older research callers. There is no automatic synonym or inflection expansion.

`SEARCH_INDEX=full` is the default packed chapter index, with grammar pruning
on by default for both reader frontends. `compact` uses four-character prefix
filters over eight-chapter groups; `scan` retains lexical lookup/normalization
but omits chapter filtering. `none` stores zero search metadata and decodes
characters into a streaming KMP/prefix phrase matcher; search grammar summaries
are omitted too. Text compression is identical. Optional applets
append `-compact`, `-scan` or `-none` after the translation suffix, retain ID 0xA1B1,
and are alternative installations. Build, for example:

```sh
make -C betawise/applets/BibleReader READER=BibleReader VERSION=KJV SEARCH_INDEX=compact PRUNE=1 PROFILE=0 TEST_FONT=0 NATIVE_OPEN_TEST=1 NATIVE_PAGE_TEST=1
```

The [KJV MAME benchmark](../prefix-search.md) compares
ROM, A5/stack/file RAM, first-hit/display latency and complete-result speed for
seven queries. Full remains recommended. Scan saves ROM, but completing a rare
search can take much longer even when its first hit is near the beginning.

### Search profiling options

`SEARCH_INDEX=full` means the original packed word/chapter postings, with prefix
matching; `compact` is the four-character bucket alternative. Broad queries still
verify many chapters. [God profiling](../god-search-profile.md)
compares opt-in `FAST_BITS=10|12 FAST_NATIVE=1` ROM lookup tables,
`SEARCH_CLEAR_COMPLETE=1`, and the KJV-tested `VERSE_BOOST=1` experiment. The latter
currently accelerates only God-prefix words with sparse verse restarts and adds
about 3.8 KiB A5; it is not a general verse index. These options default off / eight
bits and leave the existing compressed Bible payload unchanged.

[Directional search measurements](../navigation-search.md)
compare all four options from Genesis 24, Psalm 119 and John 3. Ordinary navigation
stops at one result; it does not enumerate matches before displaying the text.

## Search modes

In Find, press **Tab** (or Shift+Tab) to cycle Same verse, Exact phrase and Nearby
20 words. The selected mode stays visible above the query and persists in A5;
changing it preserves typed text. Enter accepts; Esc cancels. Matching remains
relative to the reading cursor in either direction.

[Mode measurements and validation](../search-modes.md)
compare Full and Compact from Psalm 119 and John 3, including negative phrases,
repeated terms, wildcard overlap and actual native dialog-to-result latency.
No new index or compressed text resources are required. The unordered matcher
keeps at most eight assigned occurrences, rather than a whole verse/chapter.
