# BibleWise local font selection and everyday-use regression

Investigated against Neo 3.21, ROM SHA-256
`32fe55bb50c1b58326bd303f14973b8402ddf8bf6662b210e4d5e9f931c7e6c0`.
This also incorporates the findings in the **X11 Fonts** chat
(`01a20597-b735-7220-a435-d5541f593b7d`).

## Title corruption

BibleWise uses the native `DialogInit` / `DialogDraw` / `DialogRun` list, with
an app-owned title and provider enumeration. It is not a custom list renderer.
The native system font selector at `0x42284E` uses that same list machinery:
`0x422858..0x422868` passes single-column, rows 2–4, width **40**.

Our width of 44 exceeded the native console's text area. Scrolling invokes the
row-clearing path at `0x41B992..0x41B9C2`, which writes spaces through the normal
console. Clearing too many columns wraps into the title row. The first scroll
erased exactly 47 ink pixels belonging to “adi”: bounding rectangle
`x=12..26, y=2..11`. The preserved reproduction is
`/tmp/bible-font-menu-reproduce`.

The production list now uses width 40 and writes its title through the native
6×16 console. The regression checks every title pixel through Down, Up, Home,
End and cancellation, with native cursor geometry asserted separately. The
modal title is a region assertion; this does not claim pixel verification of
every native list item or scroll indicator.

## System picker versus a view-local choice

The system picker has no editor/destination argument. Confirmation writes the
shared provider ID at `0x5C8A`, slot at `0x5C8C`, and four cached face pointers at
`0x5C7A..0x5C86`. See `0x422A24..0x422AEC`. It therefore changes the font used by
ordinary system/AlphaWord lookups.

An editor can retain independent descriptors through `TextEditorSetFonts`.
However, `TextEditorRefresh` reloads shared fonts. BibleWise now reapplies its
local descriptors after refresh and restores the logical viewport, caret and
selection before drawing. `TextEditorSavePosition` also moves the gap without
rebasing the selection anchor; the reader rebases that anchor immediately after
saving. Both failures have explicit AlphaWord round-trip regressions.

A snapshot/restore wrapper around the system picker would depend on private ROM
state and could also need to restore mutable state inside a future font bank.
There is no supported local-only picker mode identified in the inspected ROM.
Keeping the native list widget with local results is simpler.

The X11 Fonts investigation also established that picker confirmation and
ordinary font lookup both issue messages 2→3→4→5, using the same destinations.
A provider must not open a family/size submenu on an ordinary descriptor request.
A future BetaWise font bank should expose an explicit chooser/query API that
returns stable descriptors for an individual selection. Its native default can
remain independent of the reader's choice. A shared initial font default is
reasonable; reading and writing preferences should remain independently editable.
No font-bank protocol or secondary picker was introduced in this change.

## Additional issues found by the expanded tests

* Cached hyphen `0xAD` must become `-` for clipboard text and count as a line break
  after drawing the hyphen for caret measurement. The local bitmap oracle now
  handles this documented ROM cache representation explicitly.
* The rich private face needs normal spaces/punctuation and uppercase fallback
  glyphs. Zero-width entries disrupted spacing and wrapping after small-cap
  words. The existing private bitmap buffer has room; no new A5 buffer was added.
* Native refresh replaced local fonts on return from AlphaWord.
* Native position saving relocated the gap but left selection anchors stale.

The cached-hyphen copy and Leviticus small-cap wrapping regressions are separate
from the general reading/navigation cases.

## Maintained regression

From the workspace root:

```sh
python3 betawise/tests/mame/asneo/check-biblewise-usage.py --output /tmp/biblewise-usage
```

The matrix has 516 checkpoints across 12 groups: all 65 book seams in both
directions, Genesis/Revelation endpoint no-ops, both sides of Jude and other
single-chapter books, chapter/verse aliases, all eight display combinations,
paging, exact/prefix/phrase/nearby search, next/previous/repeated searches,
invalid input and cancellation, no-match and wrap notices, clipboard, local
font identity and AlphaWord round trips. Everyday-use cases cover KJV and NKJV;
the complete book-seam walk uses NKJV. Rich-font samples cover Times, Helvetica
and Century Schoolbook; modal forms use the ROM system font.

The acceptance summary is `/tmp/biblewise-usage-acceptance/results.json`. It
references the preserved raw controller records, font/descriptor/cursor state,
independent references, comparisons and per-run manifests. All validation is
local and deterministic; no model vision is used. Historical failed captures
remain available alongside the accepted runs.
