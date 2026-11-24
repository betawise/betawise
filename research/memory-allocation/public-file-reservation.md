# Public file compaction and private heap reservation

Executed on AS3000 3.01, Neo 3.01 and Neo 3.21 in disposable MAME instances.
This is a synthetic native file-table fixture, not full applet/editor acceptance.
No screenshots, model inference, physical devices or user sessions are used.

## Result

`FileClose(); FileSetCurrentLength(FILE_LENGTH_SNAPSHOT_ALL);` compacts all
three exercised ROMs through public A-line calls only. The test uses public
FileGetFreeSpace, FileOpen and FileSetCurrentLength for subsequent checks and
file capacity growth; it makes no direct private ROM function calls.
The fixture setup and observer use private file layouts; reserving/releasing
4096 bytes still explicitly writes the private RAM floor. This is not a
public-only heap allocation API.

The three packed file capacities are 512, 1024 and 2048 bytes (3584 total).
The public free-space result equals the physical vacant tail in these fixtures.
After lowering the floor, public FileOpen grows file capacity only up to the
new boundary. Payload bytes, position fields and all four registered bindings
remain correct, and the complete 4096-byte independent heap guard survives.
A preflight rejection leaves the floor and guard unchanged. Restoring the floor
allows public FileOpen to reclaim the tail, leaving less than 512 bytes unused.

## Saved lengths are observable state

The seeded (live, saved, reserved) triples are:

- Clipboard: (200, 256, 0).
- First ordinary file: (1000, 1300, 800).
- Second ordinary file: (1600, 1400, 2000).

The public free-space query's native invariant checking normalizes the second
ordinary file's saved length upward to 1600. The raw seeded and before captures
record that transition. Snapshot with a cached file does not compact; its
resolver may return an error, so return status is not treated as proof of work.
After FileClose and global snapshot, **all three saved lengths, including the
clipboard's, equal their live lengths**. This corrects the earlier assumption
that the first/clipboard record was excluded.

Opening the first ordinary file and applying FILE_LENGTH_RESTORE_SAVED returns
1000, rather than the original 1300. Opening can redistribute capacity, so the
test explicitly closes/snapshots again and verifies the packed bound before
lowering the floor. Current contents remain intact, but old saved-length
restore semantics have changed. This sequence is therefore not established as
transparent compaction for arbitrary native editor sessions. Do not restore a
longer saved length after shrinking its retained allocation: bytes beyond live
length might no longer exist.

## Reproduction

From the workspace root, choose a new output directory:

```sh
python3 betawise/research/memory-allocation/run-public-floor.py /tmp/public-floor-new
python3 betawise/research/memory-allocation/verify-public-floor.py /tmp/public-floor-new
python3 betawise/research/memory-allocation/verify-public-floor.py /path/to/new-output
```

The retained public-floor-evidence manifest hashes source scripts, actual Lua,
ROM inputs, emulators, logs, and five compressed full-RAM captures per ROM.
No ROM images or disposable flash/session images are distributed with evidence.
The test runs calls with interrupts masked; production serialization and native
editor/Manager integration remain to be qualified independently.

Follow-up: [saved-length consumers and preserving public compaction](saved-lengths-and-public-compaction.md)
qualifies a preserving create/delete path and its destructive low-memory fallback.

Retention: the compact results-summary.json and topic tables retain outcomes.
Raw captures, generated probe copies and logs named above describe historical
output locations; regenerate them with the documented runner in a fresh
directory and pass that directory to the verifier. They are not repository inputs.
