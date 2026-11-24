# Native Manager transaction with a private RAM reservation

Checked 2026-11-23 against original Neo System 3.21. Archived firmware source is
excluded. All flash, RAM and applets are disposable fixtures; no physical USB
device or saved user session is accessed.

## Outcome and qualification

**The native Manager-layer install/remove plus actual warm-restart test passed,
with two explicit emulator adaptations. A complete neotools-over-USB test has
not passed.** The native RAM behavior agrees with the preceding bounded-phase
test, but is now reached by actual Manager requests rather than manually
applying the finalizer/removal bookkeeping.

Unmodified local neotools `install_applet`, `remove_applet`, `restart`, applet
enumeration and applet download functions sent their normal requests. The
original ROM parsed requests, staged/programmed an applet, finalized its
registration, removed it, adjusted markers/floor, and executed warm startup
through the native system transport poll/close callbacks. No installation or
removal outcome, successful firmware response, A5 base or post-install floor
was injected. Only initial heap reservation/guard/record seeding was test code.

The two adaptations must not be omitted when describing this result:

1. **Packet transport adapter.** The Python device implements read/write and
   dialogue methods using a bounded Lua mailbox into the original Manager
   packet handler and system open/poll/close callbacks. It passes input in
   eight-byte chunks. This replaces USB delivery and session establishment;
   it does not exercise descriptors, USB endpoints, controller IRQs or host
   enumeration. The initial directory was genuinely created by a cold boot
   from two preloaded test applets, not seeded RAM directory entries.
2. **Test-only NOR command-lane normalization.** The current emulator accepts
   the native byte CFI query but intentionally rejects byte-lane program/erase
   commands. Without an adaptation, the real program-block request returns
   **8C**, and the applet is not installed. The ROM was observed issuing
   byte-lane AMD unlock/A0 commands followed by word data writes. With the
   explicit fixture enabled, those command strobes are also supplied as
   low-byte-valued word commands to the existing NOR state machine. Original
   word data writes perform programming; original verification determines
   success. The fixture covers observed AA/55/A0/90/80/F0 command locations,
   not a new physical flash wiring contract. Production emulator code was not
   changed. There were 1582 normalized command strobes in the passing run.

The unadapted failure and raw bus command trace are retained. The passing run
also downloaded the installed image through neotools and checked every one
of its 1024 bytes against the generated applet before removal. Thus it does
not merely accept a success reply or register a pre-copied image.

## Actual observed sequence

Two generated 2048-byte-RAM applets are initially installed. Their callback
only clears the status result and, on plain INIT, stores an identifying long
at A5. It contains no RAM-clear, file or allocation routine. The third applet
requires 3072 bytes of RAM and is installed by the Manager transaction.

The test compacts native file capacity, lowers the live floor by 4096, fills
the heap with `5A`, and poisons both ordinary A5 blocks with `C3`. The first
two longs in each A5 are a heap pointer/size record.

| State | Floor | Applet 1 A5 | Applet 2 A5 | Applet 3 A5 | Gap below packed A5 |
|---|---:|---:|---:|---:|---:|
| Reserved / ordinary warm restart | `7B800` | `7D000` | `7C800` | — | `1000` |
| Install finalized, before restart | `7AC00` | `7D000` | `7C800` | `0`, not initialized | — |
| After install's native restart | `7AC00` | `7D000` | `7C800` | `7BC00` | `1000` |
| After removal's native restart | `7B800` | `7D000` | `7C800` | removed | `1000` |

All values are hexadecimal. The gap is 4096 bytes, not 0x1000 additional
bytes per applet.

The ordinary restart is requested with neotools' normal `08` request and
acknowledged by native `52`. A native transport poll performs the restart.
The A5/heap region remains byte-for-byte identical and the floor is retained.

The installation executes requests `06`, `02`, streamed data, `0B`, `07`
and receives native `46`, `42`, `43`, `47`, `48`. Before restart, the newly
registered applet has no A5 base and the init marker is zero. After `08/52`
and native warm startup, applet 3 has its newly computed base.

A ROM-read observer associated with `4173CC` records that **every byte in
`[7AC00,7D800)` is zero during startup**. A read tap can fire on a prefetched
branch target: this capture precedes completion of the base table and must not
be used as an instruction-execution breakpoint or proof of INIT ordering.
The executed-callback follow-up below establishes that ordering. The two
existing applets keep the same numerical A5 bases in this append-only case,
yet their old contents and heap records are gone. Their INIT callbacks run
again and place the identifying words `70000001/70000002`; the new applet
places `70000003`. All other bytes in their A5 blocks remain zero.

