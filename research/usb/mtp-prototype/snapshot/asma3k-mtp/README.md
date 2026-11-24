# AS3000 native-file MTP prototype

This is a replaceable, uncommitted experiment for **AS3000 System 3.01** and
MAME's existing PDIUSBD11 emulation. It does not modify the emulator repository,
install an applet, implement Archive, export Applets, or touch a saved user session.
It is a foreground polling driver, using GPIO/I2C directly with the USB IRQ
masked and the native USB event pump excluded by the RAM bootstrap.

## Implemented behavior

One storage, **AlphaSmart Files**, contains applet-named association objects and
native file objects. The clipboard is excluded by both its record and reserved
ID. Data is the native logical byte stream: no AlphaWord-to-text conversion,
gap stripping, extension invention, FAT image, or whole-upload buffer.

Read-only supports DeviceInfo, sessions, storage IDs/info, object counts,
handles/info, and downloads. The read-write build adds SendObjectInfo,
SendObject and DeleteObject. It streams through a 128-byte write buffer into
files created by the actual ROM FileCreate/FileWriteBuffer calls. Cancel,
reset and exit discard an incomplete created file through FileDelete.

Uploads require an existing non-System applet folder, a representable ASCII
filename of 1–15 bytes, and available native allocation space. Unsupported
characters, duplicate names and excessive sizes are rejected before accepting
the file payload. A client replaces a file by deleting it and uploading a new
object; atomic replacement, rename, folder creation, external concurrent writers,
and crash/power-loss recovery are not implemented. Native deletion renumbers IDs;
the session handle map tracks ordinal changes instead of retaining RAM pointers.
FileCreate can grant most free file RAM as reclaimable capacity: a 513-byte
upload ended with capacity 169,472 bytes. That is native allocator policy, not a
second MTP file buffer; FileGetFreeSpace includes reclaimable allocation space.
The 256-entry session map never recycles a handle in that session. ROM global
file slots and available session handles are separate limits.

The device advertises 8-byte bulk endpoints and an interrupt IN endpoint.
Container fields and UTF-16 strings may cross packet boundaries. Explicit byte
loads/stores are necessary: this GCC version otherwise merged accesses into
unaligned word/long instructions that fault on a 68000. Data and response
transfers terminate with a ZLP when required. Event messages use logical EP2
(model index 7), not the bulk endpoint. The event queue is intentionally small;
external-change notification policy and every class recovery edge are not
production-qualified.

## Native allocation and harness safety

The historical disposable file fixture is repacked contiguously from native
buffer base 0x4558, preserving all logical contents. The real ROM checker requires
that base and contiguity; 0x6000 was an invalid first attempt. The native allocation
ceiling at 0x354e is reduced to 0x30000. RAM above that holds this test's code,
BSS, stack and telemetry, and cannot be reclaimed by FileCreate. Mirrors to old
applet variables are cleared in the fixture. The same saved CPU/RAM snapshot is
restored on normal completion. This is not an installed-app RAM-allocation design.

Sources: usb.c is the GPIO/I2C/EP0 polling engine derived from the existing MSC
experiment; mtp.c owns transactions, metadata and writes; native_fs.c reads the
AS3000-specific native tables; syscalls.S contains genuine A-line entry stubs.
There are no private ROM function calls in the file write path. Native table
addresses and the loader's allocator ceiling remain firmware-specific.

## Footprints

Build commands, from workspace root:

```sh
python3 .research-work/asma3k-mtp/src/build.py .research-work/asma3k-mtp/build-ro
python3 .research-work/asma3k-mtp/src/build.py .research-work/asma3k-mtp/build-rw --writable
```

Same m68000 GCC -Os toolchain, without LTO:

| Build | Code/constants image | Static writable RAM | Observed stack |
|---|---:|---:|---:|
| Existing read-only FAT12 | 11,915 bytes | 252 bytes | 568 bytes |
| Read-only MTP | 7,697 bytes | 648 bytes | 388 bytes |
| Read-write MTP | 10,575 bytes | 1,864 bytes | 456 bytes |

“Code/constants” is the ROM-able linked binary, **not** an installed .OS3KApp
size. In this RAM-bootstrap prototype that code occupies RAM too. Applet header,
startup/fixups and installed-app integration are not included. Static RAM excludes
stack, the test-only 84-byte telemetry block, and native storage for the files.
The harness reserves 8 KiB of stack conservatively; that is not measured stack
consumption. Raw build reports and .su files are retained in each build directory.

Measured stack results and the comparison are recorded in comparison.json.
The early “5,171 bytes stack” number was invalid: an unrelated firmware write to
0x3cbcd changed the fill pattern far below SP. Final measurements track stack
writes against live SP and retain both readings. The cached-instrumentation FAT rerun at ../asma3k-msc-fs/runs/footprint-v3
passed with 568 bytes of observed stack. Read-only MTP used 388 bytes;
the VHCI read-write run used 456 bytes. These are observed peaks for covered
paths, not exhaustive upper bounds.

## Acceptance and host compatibility

- runs/resource-ro-v1: final read-only packet checks, all 16 file hashes,
  native records/payload unchanged, no ROM USB servicing or I2C errors.
- runs/rw-packets-v7: earlier full native create/read/delete, sizes 0, 1, 7, 8,
  9, 127, 128, 129, 511, 512, 513 and 4096; stable handles through deletion;
  deleted handles rejected; name/space rejection; partial upload cancellation.
