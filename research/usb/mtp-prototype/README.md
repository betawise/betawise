# AS3000 MTP/PTP prototype: reproducibility and trace retirement

The prototype implements native-file read-only MTP/PTP and experimental MTP
create/read/delete on AS3000 System 3.01 with MAME's PDIUSBD11 backend.
`snapshot/asma3k-mtp/README.md` records footprints, acceptance results, host
compatibility limitations and timing findings. Snapshot source includes the MSC
harness dependencies and USB/IP bridge. It is historical experimental code,
not a production applet or a hardware certification.

Independent VHCI clients passed native-file download/hash checks and read-write
round trips. Stock libmtp 1.1.20 failed to handle 8-byte endpoints. Gphoto2
showed partial compatibility. Interactive Thunar inspection is not an automated
acceptance pass. Final measured independent-host transfers took approximately
14.72 seconds downloading 8,705 bytes and 8.93 seconds uploading 4,609 bytes;
about 81% of bulk packet requests were NAKs. Timings reflect emulator polling,
not physical USB performance. See comparison.json in the snapshot.

## Reproduce packet timing output

From the AlphaSmart workspace root, restore snapshot source into its historical
layout if those local experiment directories have been removed:

```sh
cp -a betawise/research/usb/mtp-prototype/snapshot/asma3k-mtp .research-work/
cp -a betawise/research/usb/mtp-prototype/snapshot/asma3k-msc .research-work/
cp -a betawise/research/usb/mtp-prototype/snapshot/asma3k-msc-fs .research-work/
```

Use the workspace m68k-linux-gnu toolchain, Python 3, the USB-capable
`mame-usb/asma3k` executable and reviewed AS3000 ROMs in `mame/roms`.
The bridge source is retained under `snapshot/mame-usb/` for version comparison;
it belongs at `mame-usb/scripts/alphasmart/usbip.py`. Rebuild commands:

```sh
python3 .research-work/asma3k-mtp/src/build.py .research-work/asma3k-mtp/build-ro
python3 .research-work/asma3k-mtp/src/build.py .research-work/asma3k-mtp/build-rw --writable
python3 .research-work/asma3k-mtp/src/build.py .research-work/asma3k-mtp/build-ptp-ro --ptp
```

## Create the input fixture afresh

No historical native-before.ram or flash-memory.bin is required. In the
restored experiment source layout above, make a new input directory and boot
original System 3.01 with the reviewed AlphaWord/KeyWords applets. Use only the
new NVRAM/config directories, never a user's saved session:

```sh
mkdir -p /tmp/as3k-fixture-new
AS3K_FIXTURE_OUT=/tmp/as3k-fixture-new mame-usb/asma3k asma3k \
  -rompath mame/roms -nvram_directory /tmp/as3k-fixture-new/nvram \
  -cfg_directory /tmp/as3k-fixture-new/cfg -window \
  -autoboot_delay 0 -autoboot_script \
  betawise/research/usb/mtp-prototype/capture-fixture.lua
```

Initialize through the normal firmware prompts, enter a short known test
sentence in a disposable AlphaWord file, return to normal foreground operation,
and request capture from another terminal:

```sh
touch /tmp/as3k-fixture-new/capture-request
```

The helper captures this new input RAM/flash and exits; it makes no display or
protocol acceptance claim. The preparation code checks original ROM identity,
native metadata, allocator bounds, and payload/code overlap before use. The
packet checker derives expected file hashes from that input and verifies all
exported files. Select an existing non-System applet folder for uploads.

```sh
python3 .research-work/asma3k-mtp/src/prepare.py \
  .research-work/asma3k-mtp/runs/reproduce-ptp/rw \
  --ram /tmp/as3k-fixture-new/native.ram --flash /tmp/as3k-fixture-new/flash.bin \
  --build .research-work/asma3k-mtp/build-ptp-ro --port 13360 --timeout 1200
touch .research-work/asma3k-mtp/runs/reproduce-ptp/rw-only
python3 .research-work/asma3k-mtp/src/serve.py \
  .research-work/asma3k-mtp/runs/reproduce-ptp --background
```

The service writes `rw/timings.jsonl` (socket requests, status/NAKs, queue wait,
backoff and USB/IP URBs) and `resources.jsonl`. For interactive reproduction,
load Linux `vhci_hcd`, then run the following helper with the required root
privileges; it attaches only the uniquely identified localhost prototype:

```sh
sudo python3 .research-work/asma3k-mtp/src/vhci_inspect.py \
  .research-work/asma3k-mtp/runs/reproduce-ptp/rw
# Browse AlphaSmart Files in Thunar, then detach:
sudo python3 .research-work/asma3k-mtp/src/vhci_inspect.py \
  .research-work/asma3k-mtp/runs/reproduce-ptp/rw --detach
```

Run one emulator at a time. The resource monitor and single-instance lock are
part of the snapshot. Use bounded runs; a long idle attachment creates large
NAK traces. The `rw` directory name is a launcher convention; the PTP build is
read-only. Create the input fixture afresh as above. Historical file counts, payload sizes
and host timing are observations of the old fixture, not exact expectations
for a newly authored set of documents. Packet workloads can also be
exercised by `python3 .research-work/asma3k-mtp/src/run.py NEW_RUN_DIR`
after preparing that directory. For write tests, prepare with `--writable` and
`--build .research-work/asma3k-mtp/build-rw`.

## Retained results

The source snapshot, verified-build metadata and compact comparison.json retain
footprints, accepted host timing totals, NAK proportion, stack observations and
compatibility limits. Per-packet traces, per-run prepared/guest/host records,
resource streams and raw fixture captures are reproducible outputs and are not
retained. The source collector/analyzer generates them again for a fresh run.

The new input helper was added during consolidation; no new protocol or
hardware acceptance pass is claimed for it. Changing the fixture changes file
counts, transferred bytes and timing. Fresh runs reproduce format, covered
operations and validation behavior rather than old monotonic timestamps or a
user's exact browsing sequence. Neo screen validation never uses these traces.
