# Applet metadata and system-font syscall audit

Inspected the original Neo 3.21 image, not just the SDK declarations. Its pinned
identity is recorded in [the ROM inventory](../../abi-audit/rom-inventory.json).
The follow-up SDK adapters and flag-based picker integration are described below.

## Actual dispatch table and selector coverage

The table at 44F15E contains 285 entries: 264 populated and 21 zero. Every
populated entry currently has an SDK annotation; there are no additional
populated *unnamed* slots. The annotations were not used to select audit roots.
The bytes after entry 284 begin `01 02 03 04 05 06 07 08 ...`, followed by other
resource data, not an additional service array. The A-line handler masks the
opcode to nine index bits without checking this table boundary; out-of-table
opcodes therefore do not constitute additional callable API entries.

The fresh Ghidra import disassembles all 264 populated roots and their statically
identified callees (690 function entries in this run). It records references to
the applet table and selected-font state, plus unresolved computed transfers.
All 24 branches of slot 174's sparse selector switch were explicitly decoded
from the ROM tables. This is a targeted API investigation, not a claim that every
callback/computed branch of every firmware function is fully characterized.
Generated table lists, instruction excerpts, call edges and unresolved transfers
live under `build/font-access/` and can be regenerated.

## Headers are available through secondary register results

| Slot | Opcode | Neo 3.21 entry | Established result on success |
|---|---|---|---|
| 143 | A23C | 439BBC | D0 = installed index; A0 = matched header |
| 144 | A240 | 439BF4 | D0.b = true; A0 = end of source name in header |

The name getter copies the header's name, stopping at NUL or the end of its
36-byte field. A0 remains at that stopping point. A small assembly adapter can
capture it immediately and reconstruct the header as:

```
header = source_name_end - strlen(copied_name) - offsetof(AppletHeader_t, name)
```

The format offset is 24. Thus enumeration by installed index can obtain both
the name and header with one existing syscall, without a fixed applet-table
address or a guessed ID. It can then read `header->flags & 0x20` and separately
check the disable mask. Name-prefix stripping is only presentation logic.
For callers already looking up an ID, slot 143 supplies the header directly.
The name-getter route also handles a full-width, unterminated name correctly.

These are **undocumented secondary register results**, not vendor-promised
return types. Ordinary C declarations discard them; an adapter must capture A0
before any subsequent call. On failure A0 is stale or a service entry address,
so the boolean/index result must be checked before using the pointer. ID zero
also has the usual slot-zero/result-zero ambiguity.

The complete 56-byte ID lookup and 108-byte name getter are byte-identical across
AS3000 3.01, Neo 3.01 and Neo 3.21 after normalizing their four-byte applet-table
base operand. Static comparison does not certify unrelated/future ROMs.

Eight real A-line cases passed in disposable Neo 3.21 MAME state: font and
non-font headers, an unprefixed font with a full 36-byte name, and missing ID/name
lookups. Success cases assert reconstructed headers and their actual flag words;
failed calls deliberately do not interpret A0. A5 preservation is also checked.
Controlled descriptor fixtures are used; these are not whole UI acceptance tests.

## No global font-selection setter found

No populated slot is a dedicated global-font getter/setter or header/flags getter.
The 24 CallSysInt selectors include the built-in font pointer and small font
pointer, but no selected-provider setter. The opaque 0D00/0E00 pair accesses byte
5DB0, not font selection. The scratch-pointer selector returns 5DBE, also not the
font-selection block.

The native chooser at 42284E is not a dispatch-table target. Its confirmation
path updates 5C7A..5C8D: four descriptors, provider ID and installed slot (20 bytes).
The internal getter at 422AF4 reads/validates that selection, lazily loads faces,
and can reset an invalid selection to System; it is not an arbitrary-provider
setter and is not a syscall-table target either.

Slots 10/11 were traced through their save/restore implementations. They save
screen content, cursor state and the **console** font pointer at 5C68; they do not
save or restore the four selected text-editor faces, provider ID or slot.
Slot 183 sets four pointers on a supplied editor, not the global selection.
The native event loop can open the chooser through keyboard handling, but that
is not a callable save/select/restore interface.

Consequently the header-result adapter can solve flag-based discovery without
fixed firmware addresses. The proposed global save/select/capture/restore wrapper
still needs access to private selection state or another mechanism not found
in this audit. No such restore wrapper was implemented or claimed tested here.

## Reproduce

From the repository root:

```sh
python3 research/syscalls/applet/audit-font-access.py --ghidra --mame
```

The runner checks actual table bytes against the pinned ROMs, compares lookup
bodies across three images, emits disassembly, creates a separate Ghidra project,
and executes the register-result probe against original firmware. All generated
projects, reports and disposable MAME state stay under `build/font-access/`.

## SDK integration

`AppletGetId(index)` reads the stable provider ID through the same private
header adapter, for persistence or explicit known-ID display exceptions.
`AppletGetFlags(index)` now exposes the full header flag word for indices 1–31,
returning zero for absent/out-of-range/zero indices (zero may also be a valid
flag word). `AppletIsFont(index)` tests the native provider bit 0x20; disabled
state and context locks remain the separate `AppletGetDisableMask(index)` API.
Both APIs use installed indices. Callers holding IDs resolve them once with
`AppletFindById` before querying flags/masks or sending messages.

The ID-based and index-based header adapters are private in
`os3k_applet_internal.h`. They capture A0 through inline assembly around ordinary
PIC/GOT calls to the existing raw syscall stubs; neither contains firmware data
addresses. The public API does not expose header pointers. BibleWise discovery
now uses the font flag, not a naming-prefix heuristic.

