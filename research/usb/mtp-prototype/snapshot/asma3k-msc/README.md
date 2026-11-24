# AS3000 USB mass-storage prototype

Working disposable proof of concept: actual m68000 code runs in MAME and drives the emulated PDIUSBD11 through DragonBall GPIO / bit-banged I²C. No ROM calls, OS message callbacks, ROM patches or emulator source changes are used. Both a deterministic packet host and Linux VHCI have now validated the guest.

## Reproduce

Run from `/home/kirk/Projects/Alphasmart`:

```sh
python3 .research-work/asma3k-msc/src/build.py .research-work/asma3k-msc/build
python3 .research-work/asma3k-msc/src/run.py .research-work/asma3k-msc/runs/my-run --port 13260
```

Use a fresh run directory and an unused TCP port. Requires the existing `mame-usb/asma3k` binary (tested at commit `6a7b11dffbd`), AS3000 ROMs in `mame/roms`, Python 3.11+, and the `m68k-linux-gnu` GCC/binutils tools. Local socket permission is needed for the runner; its command prefix has been approved in this chat. No root, kernel module, external network connection, or host mount is needed.

Everything lives here. The runner loads a RAM binary and a generated disk through MAME Lua, starts the existing D11P socket, and uses disposable NVRAM/config directories. It does not edit or commit anything in `mame-usb` (the asma3k checkout). Remove or replace this experiment directory to discard the prototype. Rebuild after editing C; the runner uses the existing build.

## What runs where

* `src/msc.c`: USB peripheral driver, endpoint-zero enumeration, Bulk-Only Transport, SCSI subset and disk reads. These all execute on the guest CPU. Compiles to about 4.7 KB, plus BSS and stack.
* `src/build.py`: builds the RAM binary and an independently generated 32 KiB FAT12 superfloppy with a read-only `README.TXT`.
* `src/load.lua.in`: snapshots disposable guest RAM/registers, loads code at `0x30000`, disk at `0x20000`, telemetry at `0x3e000`, and stack below `0x3e000`. It transfers CPU execution to the binary; this is a debugger bootstrap, not an installable SmartApplet. On normal completion it restores RAM, registers and the original interrupt mask.
* `src/run.py`: deterministic USB host using the existing emulator packet socket. Host requests go through the chip model's actual FIFOs; the Python host does not generate device responses. Packet payloads are at most eight bytes. Logs retain every packet, guest counters, assertions and MAME output.

## Hardware ownership

The guest saves IMR and port-E settings, masks only DragonBall IRQ5 (`IMR` at `0xfffff304`, bit `0x00100000`), and keeps CPU SR interrupt level zero. It then polls the D11 interrupt register and FIFOs. It does not call the firmware event loop. PE1 is SDA and PE2 SCL; `PEDIR` at `0xfffff420` implements open-drain signalling (output pulls low, input releases). `PEDATA` is `0xfffff421`, `PESEL` is `0xfffff423`. D11 I²C command/data-write/data-read addresses are `0x36/0x34/0x35`.

D11 mode/clock writes `0x91,0x03` enable SoftConnect. Address starts at `0x80`; endpoint enable becomes `2` after SET_CONFIGURATION. Endpoint zero uses FIFO indices 2 OUT / 3 IN. USB endpoint 1 uses model indices 5 OUT / 4 IN. Descriptors advertise class 08, subclass 06, protocol 50, with bulk endpoints 01 and 81 and maximum packet size 8. Experimental VID/PID `081e:bdff` is not an assigned production identity.

The ownership test deliberately clears IRQ5's mask before entering the guest: early disposable ROM startup already has it masked. The guest then masks it itself before attachment. Telemetry verifies an initially unmasked source, masked operation, a pending IRQ5 in IPR (`0xfffff310`), SR IPL zero, and no ROM USB reads or ROM-owned GPIO writes during the run. This demonstrates interrupt exclusion in this emulator; it does not establish a universal firmware shutdown syscall or prove safe hot takeover from an arbitrary active firmware transaction. Physical integration must enter at a quiescent boundary and define a safe handback/reinitialization path. The Lua snapshot restore is a test facility, not a production exit mechanism.

## Verified result

