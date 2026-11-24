# Standalone editing options

Research: 2026-11-21. No prototype behavior changed for this investigation.

## Native drawing constraints

Original Neo 3.21 ROM character renderer `421A82` reads a glyph width from
the font width table (or its fixed width) and passes that width to bitmap
drawing at `4205DE`. The ordinary bitmap path reaches `4206F4`: for example,
`420780..42078E` preserves pixels outside the destination mask, clears pixels
inside it, then inserts the masked source. This is opaque replacement within
the glyph rectangle, not transparent OR. Selection takes a separate inverted
source raster path.

There is no independent drawing width and zero advance in the native font
descriptor. A width-zero glyph therefore cannot supply a visible first pass
for an overlapping bold character. This conclusion is from original-code
inspection, not a new emulator pixel regression. A custom renderer could use
OR explicitly, synthesize bold and underline, and select more than four fonts.

## Candidate cores

* **stb_textedit** is the best small C candidate. The caller owns storage,
  rendering, widths and wrapping; the core handles navigation, selection,
  insertion/deletion and bounded undo/redo. It performs no runtime allocations.
  Formatting commands, style history and Markdown serialization would be ours.
  Its author cautions about large texts and limited undo; Neo file sizes and
  software floating-point layout costs need measurement before adoption.
  Source: <https://raw.githubusercontent.com/nothings/stb/master/stb_textedit.h>.
* **Hermes PAIGE** is a much fuller rich-text engine with LGPL-2.1 licensing,
  but should not be described as a ready bare-metal C library. Its current
  CMake build requests C++17, includes C++ import/export code, and selects
  desktop platform and memory implementations. Neo drawing and allocation
  adaptation are unproven. Sources:
  <https://github.com/nmatavka/Hermes-Paige>,
  <https://github.com/nmatavka/Hermes-Paige/blob/main/CMakeLists.txt>.
* **Nuklear** is ANSI C with a caller-provided rendering backend and fixed-memory
  options, but is a GUI toolkit and its stock text editor is plain text. It
  adds more surrounding machinery than directly using an editing core.
  Source: <https://github.com/Immediate-Mode-UI/Nuklear>.

## Architecture choices

The present inline prototype accesses private AlphaWord editor state. Native
Copy and deletion skipping hidden source are established; an end-to-end USB
Send result is **not established by this investigation**. Export correctness
must be demonstrated rather than inferred from those other scanner users.

Three paths remain: preserve literal Markdown in AlphaWord with a separate
preview; own a native TextEditor instance in an applet with explicit document
and export ownership; or use a custom renderer and a core such as stb_textedit.
Owning a native editor avoids borrowing AlphaWord's private structure, but
retains native rendering constraints. Custom editing permits arbitrary faces
and sizes but requires style-aware layout and source/display position mapping.

Betawise could share bitmap glyph measurement/drawing, styled runs, wrapping
and viewport support between the Bible reader and Markdown viewer/editor.
Document syntax, editing transactions and file serialization should remain
separate consumers of those primitives.
