# AlphaSmart device-side USB protocol

For applet callbacks, raw endpoint payloads and the feasibility of a different
USB device class, start with [Native applet USB messages](native-usb.md). That
follow-up documents both `300xx` keyboard and `400xx` binary USB workflows,
updates the SDK declarations and adds a native dispatcher probe.

This investigation separates **keyboard Send**, **direct Manager/updater file
transfer**, and **internal applet messages**. They share firmware services but
are different interfaces. In particular, an updater opcode is not an applet
message or an A-line syscall.

Evidence collected 2026-11-21: fresh static disassembly/decompilation of the
local Neo 3.21 ROM and AlphaWord Plus 3.04; checksum-verified historical USB
captures; and the implementation in ioma8/neo-re. No physical device was accessed,
no saved session was changed, and no end-to-end USB or screen acceptance test
was run. Static anchors and capture checks are reproducible below. Existing
[editor/form API tests](../syscalls/text/README.md) establish narrower runtime
contracts, not cable interoperability.

## Sources and version boundaries

The two requested upstream URLs currently resolve to the same commit,
[`5524a6bbcf3d5a1e0ae86facb5cdc239adc64344`](https://github.com/ioma8/neo-re/tree/5524a6bbcf3d5a1e0ae86facb5cdc239adc64344).
The checkout used here is at workspace path `.research-work/neo-re-usb`.
Useful pinned sources:

- [protocol.rs](https://github.com/ioma8/neo-re/blob/5524a6bbcf3d5a1e0ae86facb5cdc239adc64344/alpha-core/src/protocol.rs): packets, checksums, header parsers.
- [neo_client.rs](https://github.com/ioma8/neo-re/blob/5524a6bbcf3d5a1e0ae86facb5cdc239adc64344/alpha-core/src/neo_client.rs): file/app download and updater sequences.
- [usb_android.rs](https://github.com/ioma8/neo-re/blob/5524a6bbcf3d5a1e0ae86facb5cdc239adc64344/alpha-core/src/usb_android.rs) and [JNI bridge](https://github.com/ioma8/neo-re/blob/5524a6bbcf3d5a1e0ae86facb5cdc239adc64344/alpha-core/src/usb_android/jni_bridge.rs): Android USB permission, enumeration, control and bulk transfers.
- [AlphaUsb.c](https://github.com/ioma8/neo-re/blob/5524a6bbcf3d5a1e0ae86facb5cdc239adc64344/smartapplets/alpha_usb_bw/AlphaUsb.c): device-side mode switch.
- [backup.rs](https://github.com/ioma8/neo-re/blob/5524a6bbcf3d5a1e0ae86facb5cdc239adc64344/alpha-core/src/backup.rs): text export policy.
- [upstream transport notes](https://github.com/ioma8/neo-re/blob/5524a6bbcf3d5a1e0ae86facb5cdc239adc64344/docs/2026-03-31-direct-usb-driver-notes.md): upstream physical-device observations, distinct from our static checks.

Local reference sources are `neotools/neotools/{device,message,file}.py` and
`neotools/usb_pcap/*.pcapng`. All paths in this paragraph start at workspace root.

| Local image | Size | SHA-256 |
|---|---:|---|
| `Ghidra/Alphasmart Neo/SmartApplets/os3kneorom.os3kos` | 395264 | `32fe55bb50c1b58326bd303f14973b8402ddf8bf6662b210e4d5e9f931c7e6c0` |
| `Ghidra/Alphasmart Neo/SmartApplets/alphawordplus.os3kapp` | 106684 | `a8ae516734a0e0b2e19d51ffb7dff3893074ca733fa40207cbff7ead1433f29e` |

Neo ROM addresses below use `runtime = file offset + 0x410000`. AlphaWord
addresses are file-relative offsets, before installation relocation. These
absolute ROM helpers must not be assumed compatible with Neo 3.01, AS3000,
Small ROM, or other language/firmware versions.

## Modes and entry

Normal Neo USB keyboard identity is VID:PID `081e:bd04`. The direct identity
used by the upstream client is `081e:bd01`. Upstream reports interface 0, bulk
OUT `01`, bulk IN `82`; its desktop client discovers the bulk endpoint pair.
USB packet size, host transfer size, eight-byte protocol header size, and
logical file chunk size are separate quantities. Historical captures show
payloads arriving in eight-byte fragments.

Upstream's host-side switch sends five HID `SET_REPORT` requests, each with one
byte: `e0`, `e1`, `e2`, `e3`, `e4`. Setup fields are `bmRequestType=21`,
`bRequest=09`, `wValue=0200`, `wIndex=0`. That is an output report, ID zero.
The device re-enumerates; the host must reopen the direct identity. Android's
ability to open the initial keyboard interface depends on platform permission
and device exposure; the JNI code explicitly distinguishes a keyboard visible
through InputDevice but inaccessible through UsbManager.

`AlphaUsb.c` provides a device-side route: on `30001` (USB attach), it invokes a
**ROM-specific sequence**, then writes reply `11` (hex). It does not implement
backup packets or its own file service. The fresh local ROM trace corroborates:

| Operation in AlphaUsb.c | Local Neo 3.21 evidence |
|---|---|
| `41f9a0(1,0,0)` | Endpoint/controller write wrapper. Selects controller backend using RAM byte `041a`; the alternate backend maps endpoint selectors before writing. This call supplies a zero-length endpoint-1 transaction. |
| `424780(100)` twice | Public slot 53, `A0D4`, **SleepCentiseconds**: each call is approximately one second, not 100 ms. |
| write byte `1` at `013cf9` | USB mode/state global also consulted by the native USB loop. Full bit semantics remain incomplete. |
| `44044e()` / `44047c()` | Reset shared USB status words at `013d02/013d04` under interrupt exclusion; invoke controller disable/enable wrappers. |
| `410b26()` | Installs direct callback `410b60`, sets status byte `0444=5`, initializes updater globals, renders status and passes through its incoming callback arguments. |

Only the delay is a public syscall among these hardcoded helper addresses.
`410b26` has two incoming byte arguments in the native callback path. AlphaUsb
calls it without establishing those arguments; native control flow is verified,
but a portable zero-argument API contract is **not** established. Likewise,
inline assembly's register clobbers deserve ABI review before reuse. Keep this
sequence as reverse-engineering evidence rather than copying it into an SDK API.
The applet's focus loop pumps events with `A25C` (slot 151,
`SystemHandleEvents`).

Small ROM can expose the same direct PID, but is a different command environment.
Upstream reports `13` returning `92` there. PID alone does not establish that
normal AlphaWord backup services are available.

## Direct transport bootstrap and framing

After entering direct mode, select the System/updater applet, ID zero:

```text
host -> 3f ff 00 72 65 73 65 74       ? FF 00 reset
host -> 3f 53 77 74 63 68 00 00       ?Swtch + applet ID, big-endian
Neo  -> 53 77 69 74 63 68 65 64       Switched
```

`NoSwitch` and `NoApplet` are negative textual replies recognized by upstream.
These bootstrap strings do not use the numeric header checksum.

Numeric request and response headers are eight bytes:

| Offset | Bytes | Meaning |
|---:|---:|---|
| 0 | 1 | Request opcode or response status |
| 1 | 4 | Unsigned big-endian argument; operation-specific packing |
| 5 | 2 | Unsigned big-endian argument/checksum/applet ID |
| 7 | 1 | Sum of bytes 0–6 modulo 256 |

Payload checksum is the sum of payload bytes modulo 65536, carried in bytes
5–6 of its associated header. Neither checksum is a CRC.

Local ROM anchors: `412bca` decodes and checks a header; `412c28` builds a reply
and remembers its status in byte `0446`; `410b60` accumulates eight incoming
bytes before calling dispatcher `410c82`. Its partial-header timeout compares
elapsed firmware clock ticks against `0x1e`; do not infer a universal host
transaction timeout from this check.

## File messages implemented by the device

The Neo ROM's `410c82` dispatcher handles these commands, selecting an installed
applet by header ID from the final 16-bit field when required. AlphaWord's ID
is `a000`. This path accesses ROM file services directly; it does not ask the
foreground AlphaWord UI to serialize each downloaded chunk.

Numbers below are hexadecimal. `L` is a 24-bit requested length and `i` an
8-bit selector. **Read and write argument layouts differ.**

| Request | Argument bytes 1–4 / final word | Successful response and following data |
|---|---|---|
| `13` attributes | `00 00 00 i` / applet ID | `5a`, argument `28`, sum16; then 40 attribute bytes |
| `12` normal file read | `(L << 8) \| i` / applet ID | `53`, source length; repeated `10` requests retrieve data |
| `1c` raw file read | `(L << 8) \| i` / applet ID | `53`; same chunk protocol, raw stored bytes |
| `10` next chunk | zero / zero | `4d`, byte count, sum16; then exactly that many bytes. `4e` is zero-byte/end response. Invalid raw-transfer state can return `80`. |
| `14` normal file write | `(i << 24) \| L` / applet ID | `50`; then block-write handshakes and `15` |
| `1f` raw file write | `(i << 24) \| L` / applet ID | `50`; same block protocol |
| `02` write block | byte count / payload sum16 | `42` ready; host sends bytes; Neo automatically returns `43` on matching sum, `8e` on mismatch |
| `15` finish file write | zero / zero | `51`; updates file length and closes/refreshes file state |
| `1d` stage attributes | file index / applet ID | `5b`; upload the 40-byte record through `02` |
| `1e` apply attributes | file index / applet ID | `5c`; applies staged attributes, potentially creating a record |
| `1b` usage | zero or nonzero / applet ID | `59`; zero queries total with reservations (`FileQuerySize(fe)`), nonzero logical total (`fd`); final word is file count |
| `1a` free space | zero / zero | `58`; flash bytes and RAM in 256-byte units |
| `08` restart | zero / zero | `52`; direct callback then enters startup, not ordinary applet resume |

File/content paths guard firmware file initialization state (`35f4 == 2675`);
not-ready paths can return `85`. Unknown applet ID returns `8a`, malformed header
or unsupported opcode `8f`, file/parameter errors `90`, insufficient space `91`.
Do not interpret all `90` responses as an empty File-key slot; they are an error
class. The ROM can put a negative native error in the argument, although some
paths discard that detail. Header validity and success status must both be checked.

The block-write receiver is `412b20`, entered through callback `410c20` after
`02`. It consumes the announced byte count, checks sum16 and generates `43` or
`8e` itself. **There is no extra `ff` wire command between block data and `43`.**
Upstream host reverse-engineering notes call `ff` a completion probe; the local
firmware and historical write capture establish the actual wire exchange.

The direct callback gives the dispatcher an output capacity of `400` bytes.
For `10`, that includes the eight-byte response header: this path emits at most
`3f8` (1016) payload bytes per response, not a guaranteed 1024. The upstream
write clients use blocks of at most `400` bytes. Always honor response counts
and assemble short USB reads rather than assuming packet boundaries.

A further read-length caveat: `53` reports the source length, while the dispatcher
limits the transfer to `min(source_length, requested_L)`. Requesting less than the
source can therefore make a client that waits for the entire `53` count stall or
hit `4e`. The Android client requests `80000` bytes and uses `53` as its target;
it does not robustly handle early `4e`, zero-progress or oversize chunks.

## File indexes, File keys, profiles, and plain/raw content

These selectors are distinct:

- `13` resolves an indexed file through `43b6f0` (`FileResolveId`), incorporating
  the current user/profile context from `438c44`.
- For applets whose header flag byte at `+13` contains `40`, normal `12` accepts
  File-key bindings 1–8 and resolves their tags through `43b660` (`FileFindByTag`).
  Other applets use index resolution. Neo AlphaWord's shipped header has this bit.
- Raw `1c` bypasses that binding branch and uses indexed resolution.
- Normal `14` similarly maps a File-key selector for flagged applets; raw `1f`
  uses indexed file selection. Bit 31 of the write argument suppresses the
  initial truncation, supporting an append/preserve-length path; its selector
  is masked with `7f`. Not all combinations were executed here.

The binding tag table at ROM `4495f9` is:

| File key | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Tag | `2d` | `2c` | `04` | `0f` | `0e` | `0a` | `01` | `27` |

The literal leading table byte is `00`; neotools uses `ff` for an unbound file.
Do not substitute the table's unused index zero for an observed unbound tag.
Named/unbound files and multiple profiles make an eight-index backup incomplete.
The [multi-user investigation](../multi-user/README.md) covers the profile API.

Normal `12` checks file flag `04`. For such text files it initializes a native
editor/scan context through private helper `429cf0` and emits converted text
through public `TextScanRead` at `4291be`. Raw `1c` uses the stored buffer and
logical length, preserving gap/format tokens. See [text scanning](../syscalls/text/README.md)
and [file services](../syscalls/file/README.md) before implementing a raw restore.
A plain-text export is not a lossless raw backup.

The Android shared client loops indexes 1–8 for attributes but issues **normal**
`12` for content using the same integer. This can pair attributes with the wrong
file. Its attribute parser reads up to 24 bytes as a filename, crossing into the
password field if a malformed/nonterminated name is present. Its `backup.rs`
only changes NUL to space and CR to LF; it does not establish Unicode decoding
or a lossless AlphaWord serialization. A complete backup should preserve raw
attributes and indexed raw content, identify profile and bindings separately,
and validate all lengths/checksums. That is a proposed client design, not a
newly tested implementation.

## The 40-byte file attribute record

Fresh ROM helpers `43c5ee` (export) and `43c660` (apply) connect the wire record
to the 72-byte RAM `FileInfo_t` already declared in
[`os3k_file.h`](../../os3k/os3k_file.h). These are different layouts.

| Wire offset | Size | Meaning / RAM source |
|---:|---:|---|
| `00` | 16 | NUL-terminated name; RAM record `+34` |
| `10` | 7 | Password bytes including terminator; RAM `+18` |
| `17` | 1 | Not initialized by the string copies; preserve as opaque |
| `18` | 4 | Minimum/reserved length; RAM `+10` |
| `1c` | 4 | **Logical file length**, RAM `+04`; not allocated capacity at `+0c` |
| `20` | 4 | File flags; RAM `+20` |
| `24` | 2 | File tag, RAM `+46`; File-key code is commonly its low byte at `25` |
| `26` | 2 | Not written by export helper; opaque/uninitialized tail |

String-copy routines stop at NUL, so padding after names/passwords is not
necessarily zero. neotools's `alloc_size` name and upstream's `attribute_bytes`
are host labels; the device instructions establish the field's source.
Attributes export does not return allocation capacity. Flags `02` and `04`
relate to current-file selection and native text handling respectively; there
is no evidence here that other bits can be freely discarded.

## AlphaWord's native Send callback contract

Neo AlphaWord entry `94` initializes its shared transfer object lazily, at
`A5+ba`, and handles transport messages through these real syscall stubs:

| Call site in Neo AlphaWord | Stub | Opcode / slot | Neo 3.21 target |
|---|---|---|---|
| `1fc` | `12ee4` | `A2E4` / 185, TextEditorTransferInit | `428598` |
| `258` | `12ee6` | `A2E8` / 186, TextEditorTransferHandleMessage | `4285ce` |
| `1e2` | `12eee` | `A2F8` / 190, TextFormTransferInit | `42f6a8` |
| `232` | `12ef0` | `A2FC` / 191, TextFormTransferHandleMessage | `42f744` |

It selects the form handler only for form mode and prefix `60000`; USB uses the
editor transfer handler. Its source editor is `A5+12`, form is `A5+70`, shared
transfer phase is `A5+bc`, and byte `A5+138` guards initialization. This is the
shipped Neo AlphaWord layout, not a layout guarantee for custom applets.

The transport callback parameter is a device-RAM record, **not a USB packet**.
Native USB loop stores and AlphaWord consumers establish this 20-byte view:

```c
/* Research view, 68000 big-endian, word-aligned 32-bit fields. */
struct NativeTransferRequest {
    uint32_t input_length;       /* +00 */
    uint32_t input_address;      /* +04: e.g. pointer to 16-bit native key */
    uint32_t output_capacity;    /* +08 */
    uint32_t output_length;      /* +0c: applet/handler writes this */
    uint32_t output_address;     /* +10: caller-owned writable buffer */
};
```

For attach `30001`, the USB loop supplies length 1 and pointer `013cf8`, with no
output capacity. For native key-down `3001e` / key-up `3001f`, it supplies a
big-endian two-byte key word via buffer `39fa`, usually with output capacity
`400`. If keyboard output is already queued, it uses `3011e/3011f` and capacity
zero. Bit `0080` in the native key word selects the key-up message.

The editor handler dispatches by the low message byte, but some arms check the
**full** code. Its sparse table at `42861e` has these branches:

| Low byte | Device handler behavior |
|---|---|
| `01` | Reply `11`, then common reset. Full `60001` additionally copies name (max 39), enters phase 6. |
| `0b`, `13` | Clear phase and key/progress state. |
| `07`, `08` | Advance/finish active phases; phases 1/7 can request the next converted text chunk. |
| `0d` | From phase 6 initialize scan/count and enter phase 7, then continuation logic. |
| `0c` | Full `6000c` enters phase 10; other prefixes phase 4. |
| `10`, `11`, `12` | Set phase 11, 7, 3 respectively. |
| `1e` | Inspect native key: low byte `2a` (Send) from idle starts scan/transfer. Active phases also route to the chunk helper. Escape from phase 1 replies `13`, enters phase 2. |
| `1f` | In a non-idle phase, reply 1; otherwise unhandled. |
| `20` | Only full `60020`; Escape enters phase 8, replies 8. |

Helper `429f14` fills the supplied output buffer through `TextScanRead`, caps
request size to a per-transfer width between 10 and 40 bytes, and updates
`output_length` and transfer progress. In phase 1 it replies 6 while supplying
text; prefix-60000 phase 7 uses replies 4/8 as it progresses. The USB loop
consumes reply 6 by converting those text bytes into keyboard reports via
`424294`, then writing endpoint selector 3 (mapped to 5 by one controller
backend). **Send is text-to-HID keyboard output**, not the `12/10` Manager
read protocol. Native key passthrough uses the same eight-byte keyboard report
buffer. Host-layout/modifier details of the converter remain to be mapped.

The loop checks attach replies `11` and `12` to suppress its default attachment
screen (`41cbfc`, `41ce32`); these replies do **not** terminate the USB loop.
AlphaWord preserves `11`, otherwise changes low-byte-01 replies to `12`.
Detach `3000c` is emitted after loop cleanup, with reply ignored there.

The existing [`TextTransfer_t`](../../os3k/os3k_text.h) is 124 bytes: file ID at
00, phase/flags 02/03, six range cursors 04, key/progress word 1c, chunk width
1e, name[40] 20, progress 48, converted length 4c, embedded 44-byte scan at 50.
These are RAM structures; do not transmit them as wire records. The
[native USB follow-up](native-usb.md) adds reviewed message declarations;
private controller helpers remain outside the public syscall API.

## Historical capture checks

The offline auditor validates pcapng block lengths, Linux usbmon linktype 220,
selected bus/device, full captured records, numeric header checksums, announced
payload lengths and sum16. It accumulates fragmented payloads. It never opens a
USB device or uses screenshots. Raw capture sources remain in `neotools/usb_pcap`;
JSON output retains wire hex, payload hashes, checksum results and frame numbers.
It is a restricted research parser, not a general USB analyzer or transaction
state-machine validator. Use ordinary Python (assertions enabled).

`view_file.pcapng`, bus 1/device 25, passed: 65 decoded records, including two
payloads. The decisive frames are:

```text
283 OUT 12 08 00 00 01 a0 00 bb     normal File-key 1 read, limit 0x80000
286 IN  53 00 00 00 0b 00 00 5e     11-byte source
287 OUT 10 00 00 00 00 00 00 10
290 IN  4d 00 00 00 0b 03 d1 2c     11 bytes, sum16 03d1
292/294 payload: 74 65 73 74 20 66 69 6c 65 20 31
295 OUT 13 00 00 00 01 a0 00 b4     indexed attributes, index 1
298 IN  5a 00 00 00 28 09 32 bd
300–308 attributes: name "semantics", length 00001abd, tag 00ff
```

Thus indexed attributes 1 describe a different unbound file than File-key 1's
`test file 1` content. This is captured device traffic, independently supporting
the static distinction above.

`send_file3_to_device.pcapng`, bus 1/device 25, passed: 58 decoded records,
including seven payloads. Frames 1141–1168 first truncate normal binding 3 with
`14 03 00 00 00 a0 00 b7` / `50` / `15` / `51`, then write 43 bytes:

```text
1149 OUT 14 03 00 00 2b a0 00 e2
1152 IN  50 00 00 00 00 00 00 50
1153 OUT 02 00 00 00 2b 0c d9 12
1156 IN  42 00 00 00 00 00 00 42
1157 OUT 43-byte payload, sum16 0cd9
1160 IN  43 00 00 00 00 00 00 43
1161 OUT 15 00 00 00 00 00 00 15
1164 IN  51 00 00 00 00 00 00 51
1165 OUT 08 00 00 00 00 00 00 08
1168 IN  52 00 00 00 00 00 00 52
```

This same capture contains another enumeration at device 27. The strict auditor
rejects that segment's version payload checksum at frame 1532. It is not counted
as passing evidence; checksum exceptions were not invented to accept it.

## Reproduction and preserved evidence

Run from workspace root:

```sh
python3 betawise/research/usb/audit-static.py
python3 betawise/research/usb/audit-capture.py \
  neotools/usb_pcap/view_file.pcapng --bus 1 --device 25
python3 betawise/research/usb/audit-capture.py \
  neotools/usb_pcap/send_file3_to_device.pcapng --bus 1 --device 25
```

Static audit hash-gates the two images, verifies actual AlphaWord PC-relative
calls and syscall words, checks ROM dispatch entries and decodes the editor/form
sparse jump tables. It does not execute firmware. Fresh Ghidra project copies,
raw disassembly, decompilations, JSON results and hashes are retained under
workspace `.research-work/usb-protocol/`; see its `evidence/manifest.json`.
The disposable project contains no user RAM session.

For independent Ghidra reproduction, create an empty output directory and
existing writable Java home, then import the ROM with BinaryLoader at `410000`,
processor `68000:BE:32:default`, and `-noanalysis`. Run [`Dump.java`](Dump.java)
as a post-script with addresses from the tables above. Import AlphaWord at zero
and dump `94`. Use `-readOnly` for later inspection of those disposable projects.
[`reproduce-static.sh`](reproduce-static.sh) reproduces the imports and dumps
(`bash betawise/research/usb/reproduce-static.sh /tmp/neo-usb-static`).
Ghidra misses several sparse
jump-table arms; inspect the raw disassembly and decoded tables instead of
assuming its decompiled byte-only message type is correct.

Remaining work: execute controlled native callback/USB transport probes with
disposable state; map HID output-report switch recognition and text-to-keyboard
layout conversion; qualify attach/detach/cancel timing; verify write append,
malformed-size and checksum-retry behavior; test indexed raw backup/restore of
named files across profiles; separately trace AS3000 and Small ROM. Current
findings support a concrete read/write protocol map, not full hardware or
cross-firmware certification.