`runs/ownership-v8/results.json` is PASS. Its raw `packets.jsonl`, `guest.json` and `mame.log` preserve evidence. Checks cover descriptors, deferred SET_ADDRESS, configuration, GET_MAX_LUN, INQUIRY, TEST UNIT READY, READ CAPACITY, write-protected MODE SENSE, exact boot-sector and multi-sector READ(10), FAT/root/file contents, out-of-range sense/residue, rejected WRITE(10) with DATA PROTECT and unchanged disk, malformed-CBW stall and reset recovery, endpoint halt status, unsupported-control stall and subsequent SETUP recovery, bus reset and re-enumeration, and the ownership assertions above. Normal completion records restoration in `restored`.

The packed CBW/CDB byte fields must be read bytewise: GCC can combine ordinary byte expressions into unaligned word/long loads, which trap on the 68000. The parser uses volatile byte reads for these fields.

## Limits

This is AS3000 hardware emulation, not Neo acceptance. No physical USB electrical/timing validation, complete BOT thirteen-case compliance, arbitrary SCSI compatibility, installed applet lifecycle, or native AlphaSmart RAM-filesystem export is claimed. The current disk is synthetic and read-only. Errors/timeouts fail the bounded host run; failed exploratory runs remain under `runs` as diagnostics. Screen contents play no role in validation.

## Linux VHCI validation

`runs/linux-vhci-v1/results.json` is PASS. The unchanged guest binary enumerated through the existing USB/IP bridge and Linux `vhci_hcd` as USB device `3-1`, VID/PID `081e:bdff`. Linux `usb-storage` bound and exposed `/dev/sdb` for this run (the device name is not fixed). The kernel reported `ro=1` and 64 sectors. Reading the entire block device produced exactly the generated 32768-byte image, SHA-256 `94018509b82c3f25de51a4bbb1ebebb159bfb2f8d47473c65a315561c7905cd3`.

Linux mounted the device using its `vfat` driver with `ro,nosuid,nodev,noexec`; `README.TXT` matched the expected contents. The helper unmounted it and detached VHCI port 0. MAME then restored RAM/registers. Guest telemetry recorded zero I²C errors, zero ROM USB reads and zero ROM-owned GPIO writes, with pending IRQ5 observed and CPU IPL zero. The run took about 89 seconds and logged 25266 packet requests. No device-side changes were needed for Linux compatibility. This run checks Linux's read-only status and a read-only mount; the earlier packet test separately exercises rejected WRITE(10).

Evidence includes `host-commands.log`, `linux-usb-descriptors`, USB/block uevents, `linux-readback.img`, `linux-README.TXT`, `host-result.json`, `guest.json`, `results.json`, `packets.jsonl` and the MAME restoration log. Screen captures were not used.

To repeat, start the normal-user runner from the workspace root (fresh directory and unused packet port):

```sh
python3 .research-work/asma3k-msc/src/vhci.py .research-work/asma3k-msc/runs/linux-next --port 13271 --timeout 900
```

Once it prints READY, run this **one administrator command** in another terminal:

```sh
sudo python3 /home/kirk/Projects/Alphasmart/.research-work/asma3k-msc/src/vhci_check.py /home/kirk/Projects/Alphasmart/.research-work/asma3k-msc/runs/linux-next
```

`vhci_hcd` must already be loaded and `/usr/sbin/usbip`, `mount`, `umount`, `dd` and `findmnt` installed. The runner exports only on localhost TCP 3241 and waits up to 12 minutes for the helper. The helper attaches only bus ID `1-1` on that port, identifies the prototype by VID/PID/serial under VHCI, verifies the block device, compares every sector and reads the filesystem, then unmounts/detaches in cleanup. MAME stays under the ordinary user; no permissions, udev rules, groups or services are changed. The existing `mame-usb/scripts/alphasmart/usbip.py` is imported without modification. The two runner files are entirely replaceable experiment scaffolding.

## Native filesystem successor

The replaceable `.research-work/asma3k-msc-fs` experiment now implements streaming FAT12 over native AS3000 files, with no guest disk/FAT/sector image. Its README records host-only checks and prepared (not executed) packet/VHCI runs. This earlier synthetic-disk run remains separate acceptance evidence.
