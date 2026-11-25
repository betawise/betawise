# Markdown editing and viewing research

Private applet IDs for new builds are listed in [the local index](../../applets/PRIVATE_IDS.md). Historical captures below retain their original IDs.

Research into Markdown and basic rich-text editing on the Neo: native text
formatting, AlphaWord integration, fonts, standalone editor options and export.
CoWriter is one investigated integration mechanism, not the scope of the project.

**Current interactive prototype:** [Markdown while typing](LIVE-MARKDOWN.md)
adds asterisk/underscore emphasis, literal list markers and continuation,
code-literal spans/fences, simple headings and quotes, cached typing and
complete-source deletion. The four-face font remains proportional.
[Linked-file and shortcut research](LINKED-FILES-AND-SHORTCUTS.md) includes a
separate hidden Beamer-ID hook probe. The older preview fixture below is a
separate experiment.

[ArtfulType architecture review](ARTFULTYPE.md) considers an owned styled editor,
shared Betawise rendering, semantic heading navigation and Markdown/RTF output.

Original-code investigation, 2026-11-21. Image hashes are pinned in
[images.json](images.json). Scope: the locally retained Neo AlphaWord Plus and
CoWriter images, and original Neo 3.21 ROM. This does not certify other versions.
No manufacturer binaries are modified. No public SDK declarations are inferred
solely from decompiler types.

## Findings

### Open-file bind pointers do not identify the live editor

A 2026-11-22 probe installs only original AlphaWord, without a CoWriter
companion, and reads the current 0x48-byte file entry and AlphaWord's editor
without invoking file/editor APIs. All four output-bind destinations at file
offsets 24/28/2C/30 are zero in six states: empty, after typing `abc`, with its
last character selected, after Home, in File 2 and after reopening File 1.
For the selected case the live editor has raw caret 2, anchor 3 and nonzero
selection state, while the file's sequential position remains zero.

This rules out these bindings as an editor-discovery route in the tested
original Neo 3.21 session. It does not claim that bindings are always null for
every applet or firmware version. The shared `FileInfo_t` contains output
registration addresses, not an editor-owner pointer. Original `FileBindState`
at 43A81C stores all four arguments into those fields, including null arguments;
native text paths such as 42AFEE and 42E6AE pass four null destinations.
`TextEditorSavePosition` at 42830E writes editor viewport offset 18 through the
file-position service, rather than the caret at editor offset 24.

Raw file/editor records, assertions, original-image hashes, logs and a portable
reproduction script are committed in [file-bindings/](file-bindings/README.md).
The original run path was `.research-work/cowriter-integration/file-bindings-20261122/`.
The probe reads
RAM state only; it makes no screen-rendering claim and uses disposable NVRAM.

### Companion discovery

AlphaWord finds the companion by the case-sensitive name prefix `CoWriter`,
not literal applet ID A001/A002/A101. The installed table index is cached at
AlphaWord A5+016A. A5+0172 holds the companion control record. CoWriter's actual
header ID is A101; A001 is AlphaQuiz, A002 Calculator, A100 Inspiration Outliner.
This is a specific integration, not an established arbitrary companion setting.

On focus gain (message 19), AlphaWord's code at offset 0920 loads the literal
`CoWriter` at 14BC6, passes start index zero to AppletFindByName, and caches the
result at 093C. At 0942..0956 it sends message 0 with the control-record pointer.
AppletSendMessage sets the synthetic 01000000 dispatch bit, so CoWriter receives
01000000. Name lookup is a prefix lookup, rather than an exact-name comparison.
The nearby `Wireless File Transfer` lookup is separate.

AlphaWord forwards characters through companion message 1 at 0C44..0C68 and
physical key events through message 3 at 0DB0..0DD4, provided the cached index
and companion state are nonzero. Those arrive as 01000001 and 01000003.
Focus loss sends message 2 at 0C1C..0C40. Another path sends message 5 at
1F84..1FB2 after an exact Ctrl+C event (physical key 41, modifier 8000), when
reached after native editor handling; this is not a claim that ordinary Copy
always activates CoWriter. Other normal editing branches may consume it first.

### Control record

The third argument normally called the applet `status` output is actually a
**ten-byte writable record** in this protocol, not just a four-byte integer:

| Offset | Size | Meaning established from both parties |
| --- | --- | --- |
| 00 | 1 | Companion state: 0 disabled; 1 standby/pass-through; 2 active |
| 01 | 1 | Event action |
| 02 | 4 | Returned text byte count |
| 06 | 4 | Borrowed pointer to returned text |

Word alignment of the 32-bit fields is intentional. Do not pass a normal
four-byte status variable to these companion messages.

AlphaWord action handling at 0C6C..0CBC and 0DD8..0E28:

