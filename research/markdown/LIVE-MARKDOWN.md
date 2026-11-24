# Markdown while typing: native AlphaWord prototype

Current revision: literal list markers, underscore emphasis, literal code spans
and fences, cached typing, headings/quotes and completed-marker hiding. This replaces the earlier downsampled DejaVu font and visible-only
prototype. The hidden companion remains ID A1ED with the CoWriter name prefix.
It drives the original AlphaWord native editor; it does not patch its code.

## Try it

A fresh fixed session is already prepared at
`/tmp/neo-markdown-source-demo-v6`. To use it, skip the preparation command
and run MAME below. Preparation requires a new output path for a new session.

From `/home/kirk/Projects/Alphasmart`, choose a fresh output directory:

```sh
python3 betawise/research/markdown/check-editor.py --live --prepare-only \
  --output /tmp/neo-markdown-source-demo-v6
./mame/neodiag asneo \
  -rompath /tmp/neo-markdown-source-demo-v6/roms \
  -cfg_directory /tmp/neo-markdown-source-demo-v6/cfg \
  -nvram_directory /tmp/neo-markdown-source-demo-v6/nvram \
  -window -skip_gameinfo
```

On first boot answer Y then Enter. In AlphaWord select **Markdown Bitmap** using
Ctrl+Alt+Command+F, End, Enter. MAME's input menu shows the host mapping for Neo
Command. Type `**bold** plain *italic* ***both***` normally.

Opening delimiters immediately style following text. A completed, properly nested
pair hides its delimiters, using native hidden spans. Unmatched delimiters remain
visible. **Ctrl+Alt+M toggles marker visibility** without changing the source.
Use source visibility to edit the syntax explicitly. Backspace after a hidden
closing pair skips its hidden characters and deletes a visible character inside
the span; End moves beyond the closing pair when you want to continue outside it.
Deleting the last visible character of a completed hidden span removes its now
empty delimiter pair too. This prevents leaving unmatched markers on the other
side of the caret; literal asterisk runs are preserved. The source otherwise
remains Markdown, including the hidden asterisks.

The 2026-11-22 poll-demo regression also checks a heading, paragraph emphasis,
list continuation, source visibility and complete-source Copy together. A trial
that appended `.` immediately after closing hidden italic preserved the source
but failed the independent cursor assertion (x=76 instead of 79). The demo uses
the documented End-key workflow before continuing outside a hidden span.
This is an unresolved prototype limitation,
not a reason to weaken the cursor assertion. Failed runs remain under
`.research-work/cowriter-integration/reddit-demo-20261122-v2`; the accepted run is
`reddit-demo-20261122-v4` (13 checkpoints, 12 exact screen comparisons).

## Whole-document selection deletion

Ctrl+A followed by Delete or Backspace now deletes the entire native encoded
source, including hidden emphasis/heading markers and generated bullet glyphs.
Ctrl+A then Cut does the same after placing the original Markdown on the
clipboard. Both forward and backward complete-source selections are supported.
Partial selections retain the native editor's existing behavior; this is not a
new general source-aware partial-selection engine.

The failure was reproduced before the fix: selecting/deleting
`**bold** *italic* ***both***` left twelve asterisks. Native selection deletion
omits hidden regions. The companion now recognizes the complete source range
and uses TextScanDelete in ENCODED mode with hidden/protected skipping disabled,
clears selection state, refreshes and resets the caret. It does not remove
asterisks heuristically or discard literal asterisks outside a deleted range.

The 17-checkpoint `selection` suite covers mixed emphasis, Delete, Backspace,
bullet source plus its display glyph, hidden headings, source-preserving Cut and
Paste, reversed selection, literal asterisks, source-visible mode and reopening.
Empty-file checkpoints assert the complete encoded content outside the native
gap is zero bytes, selection/style state is cleared, cursor geometry is at the
origin and the exact LCD bitmap is empty.

## Lists and simple blocks

* `- item`, `+ item`, `* item`: the original ASCII markers stay visible. Leading spaces are preserved, including on continuation.
* Enter continues a bullet; Enter on an empty item exits the list. Deleting a
  list marker uses ordinary character deletion.
* `1. item` or `1) item`: Enter inserts the next number. Existing items are not
  renumbered. Up to six digits and 48 bytes of prefix are handled.
* `# heading` through `###### heading`: same-size bold text; heading markers hide
  in rendered mode. There are no six different heading sizes.
* `> quoted`: visible quote prefix, italic text. No drawn bar or hanging indent.
* Ctrl+Alt+M reveals the original source markers for bullets and headings too.

These are native text operations. Soft-wrapped list continuation lines still
start at the native left margin: paragraph/hanging indentation is not provided
by these hooks. Tables, arbitrary alignment, distinct code fonts, links with
navigation and checkboxes are not implemented.

