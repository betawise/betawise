# NEO Manager 3.9.3 and wireless-server package inspection

Follow-up: [receiver firmware and Neo radio-module analysis](receiver-firmware.md)
decodes the receiver container, identifies its CC2420 interface, and recovers
both embedded Neo radio-module firmware resources.

[Neo radio update, MAC access and Zigbee feasibility](neo-radio.md) follows the
on-board hardware debugger, both firmware branches and the stock SPI dispatcher.

[USB command tunneling](usb-tunnel.md) identifies shared buffer-based protocol
handlers and records seven original-ROM tests without USB-controller access.

Static inspection of the privately supplied `Ghidra/NEOManager3_9_3USPC.zip`.
No installer, vendor executable, firmware update, or hardware write was run.
The archive SHA-256 is
`ca87e733af62a24e4713a1b04059fae0ea03f47754240b7da64cfec9e821d0f0`.

## Inventory

[package-inventory.json](package-inventory.json) records paths, sizes and hashes
for 62 installer/software/firmware components: 25 applets, two Neo ROM files,
eight Saturn firmware packages, and 27 Windows components. It is not an
inventory of the installer’s lessons, manuals, or other non-executable content.
Original private files remain under `Ghidra/NEOManager3_9_3USPC-extracted/`.

- Main `OS3KNeoROM.OS3KOS` is **identical to the existing Neo 3.21 image**:
  `32fe55bb50c1b58326bd303f14973b8402ddf8bf6662b210e4d5e9f931c7e6c0`.
  Its embedded build timestamp is July 11, 2013, 09:44:53. The new source is
  recorded as a copy in the [main-ROM inventory](../abi-audit/rom-inventory.json).
- `SMALLOS3KNeoROM.OS3KOS` is also identical to the existing Neo small image:
  `6402c40878ba28747642ce474361b1596555b2a1f137db79c7ea8bb5b35a9523`.
  It is cataloged as a supplemental ROM, not given a guessed syscall table.
- **Two distinct applets were added** to the hash-deduplicated
  [vendor inventory](../abi-audit/vendor-image-inventory.json): Control Panel
  (`503e2aaa9ebdb85b7a693d0c75f8e1687da6cef16411cc27d66915cbae28c3f6`)
  and Thesaurus Spanish to English
  (`7605ba816106e72c090fc830d93dc0aac4c71159627dc1a477bee1d89af080a0`).
  Different hashes establish distinct images, not newer semantic versions.
  The other 23 applets match previously inventoried images; their new paths
  are recorded as copies. Wireless applets are unchanged.
- The package includes `Renaissance Wireless Server.exe`, its Utility,
  `RPGateway.exe`, `KWGateway.exe`, and `NEO2forGoogleDocs.exe`.
- **Receiver firmware is included**: `Renaissance Receiver_0120.fud`, SHA-256
  `41c645a87467f36ee2a9ff1970d3c0beaf41fce2ee5695f6cdbc8d94ecc5a2a1`.
  Its ASCII header identifies `SATURN FIRMWARE FILE/1.0`, firmware `01.20`,
  bootloader `01.08`, source `Saturn.s37`, package date March 30, 2011,
  page size 256, address size 4, and MapPosition 115752. These are header
  claims; binary block-map interpretation and checksum validation remain undone.
  Seven Responder/2Know packages are also cataloged with their exact headers.

## Protocol evidence

[protocol-strings.json](protocol-strings.json) preserves selected strings with
original file byte offsets and encoding. The complete 98,260-string dump is
`Ghidra/NEOManager3_9_3USPC-extracted/static-strings.json`, alongside the private
inputs. String presence is static evidence, not proof of executed control flow.