* 0: consume event; do not forward it to native editing.
* 1: ordinary processing continues.
* 2: loop over the returned bytes and pass each as native editor MSG_CHAR (20).
* 3: take the redraw path without inserting text or forwarding the original event.

This text insertion uses ordinary character handling, not an encoded-token
insertion interface. It is not an arbitrary formatted-document transfer API.
The record does not give CoWriter a pointer to the complete AlphaWord document.

CoWriter handlers (offsets in the full OS3KApp):

| Received message | Observed role |
| --- | --- |
| 01000000 | Initialize/open companion interaction; may run substantial UI initialization |
| 01000001 | Character input; Tab is ASCII 09 |
| 01000002 | Disable: set state 0; clear text result |
| 01000003 | Physical key input; handles navigation/modifier-dependent commands |
| 01000004 | Return current state and default pass-through action |
| 01000005 | Enable from state 0 into state 2; action 0; set private pending flag |

CoWriter entry 0094 dispatches these messages. For character Tab, 0204..02DC
checks private state and toggles state 1/2. State 2 -> 1 returns action 3.
State 1 -> 2 also clears/prepares the CoWriter UI, beyond the narrow probe here.
Tab can be gated while particular private interaction states are active.
Sentence-ending punctuation and CR lead to returned text/action 2 when the
prediction workflow permits it (047A..0590). The returned text is in CoWriter's
A5+0147 buffer. This pointer is borrowed, not an allocation handed to AlphaWord.

### Consequences for a Markdown companion

A separate applet named Markdown with ID FF10 will not automatically receive this
hook. Options include a compatibility shim with the `CoWriter` prefix, modifying
AlphaWord's discovery, or an independent applet using explicit document import.
A shim competes with real CoWriter and must implement its control-record and
lifecycle behavior. It receives keys/characters but needs an additional supported
way to obtain the full active document for preview. No generic target-ID setting
was identified in the inspected companion path. AlphaWord settings 1010/1011
control file ownership/max length, not the CoWriter target.

## Native encoded text and AlphaWord formatting

The firmware editor underneath AlphaWord supports binary formatting tokens.
That does not imply that AlphaWord supplies a rich-text authoring UI. Ordinary
AlphaWord typing escapes reserved byte values, rather than interpreting typed
Markdown as formatting. Its editor can nevertheless use native encoded content.

| Region bits | Established role on Neo 3.21 |
| --- | --- |
| 01 | Hidden text: suppress display and layout coordinate advancement; optional scanner exclusion |
| 02 | Protected text: edit helpers reject/restrict modification; optional scanner exclusion |
| 0C | Two-bit font index `(flags & 12) >> 2`: 00 slot 0, 04 slot 1, 08 slot 2, 0C slot 3 |
| 10,20,40,80 | Carried by set/clear tokens; no independent rendering effect identified in the inspected renderer/scanner paths |

These are not inherently named regular/bold/italic/underline attributes.
A font applet or local caller supplies the actual four descriptors.
Set: B1 mask B1. Clear: B2 mask B2. These are OR/AND-NOT operations, not a
nesting stack: clearing an inner style also clears an identical outer bit unless
the producer restores the appropriate state. A Markdown translator must track
its own style stack and emit transitions. B0 byte B0 escapes a literal.

Neo forward scanner 42C120 carries the low-byte region flags, invokes face
selector 42E62E on set/clear, and suppresses coordinate updates for bit 01.
Selector 42E62E explicitly masks 0C, and loads editor offsets 4E/52/56/5A.
Renderer 42A0F8 handles hidden spans and the same four faces. Its selection
highlight state is separate from these region bits. No independent underline,
strikethrough, color, alignment, or superscript meaning was established for the
upper four bits. Treat them as unknown; do not assign speculative public names.
This is a scoped absence finding, not proof that no other firmware path uses them.

Font resolver 422AF4 requests font messages 2/3/4/5 for slots 0/1/2/3.
If a font applet returns NULL, slot 0 falls back to the built-in font; slot 1
falls back to slot 0; slot 2 to slot 0; slot 3 to slot 1. The retained vendor
NeoFontMedium handler answers message 2 with its regular descriptor and returns
NULL for 3/4/5. Thus all four resolve to the same face for this stock font.
Installing a genuine multi-face font could make encoded face switches visible,
but the stock AlphaWord UI still has no established bold/italic authoring path.

Do not conflate region bits with TextEditorInit flags 04/08/10. Those set private
editor descriptor byte 0D and govern different behaviors. This investigation
has not assigned new public names to those initialization flags.

## Reproduction and evidence

Run from the workspace root with a new disposable output directory:

```sh
python3 betawise/research/markdown/run-probe.py /tmp/neo-cowriter-new
```