No display-only bullet glyphs are inserted. The previous round-bullet encoder
has been removed. Its bounded decoder remains able to recognize old escaped
95 glyphs so that reformatting can remove them and reveal the original marker.
Literal-marker tests assert that the encoded file contains no `B0 95 B0` sequence.
This eliminates that extra-character transfer hazard; native USB export with
hidden emphasis markers still remains unverified.

`_italic_`, `__bold__`, `___both___` now work alongside asterisks. Matching hidden
pairs require the same marker character and length. ASCII underscore flanking
rules keep `snake_case_name` literal. The parser remains a bounded subset, not a
full CommonMark implementation.

Single/multiple-backtick spans and backtick fences suppress emphasis, headings
and list continuation inside code. Backticks stay visible and use the current
regular face. Code is not yet rendered in a separate monospace face. Fences can
span hard lines; inline code retains the prototype's hard-line boundary. Tilde
fences and the complete CommonMark inline-code whitespace rules are unsupported.

Linked-file and Beamer research, including the executed hidden ID-based hook,
is documented in [LINKED-FILES-AND-SHORTCUTS.md](LINKED-FILES-AND-SHORTCUTS.md).

## Font

Markdown Bitmap uses the original hand-drawn X11 10-pixel Helvetica bitmap
regular, bold, oblique and bold-oblique faces in 12-pixel rows. It avoids TTF
rasterization at a tiny size and the old generator's added padding after every
letter. Advances are proportional and taken from the bitmap metrics, extended
only where needed to retain an italic overhang. ASCII glyphs are checked against
the row bounds, including descenders, before generation.

`build-markdown-font.py` uses Pillow's PCF reader to convert the installed X11
sources into Neo descriptors. Generated glyphs and profiles are included, so
ordinary builds do not require system fonts. Input hashes are in
`markdown-font.json`; copyright and permission notices are in `FONT-LICENSE.txt`.
These notices also retain the historical DejaVu prototype attribution.

The editor still has four font descriptors for the whole view. Tokens select a
slot; replacing a descriptor changes that slot's face throughout the view. A
slot could instead carry another size, but mixed-height layout is untested and
would reduce the available emphasis combinations. Hidden spans use a separate
region bit and do not consume a font slot. Underline is not a verified native
region attribute; tables and paragraph alignment need a different layout path.

## What is stored and why wrapping failed

Characters arrive through AlphaWord's CoWriter character/key callbacks. The
companion calls native TextEditorHandleMessage. Ordinary append typing then
updates a validated source/style cache without scanning or rewriting the file.
Other edits use a bounded C decoder over the current file, excluding the native
gap and recognizing the verified style/escape/soft-wrap bytes. No borrowed buffer
pointer is retained across an edit. Desired styles are compared against existing
styles. Only when they differ does the formatter rebuild native encoded text
through TextScanDelete, TextScanInsert in ENCODED mode, and TextEditorRefresh.
It restores the caret using source coordinates plus legacy generated-glyph accounting. It does not type control characters
through the keyboard, which would escape them.

Native formatting uses three-byte sequences:

* `B1 mask B1` sets region bits; `B2 mask B2` clears them.
* `04`, `08`, `0C` select bold, italic, combined slots in this font family.
* `01` hides a span from native drawing/layout. Completed delimiters remain in
  the source between hidden set/clear tokens.

The original prototype rejected every non-ASCII native byte other than its face
tokens. AlphaWord replaces a space at a soft wrap with **81**, a native layout
byte that plain scanning converts back to a space. The guard rejected it after
wrapping, stopping subsequent styling. It now accepts that native byte while
continuing to reject unknown forms and protected structures. Encoded backup
also removes the raw A7 gap using the editor's explicit gap bounds.

Native Copy normally drops hidden spans. The companion overrides the plain
clipboard contents for Copy with the selected Markdown source range, including
hidden delimiters. Full-source Copy with hidden markers is tested. Partial source
selections can contain unmatched syntax, as ordinary source fragments can.
Native USB/IR/Manager export with hidden markers is **not certified**; those paths
may need explicit source export rather than assuming native hidden-text policies
match ours.

## Prototype limits

* No malloc: 2,048-byte ASCII source limit and fixed parser/output/backup buffers
  in the applet's allocated RAM. No unowned heap between files and A5.
* `*`/`_`, double and triple marker runs provide emphasis. Backslash escaping
  and code suppression are handled, with bounded ASCII underscore flanking
  rules rather than full CommonMark conformance. Emphasis resets on a hard line break, not a soft wrap.
  Hiding matches properly nested equal-length runs, with a bounded 32-level stack.
