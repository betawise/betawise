# Cursor portability and font discovery

## Applet discovery

The current SDK discovers installed providers through applet lookup/name calls
and the audited secondary header results exposed by `AppletGetFlags`,
`AppletIsFont` and `AppletGetId`. Font status comes from the header flag and the
disable mask; a name prefix is presentation, not a discovery restriction.
BibleWise persists provider IDs and resolves current indices again on focus.

The early investigation found no dedicated header/flags syscall and initially
used name prefixes and known IDs. That implementation has been replaced by the
[metadata adapters](../applet/font-access.md); the old limitations and retained
name buffer do not describe current code. Identity-selection calls are not used
as getters, and the applet does not read a fixed RAM provider table.

## Cursor structures

The original ROMs in `../../abi-audit/rom-inventory.json` demonstrate that the bitmap
cursor address is not stable:

| ROM | SetCursor implementation | Bitmap cursor base |
| --- | --- | --- |
| AS3000 3.01 | 0x4CD826 | No Neo bitmap cursor |
| Neo 3.01 | 0x5D11EC | 0x5712 |
| Neo 3.21 | 0x42216C | 0x5C68 |

Neo SetCursor loads its cursor base directly (`movea.l #address,a3`). These are
research observations, not entry points used by BibleWise. No manufacturer
promise that this RAM remains fixed was found. BetaWise's existing `0x5C68`
implementation is deliberately unchanged at the user's request.

AS3000 works through a different path: when the bitmap font query returns NULL,
`os3k_display.c` delegates SetCursor and character output to the numbered native
syscalls. It does not dereference the Neo bitmap cursor structure on that path.

## Vendor applet evidence and limits

`audit-cursor-access.py` hash-checks all inventoried original images, recognizes
validated cursor syscall stub blocks, and resolves direct and adjacent
immediate-delta/indexed-PC references. On the current 56-image inventory, 26
images contain resolved cursor API references, including AlphaWord Plus,
Calculator, Control Panel, Beamer and KeyWords. Thus vendor applets demonstrably
use the cursor syscalls. This does not prove that none also access cursor RAM.

Raw occurrences of cursor-like integers are not sufficient evidence of direct RAM
access: several are relocation-independent PC-relative call deltas, and other
hits occur in data. The report labels them accordingly. Computed/indirect calls,
other instruction sequences and unexamined ROMs remain outside this static scan.

Reproduce without altering any original image:

```sh
python3 betawise/research/syscalls/display/audit-cursor-access.py --output /tmp/cursor-audit
```

The output preserves hashes, raw literal offsets, resolved reference candidates,
and disassemblies of the three pinned cursor implementations. This run's records
are in `/tmp/bible-cursor-audit-final/`.

## Follow-up: how vendor applets obtain a cursor (2026-11-26)

The distinction is between the grid console cursor and the native editor cursor.
The native editor has the capability BetaWise needs internally, but it does not
export that capability as a general cursor-setting syscall.

### Concrete vendor callers

A second hash-checked pass resolves selected service calls from validated,
monotonically numbered vendor syscall stub blocks. In the inventoried Neo images:

| Applet | SetCursor references | GetCursorPos | TextEditorInit | TextEditorHandleMessage |
| --- | ---: | ---: | ---: | ---: |
| Calculator | 43 | 5 | 0 | 0 |
| AlphaWord Plus | 130 | 8 | 30 | 30 |
| Inspiration Outliner | 81 | 17 | 0 | 0 |

These are static reference counts, not invocation counts. For example, Calculator
at file offset `0x3BA` pushes mode 12, column 1 and row 2 before the indexed-PC
call at `0x3CC` to its A004 stub. It is ordinary grid positioning, not a hidden
font/pixel overload. AlphaWord uses native editor contexts through A2BC/A2C0 for
its editing UI; an example initialization call is at file offset `0xA5E`.
Thus a vendor applet need not obtain the bitmap cursor structure just to use a
variable-width editor: the ROM editor maintains it internally.

### The missing operations do exist inside the ROM

In pinned Neo 3.21:

- A004 / `0x42216C` takes row, column and visibility. It temporarily assigns
  the fixed system 6x16 descriptor, computes x/y from grid dimensions and origins,
  then applies cursor visibility. In hide mode (12), it restores the previous
  font pointer, **but the coordinates were still computed using the system
  font**. This is not an arbitrary-font or pixel-coordinate interface.
- Internal `0x4221F4` accepts x/y pixel coordinates and cursor mode, erases the
  old cursor and positions/draws the new one using the current cursor font.
  Native editor paths call it, for example `0x42A19E`.
- Internal `0x421CF4` receives a font pointer, x/y and raster dimensions/options.
  It stores the pointer into the cursor font field while rasterizing a span.
  The editor's span renderer calls it at `0x42A3CC`.
- `TextEditorSetFonts` / A2DC assigns an editor context's four font pointers,
  recomputes layout and optionally redraws. It provides the supported indirect
  route for a native editor, not a general-purpose console cursor setter.

Neither internal helper is a target anywhere in the pinned Neo 3.21 syscall
pointer table. Calling their addresses directly would recreate precisely the
fixed-ROM-entry-point dependency we want to avoid. The vendor scan found no
resolved direct references to these two fixed addresses across the 56 images;
that is not proof against every possible computed reference.

The full Neo 3.21 `CallSysInt` dispatcher was also inspected again. Its recognized
selectors are the 24 already recorded in `os3k.h`; none supplies cursor x/y, a
cursor font setter, or a cursor-structure pointer. Its two font-pointer queries
return the fixed system and small-font descriptors, not cursor state.
No standalone hidden font/pixel cursor API was found in this investigation.
This is scoped to the inventoried ROMs and recognized reference forms, not a
claim about every firmware revision.

### Consequence for BetaWise

BibleWise already uses the native editor, so its reading-view caret can continue
to be managed by that editor. BetaWise's independent bitmap-font **console**
renderer is the code still relying on `0x5C68`. Using the native editor for such
views would also delegate the caret, but requires editor/file/layout context.
The discovered internal helpers do not currently supply an address-independent
replacement for that console's cursor operations. No custom cursor or SDK
behavior was implemented or changed by this research.

Reproduce the vendor trace:

```sh
python3 betawise/research/syscalls/display/trace-vendor-cursor.py --output /tmp/vendor-cursor-trace-new
```

This run's `/tmp/vendor-cursor-trace/` contains hash-pinned image records,
resolved offsets, representative vendor disassemblies and focused ROM excerpts.
