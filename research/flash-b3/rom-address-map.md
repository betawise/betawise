# Shared library placement outside SmallROM

Read-only local package/header/disassembly inspection, 2026-11-23. SmallROM
and its surrounding recovery allocation are excluded from library placement.
No source ROM, saved session or device was modified. A package map is not a
complete physical flash dump, and padding is not proof of semantic non-use.

Follow-up: [actual updater stream and F-line lifecycle](shared-library-init/README.md)
confirms that stock updates send the older zero-filled main tails. It also
refines the older secondary programmed extents and identifies the Neo13
compatibility-segment discard; the map below describes package destinations.

## Reproduction

From the workspace root:

```
python3 betawise/research/flash-b3/rom-address-map.py
```

The checked-in JSON records package hashes, descriptor destinations, logical
lengths, 2013 rounded transfers, and both zero and FF runs >=256 bytes. Raw
aligned longword matches are retained as leads, not classified references.
For example Neo05 offset 25C76 is the juxtaposition of `pea $5f` and `jsr (a3)`;
Neo13 offsets 111C and 1244 similarly combine constants with adjacent opcodes.
Their numeric matches into padding are not actual address operands. Absence of
such matches cannot exclude PC-relative/computed references or checksum reads.

## Address maps (all intervals half-open)

### AS3000 System 3.01, November 2005

- 400000..404000: reserve recovery, including SmallROM and its omitted tail.
- 404000..407BEC: secondary system descriptor, 15,340 logical bytes. The file
  has four more bytes after all logical segments; do not silently count them as
  usable flash or assume the 2013 transfer-rounding rules apply.
- 407BEC..408000: only 1,044 bytes between the logical secondary end and applets;
  not qualified, and not an independently erasable library allocation.
- 408000..4C0000: applet region (736 KiB), not a firmware gap. Manager admission,
  free-space, scanning, validation and erase-all use this boundary independently.
- 4C0000..500000: main OS segment (256 KiB), including trailer 4FFF80..500000.
- 4EB4D2..4FFF80: 84,654 consecutive zero bytes within that main segment.

No storage beyond 500000 is established by this 1-MiB model. A CPU address after
the ROM is not evidence of additional physical flash.

### NEO System 3.01, November 2005

- 400000..406000: reserve recovery, including SmallROM and its omitted tail.
- 406000..406014: 20-byte secondary system identity descriptor. Four trailing
  package bytes are outside the summed logical descriptors.
- 406014..408000: 8,172-byte logical-package omission, not a proven empty
  partition. It shares the identity/configuration neighborhood; physical dump,
  updater transfer extent and erase ownership are unresolved.
- 408000..5C0000: applet region (1,760 KiB). Verified at erase-all 5C1F50/56,
  scanner 5C2E3E/5C2E8C, capacity replies 5C1022/5C2522 and validator 5C30CA.
- 5C0000..600000: main OS segment (256 KiB), trailer 5FFF80..600000.
- 5F1CF6..5FFF80: 57,994 consecutive zero bytes inside the main segment.

The layout covers 2 MiB starting at 400000. The emulator's larger 4-MiB flash
array does not establish a spare 600000..800000 bank on physical Neo05 hardware.
Even with a larger fitted chip, mapping/aliasing, ownership and programming would
need separate confirmation; this firmware's applet bounds stay at 5C0000.

### NEO System 3.21, July 2013

- 400000..406000: reserve recovery, including SmallROM and its omitted tail.
- 406000..406400: secondary system transfer (20 logical bytes, 1-KiB rounded
  transfer). Its zero fill is transferred by the updater, not omitted storage.
- 406400..410000: 39,936 bytes omitted by these package transfers. Candidate
  only: physical contents, configuration usage and erase ownership unqualified.
- 410000..470000: main OS segment (384 KiB). Keep both trailer copies at
  44FF80..450000 and 46FF80..470000; SmallROM really calls trailer entries.
- 44FB26..44FF80: 1,114 zero bytes before the earlier trailer.
- 452E8E..46FF80: 119,026 FF bytes before the later trailer.
- 470000..runtime end: applet region. Initialization at 417094..4170E2 probes
  capacity and stores start at RAM E8A and exclusive end at E8E. For capacity
  greater than 2 MiB: end = 400000 + capacity (800000 for 4 MiB). For <=2 MiB:
  end = 3F0000 + capacity when byte 400414 is zero, otherwise 400000 + capacity
  (5F0000 or 600000 for 2 MiB). Do not write that SmallROM byte to change limits.
  Validator 41331E..413354 consumes these runtime bounds.
- 5FFC00..600000: separate 1-KiB system-package transfer with an older-address
  trailer at 5FFF80. On the 4-MiB layout this is numerically inside the broad
  applet interval, so it is not a separately available post-OS hole. Package
  installation order and the lifetime of this compatibility copy need review
  before claiming coexistence with arbitrary applet writes over that address.

No extra bank after 800000 is established. Main-ROM movement between releases
changes which addresses belong to applets; empty space on one version cannot
be assigned as a cross-version absolute library address without checking this.

## Practical library candidates

| Firmware | Main-segment padding candidate | Bytes | KiB |
|---|---|---:|---:|
| AS3000 3.01 | 4EB4D2..4FFF80, zero fill | 84,654 | 82.67 |
| NEO 3.01 | 5F1CF6..5FFF80, zero fill | 57,994 | 56.63 |
| NEO 3.21 | 452E8E..46FF80, FF fill | 119,026 | 116.24 |

These are real package-backed padding extents, not a claim that all bytes with
that value are unused. No complete independently blank 64-KiB block exists in
any listed main tail: the last block includes its trailer, and any preceding
block is partly occupied. These ranges remain candidates until reference,
integrity and update-path behavior is qualified. The common size ceiling of
these three large candidates is 57,994 bytes before library metadata/alignment.

Zero-filled NOR needs erase to change any bit to one. Therefore AS3000/Neo05
need an affected-sector rebuild or modified main-system update, preserving
firmware/trailers; they cannot use a simple program-into-erased-bytes operation.
Neo13's FF tail may permit initial programming without erasing, but replacement
still requires the correct chip/sector protocol and preservation of its neighbors.
Normal applet erasure lies outside these main tails; system updates can replace
them. A library design must handle firmware-version-specific placement/lifetime.

## neotools implications and remaining qualification

Current applet installation uses 06/02/0B/07: destination is firmware's append
cursor, not a host-selected address. Raw block upload 02 is RAM staging, not an
arbitrary flash write. 16/17/18 are system-update-related protocol constants;
local neotools does not implement a qualified targeted library installer with
these. Adaptation is feasible, but requires reconstructing and exercising the
system-update contract or adding a maintenance applet's bounded writer.
Neither route requires modifying SmallROM itself. Executing stock SmallROM as
the existing updater is different from storing library code in its allocation.

Before enabling writes: identify physical capacity/geometry and obtain full
readback (especially omitted ranges); resolve runtime reads/checksums over the
chosen tail; qualify a modified system image and library call path on disposable
flash; then verify actual erase/program/readback/error behavior while preserving
all firmware and trailer bytes. A cold boot alone would not prove every firmware
feature or updater leaves the candidate unused. This report establishes maps and
candidate capacities, not a deployable writer or hardware-safe allocation.