* Ordinary appended letters use the cached path: no whole-file scan or rewrite.
  Spaces, navigation, non-append edits and syntax changes can still scan the
  bounded source. Formatting/visibility changes can rebuild the whole document.
  It is not yet a general incremental parser. See [PERFORMANCE.md](PERFORMANCE.md).
* Foreign forms/protected text and unsupported bytes are refused. Insertion
  failure attempts encoded rollback; allocation/rollback failure paths are not
  fault-injection certified. Errors are exposed in `g_probe.error`.
* Original ROM and AlphaWord private offsets remain version-pinned. Genuine
  CoWriter coexistence, undo and power-cycle persistence remain unverified.

## Reproduce the checks

Use a new output path for each invocation:

```sh
python3 betawise/research/markdown/check-editor.py --live --case selection --output /tmp/neo-selection-check
python3 betawise/research/markdown/check-editor.py --live --case lists --output /tmp/neo-list-check
python3 betawise/research/markdown/check-editor.py --live --case blocks --output /tmp/neo-block-check
python3 betawise/research/markdown/check-editor.py --live --case profile --output /tmp/neo-profile-check
python3 betawise/research/markdown/check-editor.py --live --case hidden --output /tmp/neo-hide-check
python3 betawise/research/markdown/check-editor.py --live --case wrap --output /tmp/neo-wrap-check
python3 betawise/research/markdown/check-editor.py --live --case backspace --output /tmp/neo-backspace-check
python3 betawise/research/markdown/check-editor.py --live --case repeat --output /tmp/neo-repeat-check
python3 betawise/research/markdown/check-editor.py --live --case live --output /tmp/neo-live-check
python3 betawise/research/markdown/make-typing-demo.py /tmp/neo-hide-check /tmp/markdown-hidden.gif
```

The suites use exact full-screen bitmap profiles and explicit expected source,
faces, cursor coordinates and clipboard strings. Wrapped fixtures author the
expected line breaks before capture; they are not inferred from failing images.
Selection-only checkpoints use separate RAM/cursor/clipboard assertions. Every
capture observes firmware cursor hide/restore returns and three identical
controller RAM samples, preserving guest registers and scratch memory. No model
vision is used. The animation uses only verified captured LCD frames enlarged
4x; it is a sequence of checkpoints, not a typing-speed measurement. Nothing is
posted or sent to anyone.

The original Backspace report was not reproduced by the single-character,
empty-file, marker-deletion or plain held-key tests. An extended held-key test
with hidden formatted content did expose stranded delimiters after deleting the
last visible character. The empty-span cleanup above fixes that case, with
separate one-character italic, bold and combined tests. This is not proof that
the original intermittent report had the same cause. The soft-wrap failure was
reproduced before its fix.

Historical v4 acceptance: 64 functional checkpoints, including 58 exact full-screen
matches, plus 9 performance/source checkpoints. Artifacts and hashes are retained
under `.research-work/cowriter-integration/markdown-v4/`. The historical v4 session was
prepared at `/tmp/neo-markdown-lists-demo-v4`. Historical list animation:
`.research-work/cowriter-integration/markdown-lists.gif`. The earlier v3 runs and
animation remain historical artifacts, not the current typing performance.

Selection-fix acceptance is recorded under workspace
`.research-work/cowriter-integration/markdown-v5/`. This includes the reproduced
pre-fix failure, 17 passing selection checkpoints and the hidden/list/performance
regressions. Earlier v4 data above remains historical performance evidence.

The v5 checks passed 49 functional checkpoints (45 exact screen comparisons),
plus nine performance checkpoints. The steady typing counters still assert no
whole-document scan, parse or rewrite. Timing summary:
`.research-work/cowriter-integration/typing-profile-v5.json`.

V6 adds dedicated underscore/code/literal-list suites. The Beamer hook probe is a
separate disposable experiment; the standard inline build still has ID A1ED and
the CoWriter name prefix. Font slots remain regular/bold/italic/combined. See the
shortcut notes for the optional preview-shim design and its Beamer conflict.

Current v6 acceptance: 101 functional checkpoints (including the two hidden
Beamer-hook checks), 93 exact full-screen comparisons, plus 9 performance
checkpoints. Raw files, LCD records, logs, source snapshots, Ghidra inspection
output and hashes are under `.research-work/cowriter-integration/markdown-v6/`.
Steady typing still has zero whole-file decodes, parses or rewrites in the
profile checks; about 32 ms total and 0.42 ms Markdown overhead at 1,500 source
characters. The first uncached key is about 112 ms after the extra syntax passes.
Fresh interactive image: `/tmp/neo-markdown-source-demo-v6`.