`python3 tests/qemu/applet-flags.py` checks the production adapters with poisoned
failure pointers, narrow boolean status with junk upper bits, bit-10-only
non-font flags, bit-20-only fonts, full-width names and range guards. The MAME
probe now also executes the compiled production adapters and public predicates
against the original ROM, in addition to the eight raw-register cases (nine
cases total). Existing 18 pointer bridges and all 21 proportional picker
checkpoints passed after this integration.

## Follow-up: built-in dialog font access and coverage

`inspect-dialog-fonts.py --mame` extracts unchanged artwork and rechecks native
register results in disposable Neo 3.21 state. Outputs stay in
`build/dialog-fonts/`: 32×8 byte-slot cards, a 264×65 reading sample enlarged
without interpolation, coverage JSON, instruction excerpts and 31 register cases.

CallSysInt's complete 24-selector switch has two constant font outputs:
0700 → 44AF8E (6×16) and 4000 → 44D592 (9px proportional).
There is no selector for the 11px descriptor at 44E336. Unsupported selectors
return false without manufacturing another font output. The previous full
populated syscall-table audit found no dedicated getter elsewhere.

Creation at 433B86 allocates a pool object and looks up a geometry template.
An invalid layout returns D0=0, A1=0; exhausted allocation returns D0=0 with
A0 pointing into the object pool and A1 pointing to a geometry template.
Neither failure leaks the font pointer. Successful creation also leaves object
pointers, not a font descriptor. Creation alone does not initialize font globals.

There IS a narrower indirect route, so “no way to obtain it” would be too strong:
FontDialogTextWidth (slot 269, entry 43490C) leaves the currently active dialog
font in A1 for a nonempty ordinary string. Once the dialog subsystem is
initialized, the tested path leaves the 9px RAM descriptor at 7E32. The 11px RAM
copy immediately follows at +16. Native assertions verify both descriptors and
the latter's bitmap pointer. This avoids a literal ROM font address, but relies
on undocumented A1 contents, subsystem initialization and private adjacency;
it is not an independent getter. Before initialization A1 was zero. The probe
uses the private subsystem initializer ONLY to establish initialized test state,
not as a proposed production API. No SDK adapter or production fallback to 11px
has been added here.

The 9px resource has blank slots 01–1F and 20; the 11px resource only has blank
20. However, nonempty artwork is NOT character coverage: the 9px resource uses
one identical replacement box in 69 slots, and 11px does so in six slots.
See the exact comparison and implications below. The cards retain native byte
labels and do not substitute generated glyphs.

## Exact 9px versus 11px artwork comparison

The extraction script also produces per-slot `pixel-comparison.json`, a summary,
and `differences.png`. It compares all pixels in the advance cell, trying each
possible blank-row padding (0+2, 1+1, 2+0). A separate ink-coordinate comparison
allows horizontal translation, without obscuring advance differences.

Excluding space, blank 9px slots, and repeated replacement-box slots, 155 slots
have distinct implemented artwork in both resources. Of these, 147 match exactly
including advance after padding: 144 with two blank rows above, two with one
above and one below, one with two below. Eight differ:

* 00 full block fills the entire 9px or 11px cell.
* 40 @: advance 7→6 and three ink pixels removed after +2 vertical alignment.
* 72 r: same ink shifted right one pixel and down two; advance 4→5.
* 7A z: same ink shifted down two; advance 5→4.
* C7 Ç: advance 5→6 and different artwork.
* EC/ED/EE ì/í/î: each 11px glyph has one additional ink pixel after +1 alignment.

For printable ASCII 21–7E, 91 of 94 match with padding, with only @/r/z differing.
Thus the everyday English appearance is substantially the same, but 11px is not
merely a padded copy of the entire 9px resource.

9px is missing the Neo extras at 01–1F (Greek, arrows, fractions, math symbols,
Ń and ĳ). Its 69 repeated replacement-box slots include many Western letters:
Š Œ Ž š ž Ÿ À Á Â Ã Ä Å È É Ê Ë Ì Í Î Ï Ñ Ò Ó Ô Õ Ö Ø Ù Ú Û Ü Ý
à á â ã ä å è é ê ë ñ ò ó ô õ ö ù ú û ü ý ÿ.
Other replacements include ‰ ¥ © ª ® ± ¹ ² ³, nonbreaking space, and six Neo
extra/alias slots. All exact byte positions are recorded in `coverage.json`.
11px retains the box only at 81/8D/8F/90/9D/A0: ⌐/Φ/Π/grave alias/π/NBSP.
The ordinary ASCII grave at 60 remains available.

Recommendation: 9px is a compact English reading option (seven complete lines),
not a general Neo-US/Western default. Preserve installed reading-font priority;
its normal/bold/italic faces provide real styles, while the ROM fallback uses
the same body face for all styles. Prefer complete providers or 6×16 when text
requires unsupported characters. BibleWise supplies verse-number superscript
bitmaps separately, so its verse numbers do not depend on native ¹²³ slots.
The user's global font should remain an explicit choice rather than an inherited
unpredictable default. No default-selection policy was changed by this audit.

Cross-ROM fallback check: the pinned AS3000 and Neo 3.01 images do not contain
slots 263/269 (FontDialogCreate/TextWidth), and a byte-alignment-independent
scan finds no 9px or 11px proportional descriptors with in-image width, offset
and bitmap pointers. Neo 3.21 has ROM descriptors at 44D592 and 44E336, separated
by 0xDA4 bytes, NOT adjacent. Only their private RAM copies are adjacent (+16).
Therefore adjacency cannot be inferred from the ROM small-font getter, and the
A1 route is not a general cross-ROM fallback API. Prefer the public 6×16 getter
for a portable complete fallback; a Neo 3.21-specific 11px adapter would need
separate initialization/version validation and a safe fallback.
