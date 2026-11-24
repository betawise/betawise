# Reusing the USB command protocol over wireless

## Finding

Neo 3.21 separates its USB endpoint transport from memory-buffer command
processing. A wireless bridge can plausibly reuse that processing rather than
reimplementing the command set. This is a verified entry-point experiment, not
a functioning wireless tunnel or a complete file-operation compatibility claim.

The original ROM passed seven local MAME cases without reading or writing the
USB controller at `02000000..02000007`. No ROM instructions were patched, no
physical device was connected, and only disposable emulator state was used.

## Entry points and boundaries

| Address | Instruction-level finding |
|---|---|
| `441064` | Default USB protocol callback, taking event, request-block pointer and status-output pointer |
| `4410de` | One-byte request `01` produces two response bytes `02 30`, response length 2 and status 4 |
| `43fb48` | Shared `?Swtch` lookup; writes an eight-byte response and records a pending applet index plus one at `3dfd` |
| `441170` | Event `40006` completes a pending switch through `43fbc6`; lookup alone does not execute it |
| `43f97a` | Loads/routes requests to applet protocol handlers, changing execution/context state |
| `41080e` | System protocol adapter for event group `40000`; forwards data to the current parser pointer at `047a` |
| `4108f8` | Related adapter for event group `50000`, also using parser pointer `047a` |
| `410c82` | Default command parser, including checksum validation and the command switch |
| `412bca` | Parses the eight-byte command block and checks its additive checksum |
| `412c28` | Constructs an eight-byte response block and checksum |
| `412c82` | Resets parser/transfer state, restoring `047a = 410c82` |

The request block used by `441064` has 32-bit fields: input length at +0,
input pointer at +4, output capacity at +8, output length at +12 and output
pointer at +16. The direct parser fixtures call `410c82` with input pointer,
input length, output pointer, output-length pointer and capacity, each in a
four-byte stack slot. Those fixtures exercise simple replies only; they do not
prove capacity enforcement for arbitrary commands or continuation handlers.

USB, another transport adapter at `419ff2`, and the IrDA callback at `43d6e6`
use the same `43fb48` lookup and/or `43f97a` applet routing helpers. IrDA uses
event group `70000`. This is existing firmware precedent for sharing protocol
machinery across transports; it does not establish identical wire framing.

## Executed checks

`check-usb-dispatch.py` runs original 68k routines directly, with guest RAM
buffers and a bounded return predicate. It verifies returned stack position,
reply status/length, exact reply bytes, a guard byte after the reply, pending
switch state, and zero accesses to USB-controller registers during each call.

1. Protocol identification returns `02 30` without USB attachment.
2. A different event does not trigger that identification response.
3. An absent applet produces `NoApplet`.
4. A synthetic registered applet produces `Switched` and records index + 1,
   without executing that applet. This deliberately isolates lookup from the
   emulator's boot UI and installed-app state.
5. A corrupt command checksum produces `8f 00 00 00 00 00 00 8f`.
6. Valid command `19` produces `57 00 00 00 00 00 00 57`.
7. Valid command `20` produces `94 00 00 00 00 00 00 94`.

The last three call the shared parser directly. Simple parser responses require
neither the USB endpoint nor a foreground-app switch. File reads, applet loading,
parser continuations, reset and session cleanup remain untested here.

## Why not enter the normal USB session?

The normal event loop pumps wireless association, upload and receive processing
at `417cba`, `417cca` and `417cd0`. USB detection takes another path through
`417d0e -> 41ca36`. That session has its own loop, USB-controller calls, applet
events and exit condition. The reviewed loop does not contain those three
wireless-pump calls. Consequently, entering the normal USB session is not an
established way to keep a wireless bridge alive.

The bridge should instead remain in the ordinary system-pump context and call
the buffer-processing layer deliberately. `43f97a` and `43fbc6` can change applet
execution state, so forwarding every request blindly from a wireless callback
is not yet justified. A scheduled worker, separate saved session state and
correct A5/context restoration need investigation before general applet routing.
The parser also has a continuation pointer at `047a`: calling `410c82` for every
packet would incorrectly restart multi-stage operations.

## Proposed implementation boundary

On the computer, retain neotools' command blocks and payloads behind a new
`Device.read/write` implementation. Wireless envelopes must retain record
lengths/short responses, sequence/transaction identity and ordering. A lost reply
must not cause a write command to execute twice. No USB enumeration, HID mode
switching or physical endpoint emulation is required for this architecture.

On the Neo, start with identification and one read-only command through the
shared parser. Next seed a disposable file and exercise its complete read
transaction, including parser continuations and a return to normal applet
operation, while independently verifying that wireless pumping still advances.
Only then connect the entry points to the stock-radio transport. This leaves
the previously identified radio-protocol compatibility work in place.

## Reproduction

```sh
python3 betawise/research/wireless-server/check-usb-dispatch.py /tmp/neo-usb-buffer-dispatch
```

The output includes the generated Lua fixture, MAME log, SHA-256 and result JSON.
Source ROM identity is checked against the maintained `neo_3_21` inventory.
Selected stock instructions are recorded in `usb-dispatch-instructions.txt`.
No screenshots or model inference are used for validation.
