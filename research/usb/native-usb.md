# Native applet USB messages and custom device support

**Custom binary traffic is supported through the stock direct-mode applet
callbacks (`400xx`). A new device class such as USB mass storage is not exposed
through those callbacks.** The `300xx` messages in the original header belong
to the keyboard workflow. Neither family gives an applet arbitrary endpoint
selection or USB control-request/descriptor ownership.

This follow-up traces the original Neo 3.21 ROM and the six shipped applets
listed below. It also executes the original direct-message dispatcher with a
compiled custom callback in disposable MAME RAM: four cases pass. That proves
the callback/queue contract, **not physical USB transfer, enumeration, full
applet switching, or mass-storage compatibility**. No screenshots are used.
The older [Manager protocol notes](README.md) describe a different layer.
The [ownership follow-up](ownership.md) traces event-loop versus interrupt
servicing and identifies a shutdown signature in both inventoried Neo main ROMs.

## What can be done in the current setup?

| Objective | Answer from the evidence |
|---|---|
| Receive and send our own binary application protocol from a SmartApplet | **Yes**, via `40002` receive and `40006` send-poll, with direct replies 4/5. The ROM moves arbitrary bytes, not just text or updater messages. AlphaQuiz and AlphaWord implement this interface. |
| Supply text/native keys for keyboard Send | **Yes**, via `3001e`, `30007`, `30008` and keyboard replies 3/6. The ROM generates the HID report. |
| Choose arbitrary endpoint addresses, transfer types or descriptors through a message | **No such facility found.** The request has buffers/counts, no endpoint or setup fields. |
| Make a stock-ROM applet enumerate as a mass-storage disk using just these callbacks | **No.** Fixed ROM descriptors and EP0 request handling remain in control. Binary bulk payload capability alone is insufficient. |
| Write a private, firmware-specific low-level USB implementation | **Plausible**, using controller MMIO/private helpers and replacing/hooking the control/interrupt path. This is new driver work, not an existing syscall contract or tested mass-storage implementation. It does not necessarily require a permanent flash patch. |
| Connect a USB flash drive to the Neo's printer/host port | A separate **USB host** problem: these PC-facing device callbacks do not expose host enumeration, SCSI or block-device APIs. No mass-storage host service was found in the inspected applets/syscall table. |
| Use the emulator as a native USB disk in the desktop OS | The current MAME PC link uses an explicit localhost DUSB packet peer; it does not automatically create a host-OS USB gadget. That would require a host integration layer too. |

Here “binary” means endpoint payload bytes. It does not mean software emits USB
tokens/PIDs/CRC or overrides USB bus scheduling; the controller handles those.

