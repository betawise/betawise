# Private pools and an independent RAM reservation

Binary-only follow-up, 2026-11-23. Archived firmware source and claims derived
from it are excluded. This is research, not a production allocator/API.

## Pool search

No convincing general pool initializer/allocator matching the proposed five
32-bit fields was identified in the seven available OS packages: AS3000 3.01,
Neo 3.01, Neo 3.21, their three SmallOS packages, and UpdaterReverter.
This does not establish that such code was removed, or that no private allocator
exists. Linear disassembly is not a complete recovery of code/data boundaries;
indirect/global field accesses, alternative arithmetic, reordered fields, and
inlined routines can evade these searches.

[scan-pools.py](scan-pools.py) preserves input hashes and candidate contexts. It
looks for 20-byte strides / multiply-by-five, neighborhoods writing offsets
0/4/8/12/16, and decrement-by-one operations on possible count fields. Its
[42 candidates](pool-candidates.json) did not establish a pool:

- The main-ROM `lea ...@(20)` hits address a formatting/string cursor or a
  native file's cursor field, not a descriptor-array stride.
- Five-field neighborhoods in AS3000 `4DA782`, Neo 3.01 `5DCF06`, and Neo 3.21
  `42F702` initialize more than five pointers and add different resource
  offsets. They do not initialize a block size and paired block counts.
- Neo `5D771A` / `429152` mixes byte/word fields with pointers, branches on a
  mode, and initializes a larger structure. Neo 3.21 `451200` writes hardware
  configuration values including `A0040009` and `80000000`; its neighbors
  issue register configuration calls. Neither has the proposed pool shape.
- Count-decrement hits concern byte/text consumption, string trimming, bounds
  iteration, or serial output. Examples: Neo 3.21 `42431C` consumes a byte and
  advances its pointer; `430402` handles text layout; `444490` decrements a
  caller's character pointer. SmallOS hits accompany output to `FFFFF907`.

The separate 1-MiB stock AS3000 image in `mame/roms/asma3k.zip`, member
`28f008b3.u1`, SHA-256
`a8f5da7ccf5f8ebe27962b655335a3a3a16f60a688a4a80c74c706dd025a7501`,
has **bit 0 clear in every byte**. For example, it has zero intact `4E75` RTS
encodings. It cannot support a reliable comparison with non-OS3K firmware.
No attempt was made to guess the missing bits. The reason for this condition
has not been established.

The independently established 8192-byte scratch arena and fixed dialog-object
pool remain the concrete alternatives described in the [main audit](README.md).
The OS3K AS3000 binary itself does allocate installed applet A5 blocks: see its
registry reconstruction at `4C3038`. It should not be classified as lacking A5.

## RAM boundary identified in all three main ROMs

These are private addresses specific to the inventoried binary hashes, not
portable syscall contracts. All values are big-endian; boundary globals contain
32-bit RAM addresses, not pointers to another boundary variable.

| ROM | RAM floor global | File allocator/compactor | Mirror refresh | File invariant checker |
|---|---:|---:|---:|---:|
| AS3000 3.01 | `354E` | `4E336C` | `4E383C` | `4E3ABC` |
| Neo 3.01 | `35A6` | `5E5CC8` | `5E61B0` | `5E6430` |
| Neo 3.21 | `35DE` | `43C0CA` | `43C5B2` | `43C832` |

Installed applet RAM grows downward; file buffers occupy RAM below this floor.
The registry reconstruction subtracts each applet header's RAM size (`+08`)
from its running address, stores the resulting per-applet base, and updates
the floor. AS3000 starts at `3D800`; the two Neo ROMs start at `7D800`.

For Neo 3.21, reconstruction starts at `4130FC`, subtracts the size at `4131DE`,
stores the base in the `355E` array at `4131E8`, and writes `35DE` at `4131EC`.
The allocator reads that **same floor directly**, for example at `43C13A`,
`43C1F2`, and `43C2B4`. The checker loads it at `43C842` and verifies file
capacities against the remaining region. No independent global file-space end
was found in these allocator paths. There is nevertheless cached extent state:
every file record contains a data pointer (`+00`) and capacity (`+0C`).

