# Neo radio update path, MAC access and Zigbee feasibility

**Finding:** the Neo has on-board access to its radio MCU's hardware debugger.
Its vendor updater programs the radio directly from a SmartApplet. Replacement
radio firmware is therefore a credible path, independent of the Renaissance
Receiver or Windows software. Both recovered radio images contain MAC header
construction with short/extended addresses. The reviewed stock SPI dispatcher
does **not expose a general raw MAC-frame send/receive command**.

This is static analysis plus bounded local instruction checks. No physical Neo
was queried, reset, halted or flashed. In particular, recovery and preservation
of a particular device's identifiers/calibration have not been demonstrated.

## Inputs and evidence

- [Receiver/module extraction](receiver-firmware.md), with original and decoded
  SHA-256 values. The decoded physical images are unchanged.
- [neo-updater-debug.txt](README.md#reproduction-and-verification): 68k disassembly of the vendor
  updater's debug, memory, programming and verification routines. Addresses
  are offsets in the original Wireless Updater applet, not Neo ROM addresses.
- [neo-radio-instructions.txt](README.md#reproduction-and-verification): selected 8051
  instructions, SPI dispatchers and MAC construction routines.
- [check-neo-radio.py](check-neo-radio.py) and
  [neo-radio-validation.json](neo-radio-validation.json): eight bounded
  instruction executions plus source-byte dispatch/veneer checks.
- Full local generated listings, decompilation, CODE views and logs are under
  `Ghidra/NEOManager3_9_3USPC-extracted/receiver-analysis/neo-module-analysis/`.

## The updater is a hardware debugger/programmer

The significant 68k routines are:

| Applet offset | Operation established by instructions |
|---:|---|
| `0x3b6` | Shift a byte out, MSB first, by toggling GPIO |
| `0x420` | Shift a byte in, MSB first |
| `0x48c` | Additional read/ready handling used by the newer-chip path |
| `0x500` | Configure GPIO, drive reset/debug-entry sequence with clock pulses |
| `0x5d6` | Release/reset GPIO configuration |
| `0x62c` | Send debug command `0x14` (CHIP_ERASE encoding), poll completion |
| `0x69a`, `0x6da`, `0x708` | WRITE_CONFIG, READ_CONFIG, READ_STATUS encodings |
| `0x736` | Send `0x68` GET_CHIP_ID; receive two bytes |
| `0x7ca` | DEBUG_INSTR: send `0x54 OR instruction_length`, then 1–3 instruction bytes; read accumulator result |
| `0x82a` | Read XDATA by injecting MOV DPTR, MOVX A,@DPTR and INC DPTR |
| `0x8ea` | Read flash by selecting a bank and injecting MOVC A,@A+DPTR |
| `0x9c8` | Write XDATA by injecting MOV DPTR, MOV A,#byte, MOVX @DPTR,A and INC DPTR |
| `0xb24` | Inject a three-byte LJMP instruction |
| `0xbae` | Newer-chip programming sequence |
| `0xeb4` | Newer-chip page verification sequence |
| `0x109a` | Software CRC: MSB-first polynomial `0x8005`, initial `0xffff` |
| `0x12b8` | Older-chip programming/verification sequence |

The host MMIO locations include `0xfffff420/421/423` and
`0xfffff448/449/44b`. The clock toggles bit 2 at `0xfffff421`; bit 1 is the
bidirectional data line controlled using `0xfffff420`. Reset/debug entry also
uses bit 3 through the second GPIO group. Register addresses/bit operations are
verified; physical PCB pin numbers are not assigned here.

The injected instructions are actual 8051 opcodes. Examples: `90 HH LL` sets
DPTR, `e0` reads XDATA, `74 VV f0` writes XDATA, `e4 93` reads CODE, `a3`
increments DPTR, and `02 HH LL` jumps. This matches the manufacturer's
[hardware-debug interface](https://www.ti.com/lit/ug/swru191f/swru191f.pdf),
not an application-level firmware-download protocol.

The updater selects resources using **hardware chip ID**, correcting the
earlier interpretation of this as a version check:

- GET_CHIP_ID high byte `0xa5`: use resource `02.00`, programming at `0xbae`.
  TI identifies `0xa5` as **CC2530**.
- GET_CHIP_ID high byte `0x85`: use resource `01.30`, programming at `0x12b8`;
  that image uses the CC2430 register map.

This identifies supported hardware branches, not which branch a particular
user's Neo contains. Source evidence is the `0xfc -> 0x736` call, masks at
`0x102`/`0x1c6`, resource pointers, and the matching radio-register code.

### What programming actually entails

The newer path invokes CHIP_ERASE, stages data and helper code in RAM, then
programs **64 pages of 2048 bytes**. Each page buffer starts filled with `ff`;
19-byte source records overlay their 16-byte contents at the recorded physical
addresses. The source image therefore describes a 128-KiB programming span.
That span is **not proof of the MCU's total flash capacity**.

The newer path uses XDATA flash-controller addresses `0x6270`–`0x6272` and DMA
registers around `0x70d2`–`0x70d7`. The older path uses the corresponding
CC2430 `0xdfxx` registers and a RAM routine. The updater can inject code without
requiring the existing radio application to be functional. It contains no
signature-verification gate in the reviewed direct-programming path.

However, CHIP_ERASE is a real full-chip operation. Debug lock bits, power loss,
restoring radio settings/identity, ROM background-radio activity, and recovery
on both hardware versions still need deliberate validation before a user-facing
flasher. **An official update routine is evidence of capability, not proof of
safe recovery for arbitrary replacement firmware.** A read-only chip-ID/flash
capacity/full-backup tool should precede writing anything.

## Disassembly and compiler handling

The images are enhanced 8051 code. A 64-KiB CODE view maps physical flash
`0x0000`–`0xffff` with the upper window selecting flash bank 1; this matches the
documented reset mapping for these chips. The populated executable regions
observed here are below `0x10000`; metadata at `0x1fff0` is not imported as code.

[PrepareNeoModule.java](PrepareNeoModule.java) seeds reset/interrupt vectors,
startup initializers and recognizable compiler far-call targets.
`01.30` calls through a computed DPTR/bank helper at `0x0086`; `02.00` has
six-byte veneers consisting of `LCALL 0x0e49`, a little-endian target word and
a bank byte. The newer helper consumes those inline bytes and changes the
return target; an ordinary disassembler otherwise treats them as instructions.
There are also inline switch tables, including one at `0x98a5`.

The script seeds only reviewed bank-0/bank-1 target forms. Its no-return
normalization is an analysis aid, not a claim about every function's behavior.
Generic 8051 SFR names in Ghidra are often wrong for these TI chips, and inferred
parameter prototypes are not certified. Full snapshots contain 205/558 exported
functions after call-target recovery, but that is **not complete code coverage**.
Assertions below are based on instruction bytes, explicit paths and bounded
execution, not inferred C types or apparent decompiler switches.

## MAC capability versus the stock SPI interface

By “MAC packets” this investigation means 802.15.4 frames with selectable MAC
address fields, not merely reading the radio's device address.

Both firmware images contain a conventional MAC header builder:

| Image | CODE entry | Observed fields |
|---|---:|---|
| `01.30` | `0x3c45` | Frame type, security flag, ACK-request flag, PAN compression, sequence counters, PAN IDs, short and extended addresses |
| `02.00` | `0x78dc` | Corresponding fields, including destination modes `0x08`/`0x0c` and source modes `0x80`/`0xc0` in the high FCF byte |

The newer firmware's FIFO writer at `0x1142` copies bytes to the radio's `RFD`
SFR `0xd9`; radio state-machine code issues RFST commands through `0xe1`.
Thus the radio MCU can construct and transmit addressed frames. This does not
mean a SmartApplet can submit that header through the stock API.

### Newer image: SPI dispatcher at `0x9843`

The routine reads the command word from packet offsets 4–5, ignores packets
with the command high bit set, and dispatches masked high-byte groups through
the inline 16-bit switch at `0x98a5`. Groups `0x0000`, `0x0200`, `0x0300` and
`0x0800` have active handlers; the other listed groups have no operation here.
Known paths include:

| SPI command | Call/target | Established behavior |
|---|---|---|
| `0x0006`/`0x0007` | Existing identification/configuration paths | Consistent with Neo ROM synchronization research |
| `0x0200`/`0x0201`/`0x0202` | Network-management handlers | Includes the ROM's selected-network operation |
| `0x0300` | `0x1827 -> 0x1eac` | Existing service/data-processing path |
| `0x0802` | `0x1845 -> 0x1867` | Higher-level upload/transfer path |
| `0x0803` | `0x1839 -> 0x19c1` | Higher-level receive/transfer path |
| `0x0800` | `0x1767 -> 0x2dcc` | Diagnostic byte write using a 16-bit XDATA address |
| `0x0801` | `0x1761 -> 0x2e42` | Diagnostic byte read using a 16-bit XDATA address |

The diagnostic address comes from packet offsets **6 high, 7 low**; writes take
their value from offset **8**. The actual MOVX bodies were executed locally
against artificial XDATA memory at `0x6249`, `0x6193`, `0x12ff` and `0x1300`,
with multiple values, checking the destination and unchanged unrelated memory.

**Read-reply caveat:** the `0x0801` handler stores the loaded byte at output
offset 6, then calls header builder `0x1e50`, which also writes output offset 6
from a stack-supplied field. This is an apparent result-clobber issue that must
be resolved before using the command as a read-only diagnostic API. The tests
verify the MOVX bodies only, not a complete reply or SPI transaction. Merely
finding a read handler is insufficient to promise working register readback.

No general MAC-frame transmit/receive, promiscuous-capture, or arbitrary-peer
MAC request interface was found in this reviewed dispatcher. Registers can be
addressed by the diagnostic write routine, but racing the stock MAC scheduler
through byte pokes is not an established reliable raw-radio API.

### Older image: dispatcher around `0xc48c`

The same command groups appear in the switch at `0xc4bf`. Group 8 branches to
`0xc5fb`, where `0x0800`/`0x0801` perform diagnostic writes/reads. Unlike the
newer image, instructions at `0xc63f`/`0xc654` set DPTR high to **zero**; the
access is confined to `0x00xx`, not a full arbitrary 16-bit register address.
Its response path and memory-mapping implications are not certified here.
Do not apply the newer diagnostic command behavior to an older Neo.

## Is Zigbee the right target?

### Stock-firmware experiment before replacement

The first experiment should retain the radio firmware. The Neo already exposes
association and binary transfer services; Windows document conversion and Google
Docs integration are application layers, not requirements of the Neo ROM packet
API. This does not establish that the radio's over-air transport is transparent.

The maintained [wireless ROM probe](../syscalls/wireless/README.md) now passes
54 cases. Four new cases send and receive 256- and 2048-byte payloads cycling
through every byte value, checking every byte, lengths, the send checksum and
the receive buffer boundary. These execute original 68k ROM code with synthetic
SPI samples in MAME and disposable state. They demonstrate binary transparency
at the **Neo-to-module API boundary**, not over-air delivery. Local run artifacts
are `/tmp/neo-stock-radio-binary-probe/` (temporary, not required source inputs).

Current capability boundaries:

| Operation without radio reflash | Evidence / remaining work |
|---|---|
| Call stock association and file-transfer services from a custom applet | ROM interfaces and controlled tests established; real network completion still needs hardware |
| Supply binary application data rather than XML | Original ROM packet send/receive tested with all byte values; module/service acceptance still needs tracing |
| Replace Windows document conversion | Independent application work; not needed to investigate association and binary transport |
| Use a replacement USB radio as coordinator/receiver | Requires reproducing the stock on-air association, framing and transfer behavior; not demonstrated |
| Send arbitrary raw MAC frames or join ordinary Zigbee | No general stock SPI command found for either operation |
| Read arbitrary radio registers using stock diagnostics | Newer read-reply caveat above remains unresolved; not a ready hardware probe |

Next, follow `0802 -> 1867 -> 4fdb`, `0803 -> 19c1 -> 50db` and
`0300 -> 1eac -> 5b16` in image 02.00 through their queues into MAC transmission.
Recover the over-air service envelope, fragmentation, acknowledgement/retry
state and destination selection. Compare those fields with receiver firmware,
then implement the smallest stock-compatible exchange on the Nordic dongle.
The first hardware acceptance criterion is one known binary block from Neo to
computer and a different block back, verified byte-for-byte. The existing hub
can supply a baseline for captures without becoming an end-user dependency.

This path requires understanding the stock radio protocol, but not recreating
Google Docs integration or the Windows conversion pipeline. Kermit should be
considered after establishing a reliable bidirectional byte/block transport;
no transparent serial tunnel has yet been demonstrated.

**Zigbee is a reasonable preferred target if we can fit and integrate a stack
on the supported Neo variants.** It standardizes network formation/joining,
addressing, security and application endpoints. We would still define the file
transfer application messages and computer-side support; a generic lighting
hub would not automatically understand Neo documents.

The material feasibility distinction is:

- CC2430 has at most 128 KiB flash and 8 KiB RAM. It supported historical Zigbee
  stacks, but that does not establish support for a modern Zigbee stack here.
- CC2530 supports larger flash options. TI explicitly recommends the **F256**
  for Zigbee because its Z-Stack generally needs more than 128 KiB. Its
  [Z-Stack 3.0.2](https://www.ti.com/tool/Z-STACK) supports CC2530/CC2538;
  CC2430 should not be assumed to use the same modern stack release.

The key next measurement is chip ID and **actual flash capacity**, through the
hardware debugger. On CC2530, CHIPINFO0 at XDATA `0x6276` encodes flash size in
bits 6–4 (3 = 128 KiB, 4 = 256 KiB). The byte can be read using injected
instructions without erasing flash. No such hardware read has been performed.
See the [TI CC253x guide](https://www.ti.com/lit/ug/swru191f/swru191f.pdf).

A viable implementation could put Zigbee on the radio MCU and expose an SPI
application interface to Neo applets. If radio flash/RAM prevents that across
all variants, another architecture is a small radio MAC coprocessor plus more
of the stack on the Neo's 68k CPU; that is an unimplemented alternative with
its own portability/memory work, not a proven fallback.

Preferred sequence: read-only chip identification, capacity and backup; minimal
replacement/RAM-resident radio experiment with deterministic checks; stack-size
and SPI integration proof; then Zigbee joining and file-transfer development.
Legacy XML, Windows server and receiver USB compatibility are not requirements.

## Reproduction

```sh
python3 betawise/research/wireless-server/decode-neo-modules.py
python3 betawise/research/wireless-server/check-neo-radio.py
```

For Ghidra, construct a CODE view from the first 65536 bytes of a decoded image
and import with `8051:BE:16:default`, base 0. Run `PrepareNeoModule.java` before
analysis and `DumpReceiver.java` afterward (the exporter name is historical).
`InspectNeoModule.java output.txt start:end ...` provides bounded linear views
for manual paths. Inline tables must be decoded as data; the listing explicitly
warns that linear data interpretations are not executable evidence.

The committed checks are local and deterministic, preserve source hashes,
fail on unknown instructions, and do not invoke radio hardware or screen/model
inference. No claims of stock packet interoperability, arbitrary firmware
recovery, live debugging, or a functioning Zigbee build are made.
