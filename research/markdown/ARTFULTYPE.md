# ArtfulType and a Neo styled editor

Inspected 2026-11-22, upstream commit
`7cc0b04a876810fa222685366e0e3e2c546dda98`.
Source checkout: `/tmp/artfultype-research-20261122`.
This is source inspection, not an executed Mac/Neo port.

## What ArtfulType actually supplies

[ArtfulType](https://github.com/ActionRetro/ArtfulType) is a C application for
classic Macintosh, rather than a platform-independent editor engine. Its eight
C files total about 2,790 lines, excluding headers/resources. In
[`main.c`](https://github.com/ActionRetro/ArtfulType/blob/7cc0b04a876810fa222685366e0e3e2c546dda98/app/main.c),
two `TEStyleNew` instances hold raw Markdown and styled Writer text. Mac TextEdit
handles ordinary keys, cursor/selection, wrapping, style tracking and drawing
through `TEKey`, `TEClick`, `TESetStyle`, `TEUpdate` and `TEIdle`.

[`markdown.c`](https://github.com/ActionRetro/ArtfulType/blob/7cc0b04a876810fa222685366e0e3e2c546dda98/app/markdown.c)
contains the useful application logic: `BuildHiddenView` strips markup into the
styled buffer, `DetectInlineMarkdown` recognizes typed markup in Writer mode,
and `SyncHiddenToCanonical` recreates Markdown from text and style runs. The
Writer buffer has real styles: the syntax is removed, not kept as invisible
characters in the same buffer. Style-menu shortcuts also work without requiring
the user to type Markdown. Files are plain Markdown.

This design can normalize Markdown spelling during serialization; it should
not be treated as a lossless arbitrary-Markdown source editor. Heading identity
is inferred from bold text and heading font size. Links use IDs carried in a
spare color channel. Our document model should instead have explicit paragraph
heading levels, inline styles and link metadata, independent of rendering.

## What would have to change

Mac TextEdit, QuickDraw, Font Manager, movable memory handles, file dialogs and
event/window routines are not available on the Neo. `NewHandle` allocations
occur in conversion and undo paths; the code is not allocation-free simply
because it does not call `malloc`. Undo holds up to fifteen document snapshots,
coalesces typing runs, and clears history on view changes. Source comments warn
about whole-document conversion pauses on long styled documents.

The concept is feasible on the Neo; a direct port would replace much of the
machinery that makes the Mac version small. Use ArtfulType as an interaction
and conversion reference, with an editing core such as stb_textedit and our
own storage/layout, rather than implementing a compatibility layer for TextEdit.
Source is GPLv3; upstream separately reserves its name and creative assets.
No upstream code or assets were copied into the prototype by this investigation.

## Proposed Neo document model

Own the text, style spans and paragraph records. Paragraph records contain
explicit heading levels and list kinds. A bounded heading index supplies a
chapter/section picker and next/previous-heading commands. A display zoom
setting changes device readability without changing document semantics.

Share font measurement, styled-run layout, wrapping and viewport primitives in
Betawise with the Bible reader. Keep editing, Markdown parsing and serialization
in their own components. Use fixed buffers/pools with explicit capacity and
failure handling; borrowing a temporary arena is optional, not a parser requirement.
Cache paragraph layouts and reflow affected paragraphs instead of reparsing and
rebuilding a whole document for every keystroke.

The current BibleReader already owns a native `TextEditor_t` and uses its fourth
face for local superscript verse numbers; it is not currently a complete custom
text layout engine to copy. Retain that backend unless new requirements justify
replacing it. Shared arbitrary-font layout would be new Betawise functionality,
not something already supplied by the current BibleReader.

A useful initial bitmap set is body regular/bold/italic/bold-italic, one code
monospace face and one or two heading sizes. A custom renderer has no native
four-face selector limit. Underline can be a drawn rule. On a 64-pixel screen,
large headings reduce visible rows substantially, so keep size choices modest.
Every Neo font profile and mixed-height layout needs deterministic local tests.

## RTF is an output format, not a required editor architecture

One structured document could export plain text, Markdown, a deliberately small
RTF subset, or host-specific keyboard text/style events. An RTF writer can
stream escaped text and style transitions without building an RTF AST. Font
tables and character/paragraph formatting are defined in
[Microsoft's RTF documentation](https://learn.microsoft.com/en-us/windows/win32/controls/about-text-object-model).
Preserve semantic headings in the exported stylesheet, not just larger bold text.

With mass storage, an actual `.rtf` file is the convenient desktop handoff.
Sending literal RTF syntax as keyboard characters does not import it as rich
text. Keyboard transfer with Ctrl+B/Ctrl+I depends on destination application,
platform shortcuts and current style state; headings/lists are less portable.
Full import and lossless round trips of arbitrary Word-produced RTF are a much
larger project than exporting our own supported subset.

The direct MAME prototype recording demonstrates existing inline AlphaWord behavior only.
Standalone editing, variable sizes, heading navigation, RTF and formatted host
transfer are proposals, not implemented features shown in the recording.
