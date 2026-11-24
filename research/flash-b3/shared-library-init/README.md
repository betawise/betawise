# Main-ROM shared library: updater stream and F-line lifecycle

Investigated 2026-11-23 using original local binaries and disposable Neo 3.21
MAME flash/RAM. No physical USB/device access and no physical NOR programming.
SmallROM was not modified. The purpose is to reuse otherwise wasted ROM capacity
for shared executable code; helper deletion/compaction recovery are separate.

## Conclusions

1. The inspected vendor Manager streams the **whole package file**, including
   the older zero-filled main tails. A smaller executable payload does not leave
   those package-backed zeros erased. Under a successful stock update the AS3000
   and Neo05 main tails become 00, while Neo13's large main tail remains FF.
2. F-line gives a working service entry without modifying the zero-filled A-line
   pointer table. In the executed Neo13 baseline, F-line vector 2C was zero; stock
   warm initialization and the native RAM loader did not replace our vector.
3. Reinstall/check the vector during Betawise initialization. Do not rely on its
   survival across physical resets: the emulator's reset mirroring is a material
   limitation, and physical retained-SRAM behavior was not established here.

## Actual vendor updater path (static trace)

Host: local NEOManager.exe from NEOManager 3.9.3, SHA-256
`2b06bdd3ab5c04bef45ad128fde24c0e7db24796d21c8083a90eeefa5973cc12`.
This is the inspected local host version, not a claim about every vendor release.
The large update function at **4309D0** has diagnostic name `UpdaterAddApplet`.
Read-only Ghidra decompilation was cross-checked with x86 disassembly. The initial
whole-program analysis reached its time limit, but the relevant functions and
file-I/O wrappers were recovered; conclusions below follow those actual paths.

- For main-system images it enters SmallROM with request 18, clears the segment
  map with 16, seeks to package offset **50h**, reads big-endian address/length
  pairs, and sends 17 with the address and `(length + 3FFh) >> 10` KiB. A zero
  descriptor terminates segment configuration. 4317AB..4317B8 shows the rounding.
- The path then joins **431049**, obtains actual file length through **438370**,
  seeks to file byte zero, and loops over `_read(..., 400h)` through **4383A0**.
  438370 uses `_lseek` to EOF and restores the old file position; 438400 is the
  seek wrapper. This is not a header's executable/code-size field.
- Every returned byte contributes to the block checksum. Request 02 declares
  the returned count/checksum, the block is sent, and 0B requests programming.
  Remaining file length is reduced by the actual read count. The loop has no
  zero/FF trimming or executable-end cutoff. The header itself is streamed too.
- Transport variants share this file-stream loop. The AlphaHub path has extra
  compatibility decisions for the 5FFC00 segment; these do not trim main tails.

The resulting ordinary single-device stream is:

| Package | Main destination | Main bytes sent | Main padding sent |
|---|---|---:|---|
| AS3000 3.01 | 4C0000..500000 | 262,144 | 84,654 zero bytes at 4EB4D2..4FFF80 |
| Neo 3.01 | 5C0000..600000 | 262,144 | 57,994 zero bytes at 5F1CF6..5FFF80 |
| Neo 3.21 | 410000..470000 | 393,216 | 119,026 FF bytes at 452E8E..46FF80 |

All intervals are half-open. The earlier packages' four extra file bytes are
also sent: AS3000's secondary stream ends **407BF0**, inside a rounded segment
ending 407C00 (16 bytes not sent); Neo05's secondary stream ends **406018**,
inside a rounded segment ending 406400 (1,000 bytes not sent). These small
remainders can stay FF following successful erase, unlike the main zero tails.
This refines the earlier logical-descriptor-only map. It does not make nearby
identity/recovery sectors independently available for library storage.

### Device path and zero handling

Neo13 SmallROM: request 17 at **401C24** records up to four base/length entries,
scales the host length by 1024, and erases containing sectors through **4022B8**.
Request 02 stages data; 0B at **401DB4** uses staged byte count **142A** and flash
cursor **1C56**, splits blocks at segment boundaries, and calls **402262**.
That wrapper copies **40230E..4023F4** into RAM and executes it. The worker's
**4023A6..4023DA** loop programs each source word, verifies it, advances by two,
and decrements count. It does not skip zero words or stop at a run of zeros.

Older workers have the same relevant count-driven behavior: Neo05 worker
**402126**, AMD byte program at **40227A**; AS3000 worker **402C96**, AMD byte
program at **402DFA**. Intel-compatible branches also program each supplied
byte, rather than treating zero as an end marker. Chip recognition/status failure
can prevent an update; these static paths describe successful supported updates,
not physical qualification for an unidentified board.

Neo13 has a separate explicit exception: **401DDC..401DE4** recognizes segment
base **5FFC00** and clears the staged count, discarding that compatibility block.
The host still sends it. Do not infer its final physical contents solely from
the package or count it as a guaranteed programmed trailer. It does not affect
410000..470000 or the library candidate tail. This special case is reflected in
the stream reconstruction rather than incorrectly treating all sent bytes as
programmed bytes.

## F-line ownership: inspected code and executed observations

A-line vector is RAM **28h**, F-line is **2Ch**. The main firmware initializers
write bus/address/illegal/divide vectors (08/0C/10/14) and A-line (28):