For the mass-storage device case, USB-IF's [Bulk-Only Transport specification](https://www.usb.org/sites/default/files/usbmassbulk_10.pdf)
requires a mass-storage interface, bulk IN/OUT, class reset and Get Max LUN
requests, command/status wrappers and their transfer/recovery rules. A disk
implementation also needs block-command responses and a backing sector layout.
The Neo's applet-file table is not already a FAT block device.
The [ISP1763A manufacturer documentation](https://www.st.com/en/interfaces-and-transceivers/isp1763a.html)
shows configurable peripheral endpoints and controller RAM, so the later hardware
is not intrinsically keyboard-only. That does not establish a usable stock
applet API or support every Neo board revision.

## Native request record and reply ownership

[`UsbRequest_t`](../../os3k/os3k_applet.h) documents the 20-byte target RAM record:

| Offset | Type | Meaning |
|---:|---|---|
| `00` | u32 | Input byte count |
| `04` | pointer | Borrowed input buffer; two-byte native key for key events |
| `08` | u32 | Writable output capacity; can be zero |
| `0c` | u32 | Output byte count written by the applet; initialized to zero |
| `10` | pointer | Borrowed output buffer |

The callback's separate third parameter is a pointer to a **32-bit reply word**.
The record is a native big-endian m68k structure, not a wire header or SETUP
packet. It has no descriptor, endpoint, USB request type, PID or transfer handle.
The ROM owns the record and buffers; consume input during the callback and write
into the supplied output buffer. Do not retain pointers or substitute a private
output pointer: direct dispatcher `44129e` queues the fixed buffer at `35fa`.

Normal direct dispatch supplies capacity `400` hex (1024 bytes). The applet must
bound its output length; the dispatcher does not turn an oversized count into a
safe bounded transfer. Keyboard events during output or suspend supply capacity
zero even though the output pointer is nonnull.

## Complete reviewed `300xx` keyboard message set

All numbers in the remaining tables are hexadecimal unless a decimal unit is
explicitly written. These sites are in **Neo 3.21**; they are not cross-ROM
address guarantees.

The keyboard loop is `41ca36`. It gets the foreground applet entry and A5 data
context and calls the applet directly. It also keeps processing controller state,
physical keyboard events, queued native keys, and text-to-HID conversion.

| Code / new name | Input / output capacity | Producer and meaning |
|---|---|---|
| `30001` `MSG_USB_PLUG` | 1 byte at `13cf8` / 0 | `41cbf4`, `41ce26`: keyboard-session attach/reopen. Host-detection state, initially `80`; EP0 device-descriptor probing updates it. This is not a USB device descriptor. |
| `30007` `MSG_USB_SEND_POLL` | empty / 1024 decimal | `41d0c0`: requests more applet output after native keyboard output drains to its sentinel. |
| `30008` `MSG_USB_SEND_DRAINED` | empty / 1024 decimal | `41cfd4`: text-to-keyboard conversion queue drained. KeyWords uses this to supply more text or finish its export. This is not a generic endpoint completion interrupt. |
| `3000c` `MSG_USB_UNPLUG` | empty / 0 | `41cde2`, `41d3ac`: keyboard-session close. Includes transition into direct mode, not only physical cable removal. Reply ignored at these notification sites. |
| `30012` `MSG_USB_SUSPEND` | 1 byte / 0 | `41cd2c`: entered suspend. Input is bit 5 of state byte `13d02`, normalized to 0/1: remote-wakeup enabled. |
| `30013` `MSG_USB_RESUME` | empty / 0 | `41ccce`: left suspend. Reply ignored at this notification site. |
| `3001e` `MSG_USB_KEY_DOWN` | native key word / 1024 decimal | `41d224` selects this code for key-down with no pending output. |
| `3001f` `MSG_USB_KEY_UP` | native key word / 1024 decimal | `41d21c` selects key-up. Input key has bit `0080` set. |
| `3011e` `MSG_USB_KEY_DOWN_BUSY` | native key word / 0 | `41d20a`: key-down while a HID/text output or native key queue is active. |
| `3011f` `MSG_USB_KEY_UP_BUSY` | native key word / 0 | `41d202`: corresponding key-up. |
| `3021e` `MSG_USB_KEY_DOWN_SUSPENDED` | native key word / 0 | `41cef2`: key-down in suspended state. Reply 9 invokes the native remote-wakeup sequence. |
| `3021f` `MSG_USB_KEY_UP_SUSPENDED` | native key word / 0 | `41cee2`: corresponding key-up, same reply-9 handling. |

Key input lives at `39fa` as two explicitly written big-endian bytes. It is the
firmware key/modifier word from `os3k_keyboard.h`, not a USB HID usage or an
already encoded HID report. The `301xx/302xx` distinctions are full message
codes: masking everything to the low byte loses meaningful state.

The old `MSG_USB_UNK_07`, `MSG_USB_UNK_1E`, and `MSG_USB_UNK_1F` remain as
source-compatible aliases. Low-byte arms `0b/0d/10/11/20` in the shared text
transfer syscall do **not** prove that `3000b/3000d/30010/30011/30020` are emitted.
They also serve other transport prefixes. No such additional keyboard message
producer was found in this ROM.

### Keyboard replies are not direct-mode replies

| Reply | Keyboard-loop consumption |
|---|---|
| `11`, `12` | On `30001`, suppress the stock attachment display. Neither exits the USB loop nor changes device descriptors. |
| `0`, `2` | In the ordinary key reply switch, append the physical native key to the firmware queue. |
| `1` | Ordinary key path leaves that key unqueued; no “send output buffer” meaning. |
| `3` | Output is a sequence of native 16-bit key words. The loop clears its low length bit and copies words into its key queue. This is not an arbitrary HID-report buffer. |
| `6` | Output bytes are text. Converter `424294` produces keyboard reports, written through endpoint selector 3. AlphaWord and KeyWords use this. |
| `13` | Invoke native dialog helper at `4242ca`, used by AlphaWord's Escape path. |
| `9` | On suspended `3021e/3021f`, invoke native remote-wakeup handling. |
| `8` | KeyWords returns this when its export finishes. It is **not** interpreted as “leave the USB loop” by the keyboard reply switch. |

The main key reply switch is `41d28a`; `30007/30008` output is consumed at
`41d12a`. Output capacity is the caller limit, not a promise that every reply
supports a 1024-byte native-key queue. In particular, do not use reply 3 as a
large raw USB buffer.

## `400xx`: the direct binary USB applet interface

This is the important additional USB family. Direct loop `440d7e` uses a
selected callback in RAM `13d56`. OUT handler `4411a4` reads logical endpoint
selector 2 and dispatches its unmodified bytes as `40002`. IN completion handler
`4411f4` drains queued output, then calls `40006` when it needs more.

| Code / name | Input / capacity | Meaning and producer |
|---|---|---|
| `40001` `MSG_USB_DIRECT_OPEN` | empty / 1024 decimal | Direct session opened/selected (`440e5a`, `44140c`). Shipped AlphaWord/AlphaQuiz reply `11` and initialize their state. Not necessarily physical cable insertion. |
| `40002` `MSG_USB_DIRECT_RECEIVE` | raw OUT bytes / 1024 decimal | `4411d4`: endpoint receive; no checksum, text conversion or updater framing is imposed by this dispatcher. |
| `40006` `MSG_USB_DIRECT_SEND_POLL` | empty / 1024 decimal | `441288`: IN queue empty, supply another chunk if desired. It may recur, so it is not a one-shot completion token. |
| `4000c` `MSG_USB_DIRECT_CLOSE` | empty / 0 | `44103c`: loop-close notification. Cleanup may already have restored the default handler before this callback. |
| `40012` `MSG_USB_DIRECT_SUSPEND` | 1 byte / 0 | `440f38`: remote-wakeup-enabled flag while entering suspend. |
| `40013` `MSG_USB_DIRECT_RESUME` | empty / 1024 decimal | `440ee8`: resume through normal dispatcher `44129e`. |

Replies are consumed by `44129e`:

| Reply | Direct-mode effect |
|---|---|
| `0`, `1`, `11`, other unrecognized values | Do not queue output merely because `output_length` is nonzero. |
| `4` | Queue `output_length` bytes from fixed caller buffer `35fa`. |
| `5` | As 4, plus set a flag to send an extra zero-length IN packet after draining the bytes. |
| `8` | Restore default callback `441064`, restore saved A5 context if present and clear selected-session state. Does not reboot the machine. |
| `0f` | Clear pending data, return to HID mode, disable/re-enable the USB controller with a delay. This is a mode transition, not an endpoint stall or mass-storage reset. |

Output is currently packetized by the ROM into **eight-byte** writes through
logical endpoint selector 3 (`44122e`, `44124e`, `441348`, `441368`), although the
stock descriptor advertises bulk max packet 64. The queue retains the source
until IN transactions drain it. Do not assume one callback or one host read is
one application message; implement framing/reassembly in the application.
Endpoint 0 request handling remains independent of this bulk callback.

The default direct handler (`441064`) recognizes a selected-app transport switch.
`?Swtch` followed by the big-endian applet ID selects an installed applet;
`43fb48` creates the acknowledgement, and `43fbc6` installs its entry/A5 context
after the acknowledgement drains, then requests `40001`. Thus a custom applet
can use its **own binary protocol after selection**, without implementing the
System updater's command set. This paragraph describes activation, not an
obligation to use the Manager file protocol.

A minimal callback body for an already selected direct session can be as small
as the following echo. It is an illustration, not an installed/tested applet or
an end-to-end host client:

```c
UsbRequest_t *request = (UsbRequest_t *)param;
*status = 0;
if (message == MSG_USB_DIRECT_OPEN) {
    *status = 0x11;
} else if (message == MSG_USB_DIRECT_RECEIVE) {
    uint32_t n = request->input_length;
    if (n > request->output_capacity) n = request->output_capacity;
    const uint8_t *in = request->input;
    uint8_t *out = request->output;
    for (uint32_t i = 0; i < n; ++i) out[i] = in[i];
    request->output_length = n;
    *status = 4;
}
```

This illustrates buffer semantics only. A real streaming applet needs its own
queue/backpressure policy so a new OUT callback does not replace pending output.

## Why a different USB class requires lower-level work

The common EP0 implementation is not dispatched to `ProcessMessage`:

| ROM address | Responsibility |
|---|---|
| `44015a` | Read/decode SETUP, swap 16-bit fields from USB order, collect limited control OUT data. |
| `440578` | Select standard versus class/HID request table. No vendor callback table. |
| `44f628` | ROM table of standard-request handlers. GET_DESCRIPTOR goes to `44083a`. |
| `44f668` | ROM table of HID-class handlers, not an applet-writable registration table. |
| `44083a` | Choose and assemble fixed descriptors. |
| `4404d6`, `4402f6` | Prepare control IN response and feed it in packets. |
| `44042e` | Stall control transfer; unimplemented request entry `44060a` calls this. |

Standard device descriptors live at `44f704` (keyboard) and `44f716` (direct).
Configuration responses are rebuilt from ROM fragments on each request; RAM
pointer `13cfe` is a scratch destination, **not a persistent custom descriptor
registration pointer**. Patching its bytes once does not replace the next reply.

| Fixed interface | Interface descriptor | Endpoints |
|---|---|---|
| Keyboard | `09 04 00 00 01 03 01 01 04` | IN `82`, interrupt, max 64 |
| Direct | `09 04 00 00 02 02 01 00 03` | IN `82` and OUT `01`, bulk, max 64 |

Direct mode advertises interface class `02`, subclass `01`, protocol `00`; it
is not mass storage (`08` / commonly `06` / `50`). The standard/class request
dispatch masks requests to four bits and rejects indices above `0e`; class
Get Max LUN (`fe`) hits the unsupported `0e` entry, and reset (`ff`) is rejected.
No applet callback receives those requests for handling. Descriptors alone
would therefore not be a complete class replacement either.

Private helper wrappers exist:

| Neo 3.21 address | Observed operation |
|---|---|
| `41f90a(selector, buffer)` | Read endpoint data; selector zero also denotes SETUP in one backend. Byte-count result. |
| `41f95c(selector, buffer)` | Read ordinary endpoint/control OUT data without that SETUP-selector adjustment. |
| `41f9a0(selector, buffer, length)` | Write endpoint payload; low byte of length is used. It is not a class-independent blocking stream write. |
| `41f9fe(selector)` | Acknowledge/clear a received endpoint buffer. |
| `41faa4`, `41faf4` | Endpoint halt/clear-halt wrappers. |
| `44044e`, `44047c` | Controller disable/enable/reset shared USB state. |

Logical selectors 0/1 are control OUT/IN, 2 is bulk OUT endpoint 1, 3 is IN
endpoint 2 (keyboard or direct according to mode). Backend mapping `41f7a4`
turns 3 into the later controller's endpoint index 5. Hardware revision byte
`041a` chooses two implementations. The later backend accesses controller
MMIO through `4500b8/4500fc` and endpoint data through `450150/450226`;
revision detection is `41f7d2`. These addresses are **not A-line syscall slots**,
verified against all 285 entries in the Neo 3.21 table. Their calling convention,
endpoint state, completion handling and IRQ ownership would need a dedicated
private driver before exposing a supported API.

A mass-storage experiment would consequently need control over descriptor
responses, class SETUP requests, endpoint halt/toggle/reset, bulk transfer state,
and block commands/backing data. A RAM hook/private stack may be possible in
native applet code, as the existing Alpha USB applet already calls private ROM
helpers, but the hookup and teardown are not established by this investigation.
There is no evidence for a one-call “select mass storage” option.

Current emulator boundary: `mame/src/mame/skeleton/neo_isp1763.h` supplies
packet-level `upstream` SETUP/OUT/IN operations; `neo_usb_link.h` carries them
over the explicit localhost DUSB link. `alphasneo.cpp` wires this into the
controller/interrupt model. These are useful foundations for testing a new
stack, but passing the native callback tests below does not qualify the whole
controller, physical PC connection, or host operating-system enumeration.

## Shipped applet cross-check

Addresses here are **file-relative** applet offsets, before installation.
All six original images and their hashes are recorded by `audit-native-usb.py`.
The sparse MathFacts dispatch tables were decoded from bytes because Ghidra
omits those branch arms.

| Applet / entry | Keyboard `300xx` behavior | Direct `400xx` behavior |
|---|---|---|
| AlphaWord Plus / `94` | Shared editor transfer object at `A5+ba`; calls `A2E4/A2E8`, using native Send text conversion. Handles native key events and queue polls through the ROM transfer state machine. | Entry routes to `8844`: `40001` replies `11`; `40002` calls parser `904c`; `40006` fills a binary/text export chunk and replies 4. This bypasses the System updater dispatcher. |
| AlphaQuiz / `e20` | Entry has no `30000` family handler. It does not demonstrate a raw keyboard interface. | Handler `71dc`: open replies `11` and calls initializer `7414`; receive calls `74f2`; close calls `88e8`. A concrete shipped example of applet-owned binary bulk traffic. |
| KeyWords / `63e` | Handler `117e`, gated by `A5+bf4==0`: attach replies `11`; Send (`2a`) on `3001e` starts export; `30008` continues/finalizes; output reply 6 requests text-to-HID conversion, completion reply 8 does not exit USB. | No `40000` branch in its entry. |
| KeyWords Wireless / `734` | Handler `4a20`, enabled by export state at `A5+417`: same `30001/30008/3000c/3001e` pattern; output reply 6. Entry also gates USB by state `A5+427`. | No `40000` branch in its entry. |
| MathFacts in a Flash / `ea` | Only attach-code table arm `30001` at `18e`, showing “Connected to USB in keyboard mode.” | Only `40001` arm at `182`, showing “Connected to USB.” No endpoint data-processing handler found. |
| MathFacts Offline / `94` | Corresponding `30001` arm `138`, with the same keyboard-mode notification. | `40001` arm `12c`, notification only. No raw receive handler found. |

AlphaQuiz's additional `50000` and `60000` branches, and AlphaWord's `20000` /
`70000` branches, are separate transport families. Their sharing the request
record does not make them USB endpoints. MathFacts' range/swap check accepts
only exact `x0001` notifications for prefixes 1–7; it does not implement every
message in every family.

## Validation, evidence and reproduction

From workspace root:

```sh
python3 betawise/research/usb/audit-native-usb.py
python3 betawise/research/usb/run-native-probe.py /tmp/neo-native-usb-probe
```

The static audit checks reviewed message-emission instructions, both fixed EP0
tables, descriptors, vendor entry offsets/hashes, and absence of the private
helper addresses from the syscall table. It is an anchor check, not exhaustive
proof that no dynamically computed message can exist anywhere.

The compiled C probe asserts all request-field offsets and legacy enum aliases.
In the running original ROM it tests `44129e` with a custom RAM callback:

1. `40002`, reply 0: input bytes reach callback unchanged; output is not queued.
2. `40002`, reply 4: input includes NUL, FF, 80; all 16 output bytes `00 11 … ff`
   reach the queue unchanged, with length and fixed buffer pointer asserted.
3. `40006`, reply 5: queue data and set the pending zero-length-packet flag.
4. `40006`, reply 8: release handler and restore the default callback.

It waits for real main-ROM execution with a RAM stack, then supplies explicit
queue/callback state. It does not require the format dialog/filesystem to be
complete and does not claim full normal boot. Return detection uses PC/SP
predicates and a bounded deadline. Guest registers, scratch RAM, queue globals
and shared output buffer are saved/restored. Flash/RAM state is disposable.

Final passing artifacts are in workspace
`.research-work/usb-raw/native-probe-final/{results.json,mame.log,probe.elf,probe.bin,probe.lua}`,
with raw callback observations and queue state in `case-1.json` through
`case-4.json`.
The initial `native-probe` fixture timed out waiting for filesystem initialization
behind a boot dialog; it is retained as failed evidence and was corrected to
use the dispatcher's actual prerequisites. No screen was guessed or bypassed
as a test oracle.

Static evidence is in `.research-work/usb-raw/evidence/`: full objdump files,
entry/handler Ghidra dumps and `native-anchors.json`. The hash manifest is
`.research-work/usb-raw/manifest.json`; independent fresh imports/dumps for all
seven images are preserved in `.research-work/usb-raw/reproduced/`.
[`reproduce-native-static.sh`](reproduce-native-static.sh) recreates the reviewed applet/controller dumps in a
fresh output directory. Exploratory dumps at non-entry offsets `41cae0`,
`41f912`, `41fa00`, `441224`, `41a000` and applet `8832` are not used as function
contracts; the final reproduction uses the verified boundaries. Ghidra's
low-byte types and truncated jump tables are checked against instructions.

The isolated applet-header Doxygen check passes. The repository-wide
`research/syscalls/coverage/check-docs.py` still fails on unrelated missing
documentation for existing display, console and stdio declarations; it is not
reported as passing.

## Later focus-ownership prototype

[Focus ownership](focus-ownership.md) traces the private interrupt callback mechanism and records an interrupt-driven Neo 3.21 RAM prototype with two passing mass-storage focus/kill-focus cycles. It does not obtain custom class handling through `MSG_USB_DIRECT_*`; it supplies a separate peripheral engine and excludes the ROM connection poll. Its emulator/physical-hardware and installed-app lifecycle limits are explicit.