278 direct original-code cases pass:

* 256 face-selector inputs, proving that only bits 0C choose the descriptor.
* 16 original forward-scanner cases: set and clear each of eight region bits,
  checking token length, retained flags, and selected descriptor.
* Six CoWriter handler cases: snapshot, disable, enable-from-disabled, active
  Tab to standby, standby ordinary character, disabled ordinary character.

The CoWriter image is copied to disposable RAM and its actual entry point runs
with private zeroed A5 state. This certifies the selected branches, not full
prediction initialization, dictionary loading, display appearance, physical-key
integration, transfers, power cycling, or every callback/lifecycle path. Face
selector/scanner tests assert returned RAM/state; there are no LCD assertions
or screenshots, and no model inference. The probe uses ordered return-PC
predicates and bounded deadlines. Each run has private cfg/NVRAM, hashes,
generated Lua, logs, and assertion results. It never opens a user's saved session.

Static evidence is retained in workspace `.research-work/cowriter-integration/`:
CoWriter entry disassembly/decompilation, AlphaWord entry, native renderer/scanner
and face-selector output, vendor-font disassembly, original hashes, and passing
MAME log. AlphaWord addresses above are relative to its validated code export
`alphawordplus.os3kapp.bin`; that entire export matches the original OS3KApp bytes
at offset 0094. CoWriter addresses include its header. ROM addresses are absolute.
Do not mix those address spaces.

`Dump.java` can reproduce selected functions with a disposable Ghidra project,
68000:BE:32:default BinaryLoader import, and `-noanalysis -postScript Dump.java`
followed by hexadecimal addresses. Decompiler jump-table recovery is incomplete
in some functions; branch tables and instruction operands were checked directly.

## Live AlphaWord editor experiments (resumed)

The hidden experimental companion is `EditorProbe`, ID **FF10**, name
`CoWriter Markdown Probe`. `FontProbe`, ID FF12, supplies four distinct 8x8
fixture faces. These are research artifacts, not a complete Markdown applet or
shipping font. The tests install original AlphaWord in private disposable flash.

| Investigation | Observed result | Limit |
| --- | --- | --- |
| Live editor access | Resolve AlphaWord A5, read its editor at A5+12, install four descriptors and use native text scanner/editor routines | Private, pinned-version offsets; not a stable public companion API |
| Companion shortcut | Hidden companion receives Ctrl+Alt+M; can consume it, draw a preview and restore native editing | Name prefix competes with genuine CoWriter; no coexistence certification |
| Native formatting and edits | Insert B1/04/B1 before `word` and B2/04/B2 after it in `**word**`; visible bold, movement, selection/copy, Backspace/replacement, subsequent regular punctuation and file reopen all work | One short fixture; not a Markdown incremental editor or full editing/undo certification |
| Source and preview | Plain scanner and native plain clipboard preserve `**worW**!`; preview and return preserve source and editor position | USB/IR/Manager export and power-cycle persistence not tested |

The complete style suite passed at `/tmp/neo-editor-style-resume-2` with ten
checkpoints. Eight full 264x64 cursor-free LCD comparisons had **zero differing
pixels**. Selection checkpoints use independent RAM/clipboard/cursor assertions
rather than claiming selection-highlight bitmap coverage. References were authored
from source glyphs and input strings before capture. Each screen capture observes
the firmware cursor-hide return, records three identical controller samples, then
restores the original cursor mode, registers and scratch RAM.

The padding experiment passed five checkpoints at `/tmp/neo-editor-padding-4`:
replace `   word   ` with two three-byte tokens around `word`, using same-size
FileWriteBuffer overwrite and TextEditorRefresh. File size, raw caret offset and
gap bounds remained identical immediately across replacement. Visible caret X
changed from 80 to 32 because the padding stopped consuming screen columns. This
validates the proposed padding mechanism for that fixture, but it consumes the
padding: plain output becomes `word`, not the original spaced text or `**word**`.
It does not by itself preserve reversible Markdown syntax or eliminate the need
to refresh editor state. Normal scanner insertion also works, so padding is not
required merely to get native formatting into AlphaWord.

Normal companion action-2 text insertion **escapes** token introducers, confirmed
at `/tmp/neo-editor-keyboard-1`. It cannot inject raw styles as keyboard characters.
Clipboard format 1 likewise inserts literal/escaped bytes; attempted ClipboardSet
format 0 was rejected (probe error 8). The failing paste case is retained as an
experiment, not a supported insertion route.

Native style insertion must account for firmware normalization. In this fixture,
insert the opening token first, then the closing token; inserting the unmatched
closing token first allowed it to be normalized away. Producers must maintain
balanced transitions, account for gap-buffer movement, refresh and rescan, and
avoid retaining borrowed buffer pointers across native edits.

