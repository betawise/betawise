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
