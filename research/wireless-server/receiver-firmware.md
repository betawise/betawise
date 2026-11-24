# Receiver 01.20 firmware and Neo radio-module pairing

Static analysis of the receiver update bundled with NEO Manager 3.9.3.
**Result: the receiver uses a CC2420-compatible radio interface and implements
IEEE 802.15.4 MAC behavior in firmware.** A programmable nRF52840 remains a
strong replacement candidate at the radio level. No RF interoperability or
complete receiver replacement has been demonstrated.

No vendor code was executed, and no receiver/Neo firmware was flashed. Ghidra
disassembly/decompilation and deterministic binary checks ran locally. The
Neo display was not used as an oracle. Original source hashes are in
[package-inventory.json](package-inventory.json).

## Receiver container decoded

[decode-receiver.py](decode-receiver.py) reconstructs the reviewed receiver
package with explicit bounds, map, geometry and checksum checks. It rejects
other device/version layouts instead of applying this interpretation to them.

| Property | Verified value |
|---|---|
| Source | `Renaissance Receiver_0120.fud`, SHA-256 `41c645a87467f36ee2a9ff1970d3c0beaf41fce2ee5695f6cdbc8d94ecc5a2a1` |
| Header/data marker | Header occupies the initial 1024-byte area; `---- DATA BLOCKS ----` begins at file `0x400` |
| Payload | File `[0x415, 0x1c415)`, 114688 bytes / 112 KiB |
| Map | `---- BLOCK MAP ----` immediately precedes header-declared MapPosition `0x1c428` |
| Map prefix | Bytes `e1 0b`; meaning unassigned |
| Map entries | 448 pairs of little-endian uint32 **flash address, absolute file offset**, following the two prefix bytes |
| Page geometry | 256 bytes; all addresses and file offsets advance by 256 with no gaps/duplicates |
| Flash span | `[0x00104000, 0x00120000)` |
| Checksum | Sum of mapped payload bytes modulo 256 = **216**, matching the header |
| Decoded SHA-256 | `a8a336bc5129687a8153017c80f191af2b4a7a28caff49d16a7df2bffeb9814d` |

This is an application update, **not a full flash/bootloader dump**. The header
advertises bootloader 01.08; the package does not give us its complete contents.
Configuration values loaded from RAM/EEPROM cannot be inferred from reset-state
guesses. The checksum finding is scoped to this receiver file; other FUD device
families need independent decoding/checksum analysis.

## Processor and disassembly limits

