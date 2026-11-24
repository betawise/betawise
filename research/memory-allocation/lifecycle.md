# Private heap reservations through startup and package changes

Binary-only investigation, 2026-11-23. Inputs are the three main ROM hashes in
the ABI inventory. Archived firmware source is excluded. Static conclusions
below are separated from bounded execution of the native startup phase.

Follow-up: [original neotools/native Manager transaction](manager/README.md)
executes installation, removal and full warm startup on Neo 3.21 using explicit
packet-transport and flash-command-lane fixtures. Full USB remains unqualified.

## Result

A5 is persistent on the marker-valid warm path; an install/remove triggers a
different path that zeros the applet RAM area and repacks A5 bases from the
fixed top. A private heap record in ordinary A5 is lost on that path. Heap
contents outside A5 may be cleared, reused as A5, or partly left behind; none
of those outcomes preserves a usable heap.

Crucially, clearing A5 does not necessarily release the extra reservation.
The package-change path adjusts the existing floor by the applet header RAM
size; the later A5 repack does not recompute that global. An unrecorded private
reservation can remain as a lost gap below the newly packed A5 region.

## Addresses and control flow

All addresses/offsets below are hexadecimal.

| Item | AS3000 3.01 | Neo 3.01 | Neo 3.21 |
|---|---:|---:|---:|
| Fixed applet-RAM top | `3D800` | `7D800` | `7D800` |
| Floor global | `354E` | `35A6` | `35DE` |
| Directory-valid marker, expected `0D89` | `3566` | `35BE` | `35F6` |
| Applet-init marker, expected `2675` | `3568` | `35C0` | `35F8` |
| A5 base array, 32 longs | `34CE` | `3526` | `355E` |
| Startup clear/repack phase begins | `4C74B6` | `5C6D08` | `417224` |
| First key/UI operation after that phase | `4C765E` | `5C6EB0` | `4173CC` |
| Later plain `MSG_INIT` push | `4C78B0` | `5C7102` | `417624` |

The two markers have distinct jobs:

- If the directory marker is invalid, startup clears the file/app RAM range
  and reconstructs the directory from flash. Reconstruction calculates the
  floor from the fixed top minus installed header RAM sizes. This discards
  hidden heap reservations and is not a file-preserving recovery operation.
- If the directory marker is valid but the applet-init marker is invalid,
  startup retains the directory/floor, clears `[floor, fixed_top)` to zero,
  removes empty directory entries, and repacks surviving A5 bases downward
  from the fixed top. It later dispatches plain `MSG_INIT` to applets.
- If both markers stay valid, startup bypasses those reconstruction/clear/
  repack/initialization branches. That path preserves the lowered floor and
  existing A5 state. Reset flags or firmware reset choices can invalidate
  markers; “warm restart” alone is not a sufficient lifetime specification.

Neo 3.21 examples: `4171F2` checks the directory marker; failure clears from
`1509C` to `7D800` and calls `4130FC` to reconstruct the directory/floor.
`417236` checks the applet-init marker. Failure clears `[35DE,7D800)` through
the original memset at `4366C2` (`417244..417260`), then recomputes A5 array
entries at `4173B8..4173C0`. That repack never writes `35DE`.
`41744C` later guards the applet initialization sequence; `417624..41762A`
dispatches `18` only after the clearing/repacking phase.

Betawise's own [crt0.S](../../os3k/crt0.S) additionally copies initialized data,
zeros BSS, and rebuilds relocation state on plain `MSG_INIT`. Such a callback
cannot recover an old heap record from ordinary BSS even if firmware had not
already cleared its containing arena.

## Manager install/remove

The native package handler is a multi-step transport transaction, not a public
allocation syscall. Its RAM changes are deferred in part until startup.

Neo 3.21 selector branches provide concrete examples:

- Removal clears the applet-init marker at `411086`, adds the removed header's
  RAM size to the existing floor at `4110F8`, and clears that applet's descriptor
  and A5-base entry at `4110FE` / `411108`. It does not immediately move every
  surviving applet's A5 in this branch.
- Finalization clears the applet-init marker at `411568` and subtracts the
  staged header's RAM size from the existing floor at `41159C`. It registers/
  updates directory metadata; startup later assigns/reassigns A5 bases.
- Restart replies with `52` (`411880..41189A`); transport delivery follows it
  by calling the warm entry `410082` (for example at `410C12`). Equivalent
  AS3000 finalizer/restart paths are documented in the existing
  [installation investigation](../applet-installation/README.md).