- runs/final-rw-v2: final driver regression, additionally checking interrupt
  ObjectAdded/Removed containers and ZLPs through the emulated endpoint.
- runs/vhci-v3/ro: **PASS** with unmodified gphoto2/libgphoto2 and the independent
  kernel host. All 16 files downloaded and compared through actual Linux VHCI.
- runs/vhci-v5/rw: final firmware **PASS** with the independent Linux VHCI/libusb
  host: all original files and zero/513/4096-byte upload/readback/delete. Its host
  logs/results are referenced from runs/vhci-v3/rw, whose existing privileged
  helper reattached this replacement without another sudo command.

Stock-client findings are separate from protocol acceptance:

1. Installed libmtp 1.1.20 fails on 8-byte endpoints during session setup. Its
   ptp_usb_getpacket asks for wMaxPacketSize bytes (8), then its upper layers
   expect a complete 12-byte header. We did **not** falsify descriptors, patch
   libmtp, or count this as a successful stock-MTP-client test. Source:
   https://github.com/libmtp/libmtp/blob/master/src/libusb1-glue.c
2. Unmodified gphoto2/libgphoto2 handles the 8-byte endpoints and downloads files.
   Its zero-byte upload fails locally before it sends the data container. The
   zero object can already exist after successful SendObjectInfo; the independent
   host separately validates a complete zero-byte upload.
3. Gphoto2 uploaded and downloaded the 513-byte binary correctly. The checker then
   failed because `%f` omits an extension: it looked for VHCI513.BIN instead of
   the downloaded VHCI513. The stored bytes were independently compared exactly.
   Gphoto2 deletion and a complete 4096-byte gphoto round trip were not certified;
   both operations are covered by the independent kernel client.

Thus AS3000 protocol feasibility is established, but broad plug-and-play MTP
compatibility is **not**. Neo with a genuinely larger usable endpoint is a
reasonable next compatibility target, requiring its own hardware/backend test.
No claim is made about Windows Explorer, macOS clients, Android, or physical
AS3000 hardware from this emulator run.

The root checker unmounted nothing (MTP creates no block disk), attached only
localhost:3242, selected only the unique prototype under vhci_hcd, and detached
its port. Final services were stopped after capturing evidence.

## Timing and resource findings

comparison.json is produced by src/analyze.py. The bridge records packet socket
service time, lock wait, actual NAK backoff, USB/IP URB durations and bytes.
Clients record individual operations/stages. Queue/backoff totals may overlap
other tasks and must not be added as an exclusive wall-time partition.

The final independent VHCI run spent approximately 14.72 s in downloads
(8,705 payload bytes), 8.93 s in uploads (4,609 bytes), 3.17 s in 19 ObjectInfo
queries, and 0.75 s listing handles. Delete operations totaled 0.18 s. Initial
kernel enumeration in the earlier attach test was about 0.8 s. These measurements
place the main cost in packet movement/polling and metadata round trips, rather
than attachment or native deletion. Gphoto2 command invocations reopen sessions
and enumerate metadata repeatedly, making command-level timings larger.

Combined final VHCI diagnostics had about 81% NAK packet requests. The bridge
polls its packet socket per 8 bytes and sleeps after a NAK; the guest bit-bangs
I2C and polls controller state. Avoiding idle endpoint polls improved the final
driver, but these numbers are not a physical-controller speed limit. The old
193-second FAT mount is historical evidence, not a controlled speed comparison
with this final build: its instrumentation and host memory pressure confound it.

A harness bug caused substantial **host**, not guest, memory growth. Accessing
cpu.state.PC.value on every GPIO write recreated register-view tables. Caching
cpu.state once kept final MAME RSS around 82 MiB with no emulator swap. A single
busy polling emulator still uses roughly one CPU core. Final launchers run at
nice +10, log one-second RSS/swap/CPU samples, cap address space at 1.5 GiB, and
kill a run above 512 MiB RSS or below 768 MiB host available memory. The launcher also holds a single-emulator lock; parallel
emulator testing is prohibited. The early resource-heavy/incomplete runs are retained
as failures, not promoted to accepted results.

## Interactive Thunar plain-PTP experiment

`build-ptp-ro` is built with `--ptp`: Microsoft OS descriptors and MTP interface
signatures are removed, DeviceInfo has no MTP vendor extension, and the USB
identity is 081e:bdfd / AS3KPTP1. Core native-file operations are unchanged.
`runs/ptp-packets-v1` passes the read-only protocol/hash tests and checks the
PTP identity and absent Microsoft OS string descriptor.

`runs/thunar-ptp-v1/rw` (the folder name follows the existing single-instance
launcher convention; the build is READ ONLY) is the user inspection run. It
adds a readable Keywords/README.TXT to the disposable fixture. The user attached
it using vhci_inspect.py. Settled udev properties report ID_GPHOTO2=1 and
GPHOTO2_DRIVER=PTP, with no ID_MTP_DEVICE. No backend was forced or udev rule
modified. Actual Thunar browsing is for the user to assess. The emulator runs
at half speed, nice +10, with the same memory monitor and single-instance lock.
Detach later with the same helper and `--detach`; the service then restores
state and exits. The service has a 20-minute inspection deadline.