ARM and Thumb instructions are present. Constants reference SPI TDR/RDR/SR at
`0xfffe000c`, `0xfffe0008`, `0xfffe0010`, USB at `0xfffb0000`, PIO at
`0xfffff400`, and timers at `0xfffa0000`. Together with flash near `0x00100000`
and SRAM near `0x00200000`, this is consistent with **Atmel AT91SAM7S-family
ARM7TDMI hardware**. It does not identify the precise chip/package without a
board marking or further device-ID evidence. Compare the manufacturer's
[SAM7S128 datasheet](https://www.keil.com/dd/docs/datashts/atmel/at91sam7s128_ds.pdf).

Ghidra imported the reconstructed bytes at `0x104000`, language
`ARM:LE:32:v4t`. The initial branch vectors are encoded for a low vector alias:
for example the first word `ea04102e`, evaluated at PC 0, targets `0x1040c0`.
Do not interpret it as a normal branch executed at `0x104000`.

Automatic decompilation is **not authoritative** here. The compiler uses a
nonstandard interrupt-save/return sequence:

- Thumb veneer `0x10bc60` enters ARM helper `0x10bc64`, saves CPSR on the stack,
  masks interrupts, and returns to the Thumb caller.
- Veneer `0x10bc90` enters `0x10bc94`, pops saved CPSR **and the enclosing
  function's saved LR**, restores CPSR, and returns from that enclosing function.

Ghidra consequently marks some helpers non-returning and invents arguments/
return combinations. Some main-loop boundaries and indirect calls are also
unrecovered. Findings below use explicit instruction sequences and literal
bytes, not guessed decompiler prototypes. [receiver-instructions.txt](README.md#reproduction-and-verification)
preserves reviewed instruction ranges. Full generated disassembly, decompilation
and logs remain with the private decoded images.

## Radio identification and configuration

The following **combination** identifies the CC2420 register/command interface,
rather than merely the frequency band:

| Routine/address | Observed behavior |
|---|---|
| `0x1062b8` | SPI byte exchange, using the peripheral registers listed above |
| `0x106308` | Register write: address byte, high data byte, low data byte |
| `0x10633c` | Register read: address OR `0x40`, two data bytes |
| `0x109ab8` | RX FIFO access using command `0x7f` |
| `0x109afc` | TX FIFO access using command `0x3e` |
| `0x107ce4` | Writes MDMCTRL0 `0x11`, MDMCTRL1 `0x12`, IOCFG0 `0x1c`, SECCTRL0 `0x19`, RXCTRL1 `0x17` |
| `0x107d2e`–`0x107d5a` | Radio RAM writes to PAN ID `0x168`, IEEE address `0x160`, short address `0x16a` |
| `0x1097c4`, `0x1097d8` | Validate/program channel **11 through 25 inclusive** |

The register map, FIFO commands, and address RAM locations agree with the
[TI CC2420 datasheet](https://www.ti.com/lit/ds/symlink/cc2420.pdf). This is
strong firmware identification of a CC2420-compatible device; a physical board
inspection would establish the exact installed part/revision.

At `0x107ce4`, MDMCTRL0 is initialized to `0x0ae2` or `0x0be2`, selected by a
RAM flag. The two literal values are at `0x107d78`/`0x107d74`. Both enable
hardware CRC and address decoding, retain the normal preamble-length setting,
and leave AUTOACK **clear**. MDMCTRL1 is `0x0500`; IOCFG0 is `0x0203`.
SECCTRL0 is explicitly written **zero** at `0x107d10`–`0x107d14`, disabling
the radio's inline security mode at this initialization point. This is not a
proof that application payloads never use authentication/encryption or that
no later path can alter security behavior.

Channel programming writes FSCTRL `0x18` with:

```text
value = 0x412e + 5 * channel
center_frequency_MHz = 2048 + (value & 0x3ff)
                     = 2405 + 5 * (channel - 11)
```

The constant `0x412e` is at `0x109860`. This gives the standard channels
2405–2475 MHz for the firmware's accepted range. Channel 26, although supported
by the CC2420, is rejected by these routines. Both this restriction and the
formula are supported by code, not inferred from the manual's “15 channels.”

## MAC behavior and host framing

`0x10987c` constructs a conventional 802.15.4 MAC header: frame type, optional
security flag, ACK request, PAN compression, sequence number, little-endian PAN
IDs, and 16-bit/64-bit address modes. It maintains separate beacon and other
frame sequence counters. It does not insert a Zigbee network header here.

`0x1071a4` constructs beacon contents including superframe fields and pending
information. `0x1070d4` constructs MAC command **8**, with PAN ID, coordinator
short address, channel and device short address—the coordinator-realignment
command layout. `0x1085e4` dispatches received MAC commands including association
request/response, disassociation, data request, beacon request and realignment.
These are concrete MAC-level leads for an open coordinator implementation.
They do not establish a Zigbee network-layer stack or mesh routing.

ACK handling needs attention: the receive state machine at `0x108980` issues
strobe **10 (`SACK`)**, and another path issues **11 (`SACKPEND`)**, rather than
leaving AUTOACK enabled unconditionally. The transmit state machine at
`0x10a67c` uses `STXONCCA`/`STXON` and writes the constructed MAC header and
payload to the FIFO. Timing-sensitive MAC work must live on the replacement
radio MCU, not depend on desktop USB scheduling.

There is also a **separate USB report transport**. At `0x1042d4` outgoing
messages are fragmented into 64-byte buffers:

| First report bytes | Content |
|---|---|
| 0–1 | `5a a5` |
| 2 | First/last flags: bit 0 first, bit 1 last |
| 3 | Sequence/tag byte, shared across continuation fragments |
| 4–7 | Total payload length, little-endian uint32 |
| 8–9 | Little-endian uint16 message identifier supplied to the routine |
| 10–63 | Up to 54 initial payload bytes |

Continuation reports use the same four-byte prefix and up to 60 payload bytes.
`0x1043c8` performs the corresponding reassembly and checks tag/length. This
is not the Neo processor's `a5` SPI framing and is not an over-the-air header.
HID report-ID/API wrapping still needs to be correlated with the Windows
`SaturnUplinkComm` code or a USB capture.

## Neo-side firmware recovered from Wireless Updater

The unchanged Wireless Updater applet contains **two actual radio firmware
resources**, not just the 68k updater application.
[decode-neo-modules.py](decode-neo-modules.py) validates their record geometry,
terminator and resource size/name metadata, then preserves ordered records and
reconstructed physical flash images.

| Resource label | Applet start | Records | Reconstructed SHA-256 |
|---|---:|---:|---|
| `01.30` | `0x17f2` | 2438 | `669fb7f797d8b9f97df3f6b6ee01bbe198dfc86bfe6eb25ba8b2c18e2b3f7753` |
| `02.00` | `0xccf2` | 2662 | `7c2795b1188e67b7f399c18fe082bad8e4da29f82d6b34b822afb6331302a725` |

Records are a big-endian **24-bit physical flash address plus 16 data bytes**.
`ff ff ff` terminates a resource; subsequent `N`, big-endian size and NUL-ended
name fields independently confirm the resource boundaries. Unspecified flash
bytes are filled with `ff` in the reconstruction. Resource `02.00` writes
`0x1fff0` twice: the second write changes the final version-like bytes from
`2.0  ` to `02.00`. Both original records are retained; the reconstructed image
applies them in order. Silently dropping the duplicate produces a different
and incomplete image.

The 68k updater **selects these resources by radio family**. Its hardware chip-ID check
at applet `0x102` masks the high byte: `a500` selects the `02.00` data at
`0xccf2`; `8500` at `0x1c6` selects `01.30` at `0x17f2`.
[neo-updater-selection.txt](README.md#reproduction-and-verification) preserves the exact
disassembly, including PC-relative target arithmetic. The labels are resource
names; this does not mean a connected Neo currently runs either version.

Both decoded images contain 8051 code and `SDTP/1.0`/`SATURN` strings:

- `01.30` accesses radio registers in XDATA `0xdfxx`. At physical flash
  `0x22c4`, bytes `90 df 03 e0 d2 e4 f0` read `0xdf03`, set ACC bit 4 and
  write it back. Other nearby instructions access the PAN/address registers
  at `0xdf4b`–`0xdf4e`. This matches the **CC2430** integrated radio map, with
  its enhanced 8051 CPU. See [TI's CC2430 datasheet](https://www.ti.com/lit/ds/symlink/cc2430.pdf).
- `02.00` uses the **CC253x-family** radio register map: `0x6193` FSMSTAT1,
  `0x61a3` RFIRQM0, `0x61a4` RFIRQM1. For example physical `0x69a` starts
  `90 61 93 e0 a2 e6`, reading FSMSTAT1 and testing bit 6; `0x6a7` accesses
  RFIRQM0. See [TI's CC253x/4x user guide](https://www.ti.com/lit/ug/swru191f/swru191f.pdf).

The evidence supports two hardware-specific Neo radio firmware branches; exact
installed chips/revisions still need a board or device-ID check. These are
**physical flash** images: banked 8051 CODE mappings must be modeled before
following upper-bank calls in a disassembler. Do not import the whole 128 KiB
as one flat 8051 execution address space.

`SDTP/1.0` appears at physical `0x4a38` in `01.30` and `0x81a5` in `02.00`.
Thus service-protocol code/data is present in the radio firmware too. Existing
[Neo ROM research](../syscalls/wireless/README.md) describes the 68k-to-module
SPI API, not this co-processor's MAC or radio payload format. The component
boundary is now clearer, but which XML/compact-markup transformations happen
in each component still needs call tracing.

## What this establishes for a replacement

The recovered receiver uses the standard CC2420 802.15.4 radio/MAC building
blocks and normal channel frequencies. Nordic documents matching
[250 kbit/s IEEE 802.15.4 support](https://docs.nordicsemi.com/r/bundle/ps_nrf52840/page/radio.html)
in the nRF52840. **There is now a strong technical basis for using that dongle
for capture and a custom coordinator**, beyond the earlier manual-only lead.

Still required before recommending it as a working replacement:

1. Capture the existing receiver's beacons, association exchanges and known
   file transfers; confirm Nordic reception/CRC and the exact frame fields.
2. Finish tracing USB message IDs to coordinator/network commands and data
   indications, pairing those with the two Neo module implementations.
3. Recover the higher-layer datagram fragmentation, acknowledgements, retries,
   network-name/device identity fields, and security/authentication behavior.
4. Implement minimal coordinator firmware; demonstrate discovery, association
   and transfers with the original receiver disconnected.

No evidence here warrants a plug-and-play Zigbee claim, a mesh claim, or a claim
that copying the ARM receiver firmware onto Nordic would work.

## Reproduction and checks

From the workspace root:

```sh
python3 betawise/research/wireless-server/decode-receiver.py
python3 betawise/research/wireless-server/decode-neo-modules.py
```

Default outputs are under the private
`Ghidra/NEOManager3_9_3USPC-extracted/receiver-analysis/` directory. Both decoders
verify their inventoried source SHA-256 before writing new artifacts. Use
`--out /tmp/receiver-repro` for a disposable alternate output directory.

For local Ghidra analysis (substitute your installed `analyzeHeadless` path):

```sh
mkdir -p /tmp/receiver-ghidra
/opt/ghidra/support/analyzeHeadless /tmp/receiver-ghidra receiver -import Ghidra/NEOManager3_9_3USPC-extracted/receiver-analysis/receiver.bin -processor ARM:LE:32:v4t -loader BinaryLoader -loader-baseAddr 104000 -analysisTimeoutPerFile 90 -scriptPath betawise/research/wireless-server -postScript DumpReceiver.java Ghidra/NEOManager3_9_3USPC-extracted/receiver-analysis
```

Ghidra 10.0.3 recovered/exported 203 functions; this is partial analysis, not
complete code coverage. [firmware-validation.json](firmware-validation.json)
records fourteen passing deterministic checks: independent receiver payload
comparison, checksum/page count, rejection of altered payload/map/base and a
truncated map, both module record counts/hashes, every final module page against
its source record, rejection of bad resource size metadata, reviewed literal
values, and the channel-frequency equation. No emulator or hardware acceptance
test was run; this change adds static research tools and evidence only.