There is no identified all-applet “release your heaps before clearing”
notification in these paths. The later `MSG_INIT` is too late. Ordinary
`MSG_KILLFOCUS` addresses the outgoing foreground applet; it does not notify
every inactive heap owner or uniquely identify a forthcoming RAM repack.
Settings read/write messages are not an established pre-unload protocol.
Do not assume receipt of a callback before arbitrary reset/invalid-marker
recovery. This conclusion concerns the traced native paths, not every possible
third-party Manager workflow.

Thus the simplest safe contract for these reservations would require a
coordinated release before package changes, or an explicitly designed global
recovery/reconciliation step before fresh allocations. Merely throwing away
the per-applet records is insufficient. Raising the floor by one applet's
heap size can also cross other live arenas; release order still matters.
A5 relocation means raw pointers into other applets' ordinary A5 are invalid
across this operation as well.

## Bounded execution and limits

[run-lifecycle.py](run-lifecycle.py) and
[lifecycle-probe.lua](lifecycle-probe.lua) execute the original clear/repack
phase on all three ROMs. A read tap substitutes a self-loop only at the first
subsequent key/UI instruction, providing a deterministic stop before UI. Stored
ROM bytes remain unchanged. This instrumentation is not deployed code.

The disposable synthetic directory contains two 2048-byte applets and an
extra 4096-byte reservation. A heap record is seeded in the second applet's
A5 and a distinct byte pattern in the heap. Assertions establish:

1. With a valid applet-init marker, the phase skips clearing/repacking and
   preserves both the record and heap pattern and the lowered floor.
2. With that marker invalid, it zeros A5 and heap, packs bases from the fixed
   top, and retains the lowered floor. A 4096-byte gap remains without a record.
3. With an install-accounting fixture (second applet increased to 3072 bytes,
   floor decreased by 1024), the original phase repacks bases, destroys old
   heap/record bytes and retains the extra 4096-byte gap.
4. With a removal-accounting fixture (first descriptor removed, floor raised
   by 2048), the original phase compacts the directory and repacks the survivor.
   Its old record is zeroed. Some lower old heap bytes remain outside the clear
   range, but the extra gap remains and the record is gone.

These are controlled inputs to the actual native phase, not end-to-end
install/remove transport tests or a full reset/UI acceptance test. Interrupts
are masked and no Neo screen is used as an oracle. Captures do not establish
that every real warm restart keeps the markers valid. Static tracing identifies
the marker invalidation and floor updates in the actual Manager branches.

[Evidence manifest](results-summary.json) retains original ROM
hashes, logs, exact executed Lua, and twelve compressed full-RAM captures.

## Fill patterns and finding the floor

The native startup fills examined here use **zero**, not `A7`: both the full
file/app clearing path and the narrower applet-area clearing path push zero
as the memset value. No general `A7`-filled unused-RAM contract was established.
The local emulator initially supplies zeroed RAM as well. Even where a debug
fill exists, arbitrary file/heap contents can contain it, so scanning a pattern
cannot establish ownership or a usable allocation boundary.

There is a useful, shorter address relationship across all three ROMs:

| ROM | `AppletGetDisableMask(0)` leaves A0 at | Floor variable address |
|---|---:|---:|
| AS3000 3.01 | `344E` | `354E` |
| Neo 3.01 | `34A6` | `35A6` |
| Neo 3.21 | `34DE` | `35DE` |

Slot 152 (`A260`) is a short leaf routine. It computes
`mask_array_base + index*4` in A0, then loads the mask into D0 and returns,
leaving A0 unchanged. For index zero, **A0 + 100 is the address of the floor
variable**, not the floor value. A small assembly wrapper can capture that
register immediately and read the long at that address. A normal C call
followed by unrelated code cannot depend on volatile A0 surviving.

The lifecycle probe executes this syscall on all three ROMs and asserts both
the D0 mask value and the A0/address relationship. It is an undocumented
register side effect and layout relationship, qualified only for these images.
Signature-check it before use. Alternatively, decode its common instruction
shape: `222F0004 E589 0681 <mask_base:long> 2041 2010 4E75`.
The operand at function `+08` gives the mask base; add `100` to locate the
floor variable. The A5 array itself begins at mask-base `+80`, and the floor
follows its 32 longs. This is a RAM-layout relationship, not a universal
fixed difference between an arbitrary ROM code address and a RAM address.
The existing [FileGetFreeSpace decoder](pools-and-floor.md) provides an
independent cross-check.

Reproduce from the workspace root with a new output directory:

```sh
python3 betawise/research/memory-allocation/run-lifecycle.py /tmp/heap-lifecycle
python3 betawise/research/memory-allocation/verify-lifecycle.py /path/to/new-output
```

Retention: the compact results-summary.json and topic tables retain outcomes.
Raw captures, generated probe copies and logs named above describe historical
output locations; regenerate them with the documented runner in a fresh
directory and pass that directory to the verifier. They are not repository inputs.