For removal, the test reuses the retained gap as a heap, poisons all three A5
blocks and seeds records again. This does not lower the floor a second time.
neotools sends `05`, receives native `45`, and its dialogue-end adapter invokes
the native close callback, which sees the invalid initialization marker and
performs warm startup. A second read-only observation finds `[7B800,7D800)`
entirely zero. The survivor callbacks reinitialize and enumeration no longer
includes applet 3. The gap remains 4096 bytes. Some lower old heap bytes lie
outside the new clear range and retain `5A`; that does not preserve a usable
heap or its erased record.

This removes the last applet and appends a new one; no applet reordering is
needed to reproduce the clearing. Both original applets' A5 addresses stay
unchanged across these operations.

## INIT ordering and reclaiming the bottom without a ledger

All applet A5 reservations/bases are computed **before** the first applet INIT.
Neo 3.21 completes the loop over slots 1..31 at `41738A..4173CA`; the separate
callback loop does not push plain `18` until `417624`. Data/BSS initialization
inside each applet's callback is later than address assignment for every applet.
The analogous ordering exists in the two earlier ROM disassemblies.

The read-tap timing limitation described above prompted an additional test:
the first test applet now records the floor, INIT marker, minimum nonzero A5
base, and slot 3's base using **executed 68000 instructions inside its INIT**.
With `--repair-on-init`, it also raises the floor to that minimum, but only
when the native applet-init marker is invalid and the floor is below it.
It allocates no new heap during INIT. Records go to dedicated disposable
observer RAM, not applet A5, and survive the subsequent comparison.

The complete original Manager transaction was rerun with that callback:

| INIT observation | Floor before | Minimum assigned A5 | Slot 3 base | Floor after repair |
|---|---:|---:|---:|---:|
| After install | `7AC00` | `7BC00` | `7BC00` | `7BC00` |
| After remove | `7B800` | `7C800` | `0` | `7C800` |

Both lost 4096-byte gaps were reclaimed. The executed INIT counter increments
from one at cold startup to two after install and three after removal. The
ordinary warm restart did not reinitialize or change the recorded heap/A5
region. The removal case reserves a fresh 4096-byte heap after install repair,
rather than assuming the now-reclaimed old gap still belongs to the test.

The optional callback is a test of the idea, not a production Betawise heap
implementation. It uses private, ROM-specific addresses and runs under the
same packet/NOR fixture qualifications as the preceding transaction.

A production protocol can therefore dispense with old heap pointers when
the whole applet runtime is deliberately discarded:

1. During **native global initialization**, derive the packed bottom from the
   completed A5 table, excluding slot zero/system and absent/zero base entries.
   In these ROMs the array begins 80 bytes below the floor variable (hex).
2. If the existing floor is lower, raise it to that bottom. This releases an
   unused tail back to file space; it does not require moving live file data
   or shrinking their capacities. Do not blindly shrink an unexpectedly high
   floor as part of this repair.
3. Defer fresh private-heap reservations until the initialization sequence has
   finished, for example until SETFOCUS. Multiple participating INIT callbacks
   can then repeat the repair harmlessly. If an earlier INIT reserves a new
   heap, a later repair could reclaim it: the deferral rule is essential.

Use the native initialization phase as a precondition, not arbitrary messages
that happen to contain code 18. The observed marker is still invalid during
these callbacks and becomes `2675` after their loop. A synthetic/redundant INIT
while other heaps remain live must not raise the floor over those reservations.
There is a concrete second producer, not just a hypothetical caller: native
RAM-applet registration sends plain INIT to the RAM-loaded instance. Its INIT
push/call sites are AS3000 `4C8C1A/4C8C24`, Neo 3.01 `5C8488/5C8492`, and
Neo 3.21 `418C3A/418C44`. On Neo 3.21 the trampoline enters `418A06`, uses the
RAM image at `5C000`, queries its ID with message `26`, installs/updates its
directory entry, and sets its A5 base to image-address plus header ROM size.
It then initializes that instance without executing the global A5 clear/repack
loop. The instruction sequences were checked against all three original ROMs;
this RAM-loader path has not been runtime-qualified by the Manager test.
It does not establish that ordinary focus changes reinitialize installed flash
applets. For an actual new RAM-loaded instance, initialization is appropriate;
the unsafe inference would be that all other applets' heaps were also discarded.

No dedicated all-applet pre-warm-reset notification has been identified.
The reviewed Manager restart/transport-close paths call the warm entry directly.
Foreground KILLFOCUS and transport-close callbacks are not a guaranteed reset
warning to every applet. The later INIT is not such a warning either.

If the last heap-aware applet is removed, no surviving callback will perform
this repair; reclaiming immediately in that case still needs prior release,
a remaining helper, or Manager/startup integration. A later compatible applet's
native INIT could repair it, but the temporary leak should be explicit.