Therefore a floor write alone is insufficient. Existing capacity can extend
past the new floor even when the file's actual retained bytes would fit.
Compaction can move buffers and must refresh the caller's bound pointer fields.
The native compactor preserves the larger of saved length (`+08`) and reserved
minimum (`+10`), with 512-byte capacity rounding/minima in the exercised paths.
Before using it, establish valid native length invariants, including saved
length covering live length. Its return is not a general malloc-style success
indicator. Inspect the resulting records and bounds.

## Disposable reservation experiment

[run-floor.py](run-floor.py) / [floor-probe.lua](floor-probe.lua) execute the
unmodified original ROM functions above on a deliberately synthetic, contiguous
three-record file arena, including the native first/clipboard record. They
do not exercise a user's session, applet UI, or arbitrary production tables.

On **all three ROMs**, the experiment passed:

1. Seed distinct live/saved/reserved lengths and payload patterns, initially
   giving records substantial spare capacity. Bind all four mirror variables.
2. Invoke native compaction with a NULL target. The retained capacities pack to
   4096 bytes total, preserving the saved/reserved payload, live lengths,
   cursor fields and refreshed bindings. Run the native invariant checker.
3. Preflight space, lower the floor by 4096, and fill that reserved range with
   an independent guard pattern. Let the native allocator expand the last
   file, then request an excessively large middle-file capacity. Resulting
   file extents stay below the new floor; payloads, bindings, and guards survive.
   The native allocator uses rounded capacities; a tail smaller than 512 bytes
   may remain unused.
4. Demonstrate that an insufficient-space request is rejected by the **probe's
   preflight**, without changing the floor or guard. This is not a native
   reservation/failure API.
5. Restore the floor, then let the native allocator reclaim the tail. Recheck
   payloads, mirrors, contiguity, bounds, and the native checker.

Preserved [manifest](results-summary.json), per-ROM logs, exact executed
Lua, and compressed full RAM records cover before/reserved/released states.
The tests run with interrupts masked in a disposable context. They establish
the basic reservation mechanism, not safe concurrent or focus lifecycle use.

## What an sbrk-like implementation would need

Yes: reserving `[new_floor, old_floor)` below the installed applet blocks can
provide a separate stable-address arena without enlarging or moving the running
applet's A5. Existing applet base-table entries would stay unchanged. Ordinary C
pointers can address this arena; it does not automatically become A5-relative
storage. The experimentally supported sequence is compact, preflight, lower
the floor, then use the newly excluded tail. Do not lower first and hope
compaction will recover overwritten data.

A production implementation still needs:

- One persistent owner/ledger for reservations, overflow/alignment checks, and
  a reversible failure path. Multiple allocations can be suballocated inside
  one reservation. Releasing arbitrary reservations creates holes that one
  floor cannot describe; topmost/LIFO release is much simpler.
- Serialization with file movement and package-management operations, plus
  refresh of all registered file bindings and invalidation of borrowed raw
  data pointers. The experiment's interrupt masking is not a production policy.
- A policy for installation/removal, registry reconstruction, reset and
  firmware compatibility. Neo 3.21 installation subtracts from `35DE` at
  `41159C`, removal adds at `4110F8`, initialization writes at `4121C0`, and
  reconstruction overwrites it at `413188`/`4131EC`. An unrecorded reservation
  can consequently be reclaimed. Those paths must understand it, or the
  reservation must be released before they run.
- Actual focus-loss/resume and memory-pressure qualification with real file
  workflows. This experiment does **not** certify persistence across focus,
  warm startup, install/remove, or reconstruction. A shared Betawise component
  is a plausible place to coordinate this, but other firmware operations
  must also honor its ownership.

This is a promising basis for an independent runtime heap, stronger than
borrowing scratch RAM. It is not yet safe to expose as persistent FILE/DIR
backing or generalized `malloc` merely by writing one global.

## Discovering the boundary without fixed ROM addresses