| Component | Byte offset | Observation |
|---|---:|---|
| Wireless Server | `0x53db10`, `0x53dc10` | `SDTPStream`, `SDTP/1.0 `; nearby `WriteRequestHeader` and `WriteResponseHeader` |
| Wireless Server | `0x53d67c` | `SDMLReader` |
| Wireless Server | `0x53fd64` | `XMLDocReaderSDMLWriter`, a lead for XML-to-compact-markup conversion |
| Wireless Server | `0x545dd4`, `0x5461e0` | `DeviceServiceRequestTask`, `SDTPDeviceServiceHandler` |
| Wireless Server | `0x53bb30`–`0x53bba0` | `mDestAddr`, `mMSDUHandle`, `mBytesToSend`, `mDestAddrMode` |
| Wireless Server | `0x53cd78`–`0x53cdc4` | `mEncryption`, `mEncryptionKey`, `mEncryptionMethod`; not proof encryption is enabled or how keys are obtained |
| Wireless Server | `0x54cdaf`, `0x54ce07` | `SaturnUplinkComm.CreateSaturn`, `SaturnUplinkComm.Write` signatures |
| Wireless Server | `0x80b133`–`0x80b19f` | Windows HID APIs including `HidD_GetAttributes` and `HidP_GetCaps`; supports tracing the receiver USB HID transport |
| Wireless File Transfer | `0xbd52` | `SDTP/1.0` |
| Wireless File Transfer | `0xbf0a`, `0xc17a`, `0xc278` | Brace markup beginning `{auth`, `{nf`, `{ua` |
| Wireless File Transfer | `0xc3b6`–`0xc3d0` | `/auth`, `/setua`, `/receivefile`, `/sendfile`; `cl:%u` at `0xc3e7` |
| Accelerated Reader | `0x14a52` | XML template `<SRQ aid="RP"><OLM v="2" op="lg">...` |
| MathFacts RP | `0x13dea` | XML template `<SRQ aid="MF"><MRT v="2" op="ptd">...` |
| Receiver firmware | `0x9829`, `0x9b59`, `0x9cb7` | `PAN Name: 32 letters max`, `BeaconNotifyIndication() Fifo Full`, `MACTimer0 Interrupt Priority High Water Mark` |

This supports an application architecture with SDTP service messages, XML and
compact markup, plus a separate receiver transport. It strengthens the user's
XML hypothesis while showing that Wireless File Transfer is not simply a set
of printable XML templates. Actual conversion paths must be disassembled.
See the existing [restricted markup parser](../syscalls/markup/README.md) and
[Neo wireless APIs](../syscalls/wireless/README.md). In particular, the Neo's
`A5`/checksum framing is processor-to-radio-module SPI framing; it must not be
silently equated with either SDTP or over-the-air MAC frames.

These files do **not yet verify an nRF52840 replacement**. Priority next steps:
trace the server's USB HID report construction and parsing; decode the receiver
firmware container and identify its processor/radio implementation; trace SDTP
header construction and compact-markup conversion; then correlate with controlled
USB and RF captures of discovery, association and known file transfers. MAC
format, timing, security and proprietary radio behavior remain open. No Zigbee
stack, mesh topology, chipset identity, or packet-level interoperability is
established by this inspection.

## Reproduction and verification

From the workspace root (requires local `unzip` and `msiextract`):

```sh
unzip -q Ghidra/NEOManager3_9_3USPC.zip -d Ghidra/NEOManager3_9_3USPC-extracted
msiextract -C Ghidra/NEOManager3_9_3USPC-extracted/payload 'Ghidra/NEOManager3_9_3USPC-extracted/NEOManager3_9_3USPC/NEO Manager.msi'
python3 betawise/research/wireless-server/inventory.py --update
python3 betawise/research/syscalls/wireless/find-vendor-calls.py
```

The inventory script validates applet magic and declared package size, hashes
components, and deduplicates applets by hash. It preserves existing ROM targets
and test selection. The expanded wireless caller scan passes hash checks and
reports **16 images with validated syscall blocks and 676 reference candidates**;
the former 14-image/673-reference results remain historical observations.
This is a static caller inventory, not live wireless or full ROM acceptance.