No persistence mechanism is needed merely to recompute this bottom. Custom
configuration resources could encode heap records, but the identified resource
writer only serializes into caller-provided storage: it neither allocates a
configuration area nor supplies an automatic persistent key/value service.
Applet resources are addressed through header offset 0C, commonly in flash;
native startup applies settings via the 1D callback after INIT. Dynamic runtime
updates would need a qualified persistence path, rather than ordinary writes
through a resource pointer. No generic runtime configuration allocator/persistent
store has been established. Using settings for this repair would add machinery
without supplying information missing from the A5 table.

Repair evidence is retained in [repair-evidence](../results-summary.json).

```sh
python3 betawise/research/memory-allocation/manager/run.py /tmp/manager-init-repair --normalize-command-lanes --repair-on-init
python3 betawise/research/memory-allocation/manager/verify.py /tmp/manager-init-repair
python3 betawise/research/memory-allocation/manager/verify.py betawise/research/memory-allocation/manager/repair-evidence
```

## Executed private RAM-applet loader

The additional `--ram-loader-only` test qualifies the private Neo 3.21 RAM
entry in the emulator. It does not send INIT twice to a running installed
instance: it introduces a **new RAM-loaded instance** while the two flash
instances retain their original A5 allocations and live state.

The normal full image's trailer at `44FF80` resets SP to `7FFF0`, clears A6,
and jumps to `418A06`. A duplicate trailer at `46FF80` has the same entry.
The loader expects an applet image at fixed RAM address **`5C000`**. It sets
the prospective A5 to `image + header.romUsage`, calls message **26 / GET_ID
before INIT**, registers/finds the slot, supplies the RAM header and A5 base,
calls plain **18 / INIT**, then enters the regular foreground loop. This is
a jump/handoff entry, not a returning public syscall.

The test prepares a 1024-byte position-independent image with 2048 bytes of
working RAM, explicitly handles GET_ID before touching initialized state, and
initializes its A5 identifying word on INIT. It first compacts native file
capacity and verifies files fit below `5C000` and installed A5 lies above the
image/work extent. It reserves the fixed RAM region by lowering the floor,
loads the generated image at `5C000`, and jumps to the actual trailer.

Executed observations:

- The ROM registers new ID `7010`, header at `5C000`, A5 at **`5C400`**.
- Code inside its INIT records the global-init marker as **`2675`**, already
  initialized, and the floor as `5C000`.
- Both existing 2048-byte A5 blocks remain byte-for-byte `C3`; the global
  A5 clear/repack loop did not run.
- The new RAM applet appears in native Manager enumeration.
- No command-lane normalization or runtime flash programming is needed.

This makes RAM loading useful for emulator development without reflashing the
test applet on each iteration. It also gives a concrete reason not to treat
every INIT as permission to discard other applets' heaps.

A general physical-device uploader/unloader is **not implemented**. The local
neotools CLI has no identified RAM-upload/run operation. A physical workflow
would need a qualified RAM transfer/debugger or small loader applet, plus
reservation/lifetime management. Do not simply overwrite `5C000` and jump:
that address can belong to files or other allocations. Existing Betawise C
startup initializes relocations/GOT on INIT; GET_ID is earlier, so an adapter
must answer it without relying on uninitialized C state. The minimal assembly
entry used here demonstrates that requirement; arbitrary built applets have
not been qualified for this loader. Unloading, repeated replacement, package
changes and reset while the RAM instance is present remain unqualified. The
test deliberately ends the disposable emulator session instead.

### Proposed DebugTool file-backed loader

Add **Load/run in RAM** to DebugTool, using an OS3KApp image stored as an ordinary
binary file in DebugTool's own file table. Uploading the image through Manager's
file transport would avoid a separate loader applet or new USB protocol for the
initial workflow. The complete binary transfer and launch path is proposed,
not yet tested. DebugTool needs file enumeration/selection and image validation;
the existing file syscalls suffice without a generalized stdio layer. The
device filename need not include the host's `.OS3KApp` extension.

Before the nonreturning ROM handoff, validate the header, logical image length,
entry offset and image/workspace extents, reserve RAM against files/A5, and copy
the image to the firmware-specific address. Account for the source file's RAM
usage and compaction moving its references; source and destination must not
overlap. Retain the GET_ID-before-INIT startup requirement. Initially target the
Neo 3.21 loader exercised here; qualify unload/replacement, reset and Manager
changes, then physical hardware and other firmware versions. Label this as
transient RAM loading, rather than persistent installation.

The companion [USB/Manager command audit](../../usb/ram-applets.md)
records why the existing flash-install commands do not supply this operation.

```sh
python3 betawise/research/memory-allocation/manager/run.py /tmp/ram-loader --ram-loader-only
python3 betawise/research/memory-allocation/manager/verify-ram.py /tmp/ram-loader
python3 betawise/research/memory-allocation/manager/verify-ram.py
```

