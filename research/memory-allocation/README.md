# Runtime allocation and borrowed-memory re-audit

Checked 2026-11-23 against the three inventoried system ROMs and all 56 original
applet images in the current vendor inventory. This investigation distinguishes
an allocation of independently owned RAM from a pointer to already reserved
firmware storage. No user session or physical device was modified.
Archived firmware source is excluded from consideration. Evidence here is from
the inventoried binaries, their disassembly, and disposable emulator execution.

Follow-up: [private pool search and independent RAM-floor reservation](pools-and-floor.md).
The latter passed a synthetic three-ROM experiment, but still needs lifecycle
coordination before it can provide persistent heap storage.
The [startup/install/remove follow-up](lifecycle.md) demonstrates that a RAM
repack can erase heap records without releasing their reserved space, and
qualifies a shorter register-based method of finding the boundary variable.

Follow-up: [public-file-call compaction and saved-length side effects](public-file-reservation.md)
executes FileClose plus FILE_LENGTH_SNAPSHOT_ALL on all three ROMs. It removes
the direct private ROM call, but changes saved-length restore semantics.

Follow-up: [saved-length consumers and preserving public compaction](saved-lengths-and-public-compaction.md)
qualifies public create/delete compaction and its low-memory clipboard/snapshot fallback.

## Conclusion for stdio and general malloc

There **is** an established vendor pattern for small, one-time allocations:
suballocate the Neo 3.21 firmware's shared **8192-byte scratch arena**. It is
real and executable, not just an interpretation of a pointer-return syscall.
However, it has no system-managed allocation records, free, ownership, or
cross-focus preservation. It therefore does not solve the requirement for
stable, persistent FILE/DIR records while another applet runs.

No supported syscall for requesting an additional independently owned,
stable-address RAM/A5 block was identified in this re-audit. This is a bounded
finding from the public slot inventory, dispatcher inspection, reviewed vendor
patterns and existing message-provider audit, not proof that no private or
indirect allocator exists anywhere in proprietary code.

## Candidate inventory

| Mechanism | Established memory source | Allocation/lifetime limits |
|---|---|---|
| CallSysInt `3000` / `5000` | Neo 3.21 fixed scratch area, `0x5DBE..0x7DBD`, 8192 bytes | Borrowed shared arena; applet-local bump allocators; no lease/free/owner tracking. Unsupported on AS3000 3.01 and Neo 3.01. |
| Vendor local allocator | Slices of the area above | Byte-count allocation until full; reset on reacquisition; not a second firmware heap. |
| USB, Hub, print and IrDA message buffers | Firmware-provided input/output buffers in transport callbacks | Use the request's capacity and callback contract; borrowed transport storage, not allocation grants. |
| Wireless packet/transfer buffers | Fixed firmware packet and manager state | Shared with transport state machines; packet-length limits are not heap allocation sizes. |
| FontDialogCreate / Destroy | Neo 3.21 twenty-object pool; 1504 bytes per private object | Allocates a defined dialog object, not arbitrary bytes. Firmware uses its headers/regions and retains current-object references. Do not repurpose as malloc storage. |
| TimerStart / Cancel | Five shared timer slots | Allocates timer state, not a caller-owned data block. |
| FileCreate / file capacity | Firmware-managed file RAM, at least 512 bytes initially | Actual dynamic byte storage, but buffers can relocate; use refreshed bindings or offsets. Not a stable raw-pointer heap. |
| ClipboardResize | Global clipboard's file buffer | Resizable shared clipboard state; relocation and other clipboard users make it unsuitable for private persistent handles. |
| SaveScreen / text shadow | Shared firmware display state | Dialogs and later saves can replace it; not an ownership/reservation interface. |
| Installed applet A5 | Each applet header's declared RAM allocation | Established stable applet-owned arena during ordinary operation; installed reservation rather than a runtime extra-block request. |
| Automatic C storage | Current callback's hardware stack | Useful for bounded temporary objects; cannot back handles retained after callback return. |

An earlier chat's source-derived pool claim was mistakenly carried into this
audit and has been withdrawn. It is not an allocation candidate or evidence for
the supported ROMs. The twenty-object dialog pool above is independently
identified in the Neo 3.21 binary.

## Scratch query: static and runtime evidence

`CallSysInt` is slot 174 / `A2B8`. The queried selector is separate from that
opcode. Caller storage receives the pointer/capacity; the function's low-byte
return says whether the selector was handled. Unsupported queries leave caller
output unchanged, so callers must initialize/check it.

| ROM | Dispatcher | `3000` / `5000` result |
|---|---|---|
| AS3000 3.01 | `0x4D0EEE` | Both false; sentinel and adjacent canary retained. |
| Neo 3.01 | `0x5D4ECC` | Both false; sentinel and adjacent canary retained. |
| Neo 3.21 | `0x425F42` | Both true; pointer `0x5DBE`, capacity `0x2000`; adjacent canary retained. |

Neo 3.01's dispatcher rotates the selector word and rejects values above 6;
it has no `3000/5000` branch. Neo 3.21's sparse selector table has both:
`0x426142` writes immediate pointer `0x5DBE`; `0x42614A` writes immediate
capacity `0x2000`. These are plain constant queries, not allocation routines.

The fresh original-code probe loads the complete original MathFacts Offline
image into disposable RAM and executes its position-independent initialization
and allocator routines without patching them. No UI routine is exercised.

MathFacts file offsets:

- `0x961C`: reset the 16-bit local allocation offset at `A5+0x492`, query pointer
  into `A5+0x494`, and capacity into `A5+0x48E`; clear pointer/size on failure.
- `0x9680`: read the low-word requested byte count, check used+requested against
  capacity, return base+used and advance the local offset, or return NULL.

Fresh execution assertions:

1. Original helper initialization succeeds on Neo 3.21 and yields NULL/zero
   on the two older ROMs.
2. Requests of 1024, 4096, and 3072 bytes return consecutive slices totaling
   exactly 8192. The next one-byte request returns NULL without advancing.
3. Initializing the same helper in another independent A5 context yields the
   **same** base; its first 16-byte allocation overlaps the first caller's
   allocation. The first context's counter remains 8192 and the second is 16.
   This establishes the absence of allocation ownership in these helpers and
   queries, not a claim that two foreground applets execute concurrently.
4. After reset, allocations of 1 and 3 bytes return base and base+1. There is
   no word alignment. A zero-byte request returns base+4 without advancing.
   A general allocator over this area would need its own alignment policy.

The existing applet-dispatch transcript independently places the reset helper
in MathFacts Offline's `MSG_SETFOCUS` arm, after a firmware-version check for
at least 3.09. The routine initializes its local offset again rather than
resuming a persistent allocation ledger. We have only executed availability on
3.01 and 3.21; the vendor's 3.09 guard does not certify every intermediate ROM.

## Vendor call census

[scan.py](scan.py) checks hashes for all 56 inventoried images, emits raw
68000 disassemblies, recognizes syscall export neighborhoods, and records
nearby-register indexed/direct call candidates. The
[census](vendor-census.json) retains every image hash, header RAM size,
service candidate counts and scratch-call contexts.

Resolved scratch-query patterns:

| Applet | Query call offsets in original image |
|---|---|
| MathFacts Offline | `963C` pointer; `9668` size |
| Responder | `7784` pointer; `77B0` size |
| Wireless File Transfer | `B18E` pointer; `B1BA` size |
| KeyWords Wireless | `12F0A` pointer; `12F36` size |
| Wireless Updater | Pointer queries at `C6C`, `ED4`, `12D6`; the latter forms a second address at base+2048. |

The first four use the paired query/local-offset allocation pattern documented
in the earlier [system-service investigation](../syscalls/system/README.md).
Wireless Updater uses borrowed arena addresses directly, including a 2048-byte
partition offset. That offset is not a new firmware allocation or a universal
maximum allocation size.

The scanner excludes literal-only matches: for example, AlphaQuiz has an
unrelated immediate `3000` near a real `0300` row-height query in the older
exploratory scan. It is not counted as a scratch allocation here. Calls through
unresolved register-loaded function pointers and private allocator algorithms
are not exhaustively recovered by this short scanner. The broader
[message-dispatch audit](../syscalls/applet/dispatch-audit.md) covers all 56
applets' resolved callback graphs and explicitly retains its indirect-call
limitations. No reviewed provider message family establishes a generic RAM
allocator.

## USB/wireless distinction

The shared transport request contains input length/pointer and output
capacity/length/pointer. Existing dispatch research establishes, for example,
a PS/2 initial capacity of `0x400`, an AlphaHub output buffer at `0x35FC` with
capacity `0x3FC`, and print chunks up to `0x400`. Those sizes describe supplied
communication buffers. Their addresses and capacities are not requests to
reserve memory, and returning from a callback does not grant persistent use.
See the [transport contracts](../syscalls/applet/dispatch-audit.md#transport-pumps-and-payloads).

Wireless receive/send similarly operates on fixed packet/transfer state,
retained callbacks and borrowed network information. A callback or pointer
result does not give an application ownership of those blocks. The
[wireless investigation](../syscalls/wireless/README.md) distinguishes buffer
bounds, asynchronous operation and callback lifetime. Focus loss alone has
not been shown to cancel all asynchronous firmware activity.

## Reproduction and evidence

From the workspace root (output directories must be new):

```sh
python3 betawise/research/memory-allocation/scan.py /tmp/allocation-vendor-census
python3 betawise/research/memory-allocation/run.py /tmp/allocation-runtime
python3 betawise/research/memory-allocation/verify-evidence.py /path/to/new-output
```

The runner constructs fresh flash/RAM fixtures for all three ROMs, uses the
existing local MAME binaries, and has bounded guest call deadlines and a host
process timeout. It intentionally abandons the disposable boot context and
masks interrupts while executing the non-UI test functions. No screen capture,
font decoding, pixel acceptance or model inference is involved.

[Evidence manifest](results-summary.json) records original input hashes,
logs, and raw/compressed RAM hashes. Committed compressed RAM captures and
per-ROM logs retain the returned state. A successful test does not qualify
radio hardware, USB ownership, UI dialogs, scratch persistence across actual
applet switches, or a production allocator.

For a temporary foreground micro-heap on suitable Neo firmware, the arena is
a concrete candidate and vendor precedent. Before production use, qualify
which nested firmware operations can reuse it and how focus/transport changes
end its lifetime. For handles required to survive focus changes it needs
separate persistent backing or coordinated ownership; it cannot be treated as
an applet-private stable malloc heap merely because its address is constant.

Retention: the compact results-summary.json and topic tables retain outcomes.
Raw captures, generated probe copies and logs named above describe historical
output locations; regenerate them with the documented runner in a fresh
directory and pass that directory to the verifier. They are not repository inputs.