No identified `CallSysInt` selector returns physical RAM size or the live
applet/file RAM floor. Selector `0800` reports flash chip-select size, not RAM.
The shared scratch pointer is not a documented fixed offset from this floor.
`FileGetFreeSpace()` reports a quantity including reclaimable file capacity;
adding that quantity to an arbitrary file's end does not recover the boundary.

There is a concrete read-only discovery route in all three inventoried ROMs:

1. Read the line-A exception handler pointer from RAM vector `0x28`.
2. Validate its dispatcher instructions. It contains `LEA abs.l,A0` at handler
   `+0C`; the long operand at `+0E` gives the syscall table address. The older
   ROMs mask the opcode with `03FC`; Neo 3.21 uses `07FC`.
3. Read table entry 107 (`FileGetFreeSpace`, opcode `A1AC`). This yields the
   actual ROM implementation, unlike taking the address of the library stub.
4. Validate that implementation's known instruction shape. At implementation
   `+30` is `2039` (`MOVE.L abs.l,D0`); its long operand at `+32` is the address
   of the **live floor global**. Dereference it to obtain the current boundary.

All offsets here are hexadecimal. A bounded signature decoder is sufficient;
a general disassembler is unnecessary. Validate readable ROM/RAM ranges and
instruction signatures before following pointers; decline unsupported shapes.
Do not blindly search for the first absolute load: the same function accesses
several different globals. Hooked vectors or altered ROMs need separate handling.

[check-floor-discovery.py](check-floor-discovery.py) replayed this chain from
the actual guest vector in all three preserved reservation RAM captures,
validated dispatcher/function signatures against the original hashed ROM, and
recovered `354E` / `35A6` / `35DE`. It read the experimentally lowered floor
(`1B000` / `5B000` / `5B000`), demonstrating that it finds the live variable,
not merely the startup constant. This is an offline replay of captured guest
state, not a newly installed on-device decoder. Reading the variable is useful
independently of the still-unqualified policy for modifying it.

### Register residue follow-up

All aligned encodings of the floor address in each main image were checked:
15 occurrences per ROM, all long absolute operands (no extra short-absolute
references). They cover the five installation/initialization/reconstruction
writes and ten reads in reconstruction, startup clearing, free-space
calculation, private compaction, invariant checking and diagnostic printing.
No additional direct syscall returning the unmodified floor in a register was
identified. This does not exclude an indirect access through a computed alias.

`FileGetFreeSpace` overwrites its initial D0 floor load. Its invariant checker
loads the floor in D3 but saves/restores D3; the outer function restores its
D4-D7/A2-A4 working registers and returns the byte count in D0. The private
compactor subtracts a file base from its D0 floor loads, or uses saved D7 for a
rounded capacity; it is not a floor getter. Calling a file-changing syscall
to trigger these internal paths does not provide a consistent register result.
The allocator/checker ranges have no direct syscall-table entries in the three
inventoried ROMs. The signature decoder remains the concrete read-only method.

Heap records need not imply a shared heap or central per-allocation ownership
table. Each applet can retain its own arena records in A5, and allocate within
its arenas independently. A common reservation protocol can be linked into
each applet without requiring an installed shared library. It must still
serialize changes to the one global floor and coordinate with firmware
reconstruction/package changes. With separate stable arenas, releasing an
arena above another applet's reservation cannot simply raise the floor: that
creates an interior hole. Keeping arenas reserved, or releasing only when the
arena's low edge equals the current floor, avoids that particular collision.
Reclaiming interior holes later requires additional coordination/metadata;
freeing objects inside an applet's own arena does not.

Reproduce from the workspace root, choosing new output directories:

```sh
python3 betawise/research/memory-allocation/scan-pools.py /tmp/pool-search
python3 betawise/research/memory-allocation/run-floor.py /tmp/floor-test
python3 betawise/research/memory-allocation/verify-floor.py /path/to/new-output
```

Retention: the compact results-summary.json and topic tables retain outcomes.
Raw captures, generated probe copies and logs named above describe historical
output locations; regenerate them with the documented runner in a fresh
directory and pass that directory to the verifier. They are not repository inputs.
