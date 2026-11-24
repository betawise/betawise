# Saved lengths, public compaction, and shared-heap compatibility

## What saved length means

This is native file-record state, not a disk save timestamp or a demonstrated
user-facing undo record. Logical length (+04) controls ordinary I/O; saved
length (+08) is a retained high-water/restore extent; reservation (+10) is an
independent minimum. Ordinary length growth raises saved length when necessary,
while shrinking can leave it larger. FILE_LENGTH_RESTORE_SAVED (-2) exposes it;
FILE_LENGTH_GROW_TOWARD_SAVED (-6) exposes at most another 40 bytes. Snapshot
(-4) commits current lengths globally and triggers allocation maintenance.

The allocator retains max(saved length, reserved length), rounded to 512 bytes.
Therefore a larger saved length can keep actual tail bytes alive across logical
shrinking, not just affect free-space accounting. The normal invariant check
raises saved below live to live; an inconsistent smaller value is not a way to
safely reclaim live contents.

The original Neo AlphaWord image calls -6 at full-image offset 2C40 and -2 at
2D28 through its length helper at 2C2E (called at 1866 with modes 0/1/2).
It also queries the saved length with FileQuerySize(FC) in its per-file
size/reservation adjustment loop at 247A and restores/saves intermediate length
values through that loop. Do not equate these operations with a user-visible
Undo feature. Exact disassembly contexts are retained in saved-length-consumers.json;
original image hashes are in the existing ABI and Markdown inventories.

A native-key Neo 3.21 AlphaWord observation typed abc and received an actual
KILLFOCUS via the native Applets workflow (caller 418228). The active record's
logical and saved lengths were both 512 before, at entry, after return and after
regaining focus. Raw file-table/editor captures and hashes are retained in
alpha-saved-focus-evidence. The native editor keeps a gap within that raw length.
This is one ordinary focus transition, not proof that all AlphaWord states or
other applets have equal saved/live lengths on focus loss. No screenshots or
vision oracle were used. Preserving the saved lengths avoids needing to assume
that all dormant applets have finished their temporary length operations.

## A public path that preserves saved lengths, with a pressure caveat

Executed on AS3000 3.01, Neo 3.01, Neo 3.21:

1. FileClose, FileCreate a temporary 512-byte file, FileClose, FileDelete it.
2. Verify the original records' live/saved/reserved lengths, retained bytes and
   four registered bindings. Packed capacities are 512,1536,2048: 4096 total.
3. Verify public free-space equals the physically vacant tail in the fixture.
4. Lower the private floor by 4096, execute public FileOpen capacity growth,
   and verify every original retained byte, binding and full independent heap
   guard. Raise the floor and verify public file growth can reclaim the tail.
5. Separately exercise the snapshot route and its known saved-length changes.

The preserving path passed all three ROMs. It uses no direct private ROM calls.
The synthetic table setup/observer and explicit floor write remain private-RAM
operations. Public-preserve-evidence contains 24 compressed full-RAM captures,
logs, source/probe/ROM/emulator hashes, and independent assertion verification.

**Creation is not harmless under pressure.** In a second three-ROM run the floor
is tightened to the packed end, with public free space zero, then FileCreate(512)
is deliberately attempted anyway. Its fallback clears clipboard live/saved
lengths (200/256 -> 0/0), snapshots ordinary saved length (1300 -> 1000), and then
succeeds using the recovered space. This is original firmware behavior, not
an allocator bug introduced by our wrapper. Public-pressure-evidence retains
15 compressed captures and exact probes/logs; verify-public-pressure.py checks
this independently. A successful FileCreate result alone is insufficient.

A production wrapper must establish sufficient room and a free table entry
before creation, avoid the destructive fallback, preserve/restore native folder
and file selection, coordinate IDs renumbered by deletion, and invalidate borrowed
file pointers across movement. If those preconditions cannot be established,
return allocation failure instead of using the snapshot or clipboard-clearing
fallback. These tests establish a candidate mechanism, not native-editor/Manager
acceptance across arbitrary memory pressure. Maintaining a small prearranged
maintenance file/budget is an alternative worth qualifying, not implemented here.

Reproduce in new output directories from the workspace root:

```sh
python3 betawise/research/memory-allocation/run-public-preserve.py /tmp/preserve-new
python3 betawise/research/memory-allocation/verify-public-preserve.py /tmp/preserve-new
python3 betawise/research/memory-allocation/run-public-pressure.py /tmp/pressure-new
python3 betawise/research/memory-allocation/verify-public-pressure.py /tmp/pressure-new
python3 betawise/research/memory-allocation/run-alpha-saved-focus.py /tmp/focus-new
```

## Shared heap compatibility decision

A shared format with statically linked allocators is technically possible but
makes every client an independent metadata writer. Format versions can reject
unsupported layouts; they do not fix old allocator bugs. A bug fix that changes
coalescing, ownership or validation would require replacing affected applets,
or refusing them. Checksums detect some damage; they cannot repair arbitrary
corruption or stale raw pointers.

Prefer one installed allocation/reservation service before a cross-app shared
heap. Initially use synchronous applet messages with a versioned request struct:
query capabilities, allocate, free, resize, query statistics. Keep all allocator
metadata private to that implementation. Clients never interpret heap headers.
This requires no general dynamic linker, exported compiler helpers, negative-A5
convention, or terminal migration. Applet-local allocators can still manage GC
arenas/objects within reservations, without sharing object-level metadata.

A compatible bug fix then changes one installed implementation. The qualified
package-update/global-init path discards old runtime heaps, so a fresh heap can
use a new private layout while old clients continue through the stable API.
Ordinary marker-valid warm restart retains the same implementation/state.
Hot replacement, corrupted live heaps and unknown firmware shapes must not be
silently treated as safe; no automatic repair guarantee is implied. Keep the
API's failure, lifetime, ownership and realloc-preservation contracts stable.

Retention: the compact results-summary.json and topic tables retain outcomes.
Raw captures, generated probe copies and logs named above describe historical
output locations; regenerate them with the documented runner in a fresh
directory and pass that directory to the verifier. They are not repository inputs.