| Firmware | Initializer | A-line target |
|---|---|---|
| AS3000 3.01 | 4D0A3E | 4D12D4 |
| Neo 3.01 | 5D4A0E | 5D5320 |
| Neo 3.21 | 425A84 | 426768 |

These initializers do not install F-line. Neo13's private RAM-loader entry
418A06 additionally writes A-line at 418A1A and interrupt vectors 10C..118,
but does not write F-line. No stock F-line service/owner was identified in these
initialization paths. This is not a guarantee that every third-party applet or
unexamined factory/debug path leaves 2C alone.

The executable Neo13 fixture places a 16-byte handler at **458000**, inside the
confirmed main-ROM FF tail, in a private prepatched image. The handler advances
saved exception PC by two, writes a marker to disposable RAM, and executes RTE.
The test writes **458000** to vector 2C and executes real opcode **F123** from
RAM. It does not replace A-line or intercept/emulate the F-line exception.

| Observation | Vector 2C | Evidence |
|---|---|---|
| Original firmware cold startup | 00000000 | Full RAM capture |
| F123 dispatched to main-tail code and returned | 00458000 | Marker 464C494E and return-loop predicate |
| Normal warm startup via original entry 410082 | 00458000 | Full RAM capture and vector-write trace |
| Native RAM applet load through trailer 44FF80 | 00458000 | New RAM INIT marker 52414D49; A-line rewritten, F-line untouched |
| Emulator machine soft reset / SmallROM reboot | 00000000 | Full RAM capture; see model caveat below |

Warm-start testing uses the original startup entry, not an end-to-end USB
Manager restart. RAM loading first uses native file-capacity compaction, verifies
non-overlap with file/A5 allocations, and reserves the fixed RAM image region.
The handler and flash bytes are fixture preparation, not a successful updater
programming experiment. There are no screen, OCR, screenshot or model assertions.

### Reset caveat

`mame/src/mame/skeleton/alphasneo.cpp::machine_reset` explicitly copies the
first **100h bytes of SmallROM into SRAM** for reset-vector fetches. These source
bytes include zero at 2C. This copy bypasses guest write taps; no firmware store
to 2C was observed. Thus the reset result proves what this emulator does, **not**
that physical retained SRAM is necessarily overwritten at 2C. Actual reset boot
mapping/remapping must be checked on hardware or against a qualified bus model.
Neither physical power-cycle retention nor sleep/wake was qualified here.

## Installation and initialization direction

- Install a version/hash-qualified main-segment image containing the shared
  library, retaining existing OS addresses and trailer bytes. The existing
  addressed update backend can be driven by a future neotools feature while
  leaving SmallROM unchanged. For the older stock zero tails this requires
  erasing/rebuilding containing sectors, not just programming into erased cells.
  Neo13's initial FF placement may permit a narrower first installation, but
  updater command 17 itself erases sectors: it is not a no-erase map-only command.
- Include a library magic/version/extent and a stable dispatcher entry. Validate
  them before exposing F-line calls. Avoid A5-dependent static initialization
  assumptions: the caller's A5 belongs to the calling applet. Shared mutable
  state needs explicitly owned RAM/context and a defined ABI.
- Have the Betawise helper initialize vector 2C at startup, and let every client
  perform an idempotent `ensure_runtime` check before its first F-line call.
  Check the library image and current vector rather than assuming initialization
  ordering or persistent SRAM. Preserve interrupt state while replacing it.
- Reserve a defined F-line opcode subset, specify register/stack/result behavior,
  and define behavior for foreign F-line ownership and unknown opcodes. This
  fixture demonstrates exception dispatch/RTE, not a finished C-call ABI.
- A temporary installer can finish with a normal restart and let the startup
  path initialize dispatch. It must not free its own executing code/stack; a
  complete RAM upload/unload/installer lifecycle remains separate work.

A persistent main-ROM boot hook is optional if service must exist before any
Betawise client/helper executes. F-line dispatch itself does not require patching
the A-line table or SmallROM. The separate compaction-recovery hook remains a
separate responsibility and is not implemented by this experiment.

## Reproduction and retained evidence

From the workspace root, using fresh output directories:

```
python3 betawise/research/flash-b3/shared-library-init/trace-updater.py /tmp/updater-stream
python3 betawise/research/flash-b3/shared-library-init/vector-run.py /tmp/library-vectors
python3 betawise/research/flash-b3/shared-library-init/verify-vectors.py /tmp/library-vectors
python3 betawise/research/flash-b3/shared-library-init/verify-vectors.py /tmp/library-vectors
```

`HostRefs.java` finds string references/functions in a disposable Ghidra import;
original host disassembly/decompilation is retained privately in
`.research-work/shared-library-init/host-refs.txt` and `host-file-io.txt`.
The reconstruction retains per-block counts/checksums/hashes and disassembly
windows in `updater-final/`. It is a data-flow reconstruction from the traced
code, not a captured USB dialogue. No proprietary firmware/host image is copied
into this research directory.

The compact results-summary.json preserves the final assertions and reset
caveat; updater-stream.json preserves the notable stream/checksum table. Raw
RAM/vector traces and logs are regenerated with vector-run.py, then verified
by passing the new output directory to verify-vectors.py. They are not archived.