[RAM-loader evidence](../results-summary.json) retains exact executed Lua,
assembly, protocol headers/hashes, two full RAM records and assertions. The
first two test applets are initially seeded into disposable flash for genuine
cold directory initialization. That preparation is distinct from programming
flash during a test or communicating with a physical device.

## Last heap-aware applet removed

Once no compatible code remains installed, a per-applet INIT hook cannot fix
the floor. A persistent ledger alone cannot execute the repair either. There
are three concrete policy choices:

- Teach the installation/removal workflow to release or coordinate the arenas
  **before** removal. Our own installer can support this, but unmodified vendor
  tools cannot be assumed to follow the new protocol.
- Retain a small compatible helper (possibly an already-required font/support
  applet) to perform the global-INIT repair. It need not provide a shared heap
  or maintain a per-object allocation table.
- Accept a temporary RAM leak when the last compatible applet is removed.
  The next compatible applet's global INIT can repair it. An ordinary warm
  restart by itself does not guarantee reclamation. Do not recommend a
  file-destructive full reconstruction just to recover that gap.

Preserving heap objects across ordinary focus changes rules out automatically
freeing them on every KILLFOCUS as a transparent solution. Releasing all arenas
in a pre-removal maintenance workflow and retaining them on normal focus loss
are different lifetime policies. There is no demonstrated fourth mechanism in
stock firmware that automatically accounts for unregistered private arenas.

## USB attempt

A separate localhost DUSB attempt reached a genuinely initialized native
directory (`2675` init marker). The controller reported VBUS present but
peripheral mode disabled. Reset and descriptor SETUP returned transport status
3 (timeout), so no native USB Manager session was established. State and
packet logs are preserved in `evidence/usb-attempt*`. Earlier attempts made
before cold-start completion are not counted as evidence of that boundary.

The original cold-start choice routine was observed through its allowed-key
vector, and native Y/Enter matrix events supplied the expected fresh-RAM
responses. Read taps are installed only after the machine starts. No screen
is decoded, no screenshots/models are used, and no firmware-menu acceptance
is claimed. The passing Manager-layer test uses the same native startup and
subsequent full warm-restart path, with interrupts initially masked for RPC
entry. Warm startup restores its own normal execution state.

## Hidden files and persisted heap records

There is still **no qualified native hidden-file flag**. Native file flags
01/04/08 are incompletely understood, and 02 participates in current-file
selection. The native editor's hidden *text-region* bit is not a file flag.
The known hidden-*applet* flag also does not establish hidden-file behavior.
Do not repurpose one of these flags based on its numeric value.

A reserved filename/tag can let Betawise wrappers or FileManager explicitly
filter/protect an internal metadata file. That is a convention those clients
must implement; it does not make the file absent from generic Manager tools.
The current FileManager prototype rejects moves of files with 01/04/08 rather
than treating them as an established hidden-file policy.

A file could retain a reservation ledger when A5 is reinitialized, helping
detect discarded reservations and reclaim/rebuild them under a coordinated
policy. **Saving pointers alone does not preserve the heap:** its bytes have
been cleared, and the new applet's A5 may occupy its old addresses. Checkpointing
arbitrary malloc objects would require their data and a valid restoration/
relocation strategy, not just the ledger. Preserving normal runtime state
across package changes needs a separate design.

## Reproduction and evidence

From the workspace root, with new output directories:

```sh
# Expected to fail at native program-block response 8C with the current NOR model:
python3 betawise/research/memory-allocation/manager/run.py /tmp/manager-unadapted

# Explicitly qualify Manager/RAM behavior with the test-only command-lane assumption:
python3 betawise/research/memory-allocation/manager/run.py /tmp/manager-lanes --normalize-command-lanes
python3 betawise/research/memory-allocation/manager/verify.py /tmp/manager-lanes

# Verify the preserved passing observations:
python3 betawise/research/memory-allocation/manager/verify.py
```

The runner never discovers or opens physical USB devices. It uses original
neotools functions through its explicitly constructed PacketTransport object.
The [manifest](../results-summary.json) records ROM, emulator, client and script
hashes. Evidence includes eleven full-RAM captures, protocol headers/hashes,
raw flash command traces, native logs, readback hash and the two full-clear
observations. Original ROM/flash images are not included in maintained evidence.
This run qualifies Neo 3.21 Manager logic; it does not extend the actual
transaction claim to AS3000/Neo 3.01 or physical hardware.

Historical raw Manager traces/captures are regenerated, not archived. Run the
matching verifier with the new output directory; its prior default evidence
directory is no longer a repository input. See ../results-summary.json.
