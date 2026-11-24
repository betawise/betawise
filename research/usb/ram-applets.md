# RAM applet upload feasibility

Checked 2026-11-23 using original ROM binaries and local neotools code. Archived
firmware source is excluded. No physical device was accessed.

## Finding

The ROM contains a private RAM-applet loader, but no stock USB/Manager command
that uploads an image to it and starts it has been identified. This is a bounded
negative result, not proof that no factory/debug transport ever existed.

The strongest protocol audit here is Neo System 3.21 and its accompanying
SmallROM. Earlier AS3000 and Neo 3.01 binaries also contain the private loader;
that does not establish an equivalent USB command on those versions.

## Distinguishing the three paths

* `install_applet` in `neotools/applet/manager.py` sends requests `06`, `02`,
  streamed data, `0B`, and `07`. The data buffer is RAM staging for **flash
  installation**, not a RAM applet installation.
* Neo 3.21's private loader is `418A06`, reached through trailer entry `44FF80`
  (also `46FF80`). It expects an image already at RAM `5C000`. It establishes
  stack/vectors, gets the applet ID with message `26` before sending INIT `18`,
  registers its header/A5, and enters the firmware event loop. It is a handoff,
  not a returning function that an ordinary host request can simply call.
* Manager request `18` enters the SmallROM updater through `400420`; this is
  separate from the RAM-applet loader. SmallROM's reset path clears working RAM
  and re-enters startup, rather than executing the RAM image.

The private loader was executed in disposable emulator RAM in the adjacent
Betawise research tree. A new applet registered and received INIT while existing
applets' A5 contents survived. This proves the loader operation, not USB delivery
or a hardware upload procedure. See
[the Manager investigation](../memory-allocation/manager/README.md), section
“Executed private RAM-applet loader”, and its `ram-evidence` records.

## Protocol audit anchors

All addresses below are Neo 3.21, hexadecimal, not cross-version constants.

The full Manager handler is `410C82`, with dispatch table at `410D70`:

| Request | Handler | Relevant result |
|---|---|---|
| `01`, `03`, `16`, `17` | `412A3A` | Unsupported in the main ROM |
| `02` | `410F44` | Receive a block into the staging buffer |
| `06` | `411122` | Begin flash applet installation |
| `0A` | `41124A` | Return saved response/status byte `0446`; no launch |
| `0B` | `41125C` | Program the staged block |
| `07` | `411568` | Finalize installation |
| `08` | `411880` | Restart |
| `18` | `4125E2` | Enter SmallROM updater |
| `19` | `412636` | Set/clear a flag byte; no launch |
| `20` | `4128A4` | Wireless-related operation, not RAM execution |

The accompanying SmallROM handler is `401A80`. Its sparse dispatch table at
`401BE2` accepts selectors `00 02 07 08 09 0A 0B 16 17 18 19`:

| Request | Handler | Relevant result |
|---|---|---|
| `02` | `401D6A` | Receive staged data through callback `4020CA` |
| `0A` | `401DA2` | Return saved status byte |
| `0B` | `401DB4` | Program segments via `402262` |
| `16` | `401C10` | Clear the segment map |
| `17` | `401C24` | Configure/erase firmware segments |
| `07`, `08` | `401F8C`, `401F78` | Set restart flag and acknowledge |
| `18` | `401C04` | Acknowledge updater mode |

`402262` copies a flash programming worker to RAM before executing it. That
RAM execution is required while writing flash and is not an applet-run command.
The direct-USB poll at `401864` handles the restart flag by clearing RAM from
`0418` to `6FFF0`, then calling `40059E`.

The main ROM's default direct handler `441064` supports `?Swtch` followed by
an installed applet ID, selecting its USB callback; it does not upload code.
The separately reviewed EP0 dispatcher `440578` selects standard and HID-class
request tables (`44F628`, `44F668`); no vendor RAM-download/execute handler was
identified there. The callback and control-request audit is recorded in
`../betawise/research/usb/native-usb.md`.

## A practical neotools feature

A RAM upload/run feature is feasible with a small, normally installed loader
applet. The host can select it using the existing `?Swtch` transport and send a
new, explicitly versioned protocol over the stock binary USB callbacks.

The loader must reserve the image and workspace against file/A5 allocation,
validate the complete image and checksum, acknowledge completion before the
nonreturning handoff, and handle supported firmware versions explicitly. The
uploaded applet needs an entry shim that answers GET_ID before initialized
C/GOT state is available. Replacement, unload, restart and subsequent Manager
installation need qualification as well; the current proof covers a fresh
RAM instance only.

Suggested host interface: `run-ram IMAGE`, requiring the loader applet and
reporting its absence rather than silently installing to flash. No speculative
stock opcode or executable CLI command has been added on the present evidence.

## DebugTool as the file-backed loader

The preferred initial approach is to add **Load/run in RAM** to the existing
DebugTool applet instead of installing a separate loader applet. Store the
unaltered OS3KApp image as an ordinary binary data file belonging to DebugTool,
transferred through the Manager file transport. This is a proposed workflow;
the complete binary upload and launch path has not yet been qualified.

DebugTool would enumerate/select its files, validate the image header, logical
length, entry offset and image/workspace sizes, reserve RAM, copy the image to
the firmware-specific loader address, and perform the nonreturning handoff.
The existing FileReadBuffer and related syscalls suffice; a generalized stdio
layer is not a prerequisite. DebugTool currently has no file-selection/loading
UI, so that is new work. The device filename need not retain the host's
`.OS3KApp` extension; image validation must use the contents.

The source file itself consumes file RAM. Reservation/compaction must account
for it, refresh any moved file references, and ensure it cannot overlap the
destination. All validation and copying must finish before handing off. The
same GET_ID-before-INIT shim and replacement/unload/reset qualifications above
still apply. Initially target the emulator-qualified Neo 3.21 loader, then
qualify hardware and other firmware versions explicitly. This runs a transient
RAM instance; it does not perform persistent flash installation.

The inspected neotools source revision was
`4e0543c42d76c0635b505b7d789632e9f7e85eeb`. Original inputs and fresh-output
reproduction are described in the Manager investigation.