A preview bug exposed by exact comparisons was fixed locally: Betawise
ClearScreen resets the controller start-line while the native ROM roll byte can
remain nonzero. Preview now uses native `_OS3K_ClearScreen` to keep native drawing
and controller coordinates consistent. No common-library change was made.

### Font and AlphaQuiz scope

`check-fonts.py` exercised 21 distinct retained vendor/community font images;
all supplied only their regular descriptor, returning NULL for the other three
faces. A bold-looking single-face font is not a regular/bold/italic family.
Full census artifacts are in `/tmp/neo-font-census`. The fixture tests demonstrate
visible slot-1 bold; the original selector tests cover all four slots. They do
not constitute visual acceptance testing of a production italic/bold-italic font.

Inspected AlphaQuiz insertion sites at image offsets 7A5C..7A78 and A4DC..A4F2
use plain TextScanInsert mode 1. No formatting-token literals were identified.
This provides no evidence that AlphaQuiz authored native rich text; it is not a
proof that every possible AlphaQuiz resource or runtime path lacks formatting.

### Run the current prototype in MAME

From the workspace root, choose a fresh output path:

```sh
python3 betawise/research/markdown/check-editor.py \
  --prepare-only --output /tmp/neo-markdown-demo
./mame/neodiag asneo \
  -rompath /tmp/neo-markdown-demo/roms \
  -cfg_directory /tmp/neo-markdown-demo/cfg \
  -nvram_directory /tmp/neo-markdown-demo/nvram \
  -window -skip_gameinfo
```

On first boot answer Y and Enter to the initialization prompts. In AlphaWord,
press Ctrl+Alt+Command+F, select the final `Probe` font with End, then Enter.
Type `**word**`; Ctrl+Alt+M toggles the fixture preview and native editing. MAME's
input menu identifies the host mapping for the Neo Command key. The hidden
companion will not appear as a normal applet. The preview only removes asterisks
and draws a single line using test face 1; it is deliberately **not a Markdown
parser**, and requires the supplied 8x8 test font. The interactive shortcut does
not automatically apply native inline styles. Use the deterministic style case
below to exercise that separate experiment.

```sh
python3 betawise/research/markdown/check-editor.py --output /tmp/neo-style-new
python3 betawise/research/markdown/check-editor.py --case padding --output /tmp/neo-padding-new
python3 betawise/research/markdown/check-editor.py --case keyboard --output /tmp/neo-keyboard-new
python3 betawise/research/markdown/check-editor.py --case preview --output /tmp/neo-preview-new
```

### Implementation decision

Native in-editor emphasis is feasible: a font with four faces plus carefully
maintained native transitions can style the source while retaining literal
Markdown delimiters. Concealing delimiters with hidden spans is a separate
untested editing problem involving cursor movement, deletion, selection and
copy/export. Do not call the present prototype WYSIWYG. Four font slots also
cannot independently represent every combination of bold, italic and underline;
underline would need a chosen face combination or custom drawing.

The companion callback can temporarily take over drawing, as demonstrated, but
that does not replace AlphaWord's line layout. There is no established hook here
for native paragraph alignment, table cells or custom wrapping while preserving
its cursor/selection geometry. A separate viewer gives us control over those.

Prefer a source editor plus preview first. Keep Markdown parsing outside the
shared viewer, and use a caller-owned bounded workspace, line/block streaming and
explicit depth/length limits; no mandatory malloc and no unbounded AST. A heap in
unused RAM would need verified ownership and lifetime against file growth and A5,
so it should not be a prerequisite. General Markdown compatibility remains work,
not a property demonstrated by this fixture.

BibleReader's native styled text path and streaming/custom layout experiments
justify factoring small Betawise primitives (face selection, measurement,
wrapping, clipping, scroll position and source offsets) when a second caller
actually needs them. Keep applet-specific Markdown/Bible semantics separate.
Do not build a general layout framework before comparing those concrete needs.

CoWriter compatibility and historical usage are discussed in
[community-usage.md](community-usage.md). A standalone viewer can coexist with
CoWriter, but this investigation has not found an alternative stock AlphaWord
hotkey-launch protocol. A forwarding broker is a possible further investigation,
not an implemented coexistence solution.

The default interactive command-9 toggle also passed its three-checkpoint suite
at `/tmp/neo-editor-manual-toggle-final`, including exact preview/return bitmaps.
An interactive disposable image is prepared at `/tmp/neo-markdown-demo-resumed`.
Passing style, padding, keyboard and toggle captures, raw files/editor records,
references, logs and archive hashes are retained in workspace
`.research-work/cowriter-integration/live-editor/`. Temporary path references in
copied result files describe the original run; the archived files remain alongside
those results.
