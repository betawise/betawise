# AS3000 native filesystem as streaming FAT12

Implemented a read-only `/Applet/File` view of the AS3000 System 3.01 RAM filesystem, replacing the old synthetic README disk. The FAT12 volume is a virtual 4096-sector (2 MiB) superfloppy. No such disk image exists in guest RAM: the guest generates each requested byte into the USB driver's existing eight-byte packet buffer.

**Status:** the clipboard-excluding build passes local filesystem checks and the AS3000 packet integration test (`runs/documents-packets-v1/results.json`): all 16 files match, writes are rejected, and native records/content remain unchanged. Linux VHCI validation also passes in `runs/documents-vhci-v2/results.json`; that run was left mounted read-only for inspection and has now been unmounted/stopped at the user’s request. The earlier `documents-vhci-v1` is the failed short-timeout attempt, retained as diagnostics.

## Files exposed

* One directory per installed applet, retaining its display name, plus System. Native folders containing records are included even if their applet header is absent, using a fallback name.
* Every record in each native folder, rather than probing only File keys 1–8. Named, unbound, empty and grouped/profile records are included without changing active user/folder/current-file state.
* The clipboard is excluded. Its global record and reserved ID `00CB` are filtered even if present inside an applet table. It is working state, not an exported document.
* Existing filename extensions are preserved. Extensionless native formatted-text files use `.RAW`; other extensionless files use `.BIN`.
* Contents are exact native **logical-length raw bytes**. There is no conversion of AlphaWord gaps, formatting markers, character encoding or line endings. Native allocation slack and FAT cluster padding are never exposed as file data. A `.py` or `.txt` name is retained but does not imply that native formatting has been removed.
* FAT long filenames preserve readable names and case. Invalid/non-ASCII filename bytes are reversibly escaped as `_HH`; original underscore/tilde bytes are escaped too. DOS device names are prefixed. Case-insensitive duplicates gain `~hhhh` before the extension (or at the end of an app directory name), using their native record/app ordinal. Unique 8.3 aliases use the ordinal, so duplicate native IDs do not hide files. All files have the FAT read-only attribute.

This is filesystem content exposure, not a complete native restore container: passwords, reservation values, tags, file-key bindings and all other native attributes are not generated as extra USB files. Host acceptance manifests retain IDs/tags/flags from the disposable source capture for comparison.

## How FAT is generated without a FAT in RAM

`src/fat12.c` computes boot bytes, FAT12's packed twelve-bit entries, VFAT directory entries and file data on demand. Each app directory and file has a contiguous virtual cluster extent. Extents are derived by scanning existing native records and summing lengths; they are not stored in a generated per-file index.

Each root app slot reserves ten virtual directory entries and each native file reserves six. This covers the maximum escaped long names. Unneeded leading entries are emitted as deleted entries, with a real end marker after the last object. Fixed virtual slots make directory sizing independent of repeated long-name/collision calculations. This costs virtual disk space, not guest RAM.

Only scalar session state, one extent cache, one naming cursor and one directory-position cursor are retained. These do not contain FAT chains, directory entries, sector images or filename strings. File payload reads copy directly from native buffers into the existing eight-byte USB packet buffer. No malloc, file-opening calls, folder selection or ROM filesystem calls are used.

The view must remain immutable while mounted: other applets/native file writers and allocations must be quiesced. A metadata fingerprint is checked at READ(10)/readiness boundaries; a change invalidates the view and subsequent accesses fail until a new session. This guard is not a concurrent-filesystem snapshot or cryptographic integrity scheme. Reads perform bounds checks and malformed native records/virtual capacity overflow fail closed instead of silently dropping files.

FAT12 fits the physical AS3000 RAM scale: 512-byte sectors/clusters, two twelve-sector FATs, 512 fixed root entries, and 4039 data clusters (below FAT12's cluster-count cutoff). FAT16 would add no benefit for this view. The unused virtual sectors are generated as zero, and the block device remains read-only.

## Measured build footprint

Current `build/build.json`:

| Item | Bytes |
|---|---:|
| Guest code/read-only constants | 11915 |
| All static writable state, including USB/BOT | 252 |
| FAT view's share of that state | 60 |
| Full disk image | 0 |
| Sector buffer | 0 |
| Test-only fixed-address telemetry | 84 |
| Conservative private stack reservation in RAM harness | 8192 |

The prototype loads its code into RAM, so **252 bytes is not the total RAM occupied by the debugger-loaded experiment**. An installed applet would need proper flash-code/RAM-data linking; that packaging is not implemented here. Stack peak is not yet measured; `.su` files retain compiler per-function stack reports. There is no generated guest FAT/directory cache proportional to file count.

## Source and target dependencies

* `src/msc.c`: existing AS3000 PDIUSBD11 GPIO/I²C and read-only BOT/SCSI driver, adapted to call the streaming reader. It reduces the old general response buffer from 256 to 36 bytes.
* `src/native_fs.c`: read-only AS3000 3.01 memory adapter: applet table `0xD82`, native folder descriptors `0xF42`, clipboard-exclusion pointer `0x344A`, and 72-byte native records. Uses private RAM layout, not private ROM calls. Unknown ROMs require a qualified adapter/resolver.
* `src/fat12.c`: format/sector/name/cluster generator, independent of USB.
* `src/catalog.py` and `src/walk_fat.py`: independent host catalogue and strict FAT/VFAT reader for acceptance.
* `src/prepare.py`: prepares disposable source RAM/flash, checks live file/record overlap and creates scripts/expected manifest; does not execute an emulator or open sockets.
* `src/run.py`, `src/load.lua.in`, `src/vhci_check.py`: future packet and Linux acceptance scaffolding.

This fork keeps the previously validated **AS3000 polling takeover** (USB IRQ5 masked while running) to isolate filesystem work. It does not silently substitute the Neo focus-callback experiment or claim AS3000 focus/interrupt-driven takeover acceptance. All experiment changes are here; neither emulator checkout was modified.

## Local checks already completed

```sh
python3 .research-work/asma3k-msc-fs/src/build.py .research-work/asma3k-msc-fs/build
python3 .research-work/asma3k-msc-fs/tests/check.py .research-work/asma3k-msc-fs/checks/my-check
```

`checks/no-clipboard-v2/results.json` is PASS. The same C generator, compiled for the local host with a read-only memory fixture adapter, passed:

* All 16 document files in the earlier disposable native AS3000 AlphaWord/KeyWords capture, with the clipboard excluded; directory names, every logical byte and native-memory immutability.
* Clipboard exclusion even when its record belongs to an applet table; synthetic collisions, escaped/non-ASCII/reserved names, existing extensions, empty files, group IDs, app slot 31, exact and partial cluster sizes, and a 255-record/multi-cluster directory.
* Both generated FAT copies, packed FAT12 cross-sector boundaries, VFAT order/checksums, cluster chains, arbitrary unaligned reads, zero file slack and unallocated space.
* Out-of-volume reads, corrupt metadata/buffers, metadata mutation and oversized virtual allocation rejection.
* Independent mtools directory read of a host-only generated image. `fsck.fat` was unavailable, so no fsck result is claimed.

The test output may contain a materialized disk **on the host** for independent tooling. It is never loaded into the emulated device. These host checks do not execute the m68k build, GPIO/I²C or USB protocol. Failed/exploratory runs and old slow-layout results are retained separately; only the latest fixed-slot generator is current.

## Emulator and VHCI testing

The clipboard-excluding packet run is `runs/documents-packets-v1` (PASS). Prepare fresh directories after any binary rebuild; the old `prepared-*` directories are historical and have stale hashes.

```sh
python3 .research-work/asma3k-msc-fs/src/prepare.py .research-work/asma3k-msc-fs/runs/my-packets --ram betawise/research/multi-user/evidence/as3000-3.01/alice-created.ram.gz --port 13310
python3 .research-work/asma3k-msc-fs/src/run.py .research-work/asma3k-msc-fs/runs/my-packets
```

Run the packet test first. It reads and independently walks the virtual FAT tree, compares every exported file with the native source capture, attempts a rejected write, and verifies native records/content remain unchanged. Successful cleanup restores the disposable boot RAM/register snapshot. The packet runner needs local socket permission.

For the VHCI run, the runner prints a single administrator command only after READY:

```sh
sudo python3 /home/kirk/Projects/Alphasmart/.research-work/asma3k-msc-fs/src/vhci_check.py /home/kirk/Projects/Alphasmart/.research-work/asma3k-msc-fs/runs/prepared-vhci
```

That future helper identifies only the localhost prototype under VHCI, checks the kernel's read-only/4096-sector status and usb-storage binding, mounts read-only, compares the complete directory/file tree through Linux FAT, then unmounts/detaches. It does not read all unused virtual sectors. Existing kernel VHCI and usbip are required; no permissions/services/udev configuration are changed.

A prepared run is tied to its guest binary hash; rebuilds require a fresh preparation directory. The default preparation fixture reconstructs the reviewed AlphaWord + KeyWords flash layout for the historical disposable RAM capture. Other disposable captures need `--flash` with a matching 1 MiB flash dump in guest byte order; the full ROM region is hash-checked. Inputs are read-only. No user's saved session is mutated.

The RAM bootstrap checks native live payload/record overlap before loading code. It borrows only unused capacity/address ranges while native writers are stopped; it is not a production allocator. It zeros only the actual BSS and private stack/telemetry, leaving native live files intact. Proper installed-app allocation, live focus lifecycle, performance and physical hardware remain future qualification work.

## Leaving a successful VHCI test mounted

The runner accepts `--vhci --leave-mounted --background`. It starts a detached normal-user service and writes `service.pid`/`service.log`. The administrator checker must also receive `--leave-mounted`. On success it retains the read-only mount and VHCI attachment; the bridge and MAME remain running without an inspection timeout. On checker failure it still cleans up. `host-result.json` records the actual block device, mount path and VHCI port. `results.json` includes live guest-memory/ownership checks before `inspection-ready` is written.

To release an inspection mount, first unmount it and detach its recorded VHCI port with administrator privileges. Then create the run directory's `release` file; the service disconnects the emulated peripheral, restores its disposable RAM/register snapshot and exits. Do not stop the service while continuing to use its mounted device.

The first native-files VHCI attempt (`documents-vhci-v1`) hit the helper’s 30-second `mount` deadline. The mount nevertheless completed late; cleanup detached the device and left a stale mount. The checker now allows 300 seconds for mounting, logs commands before execution with elapsed times, detects late mounts during failure cleanup, and supports explicitly removing the previous run’s stale mount. The second run records this cleanup and validation separately; no first-attempt PASS is claimed.

## Successful mounted run

`runs/documents-vhci-v2/results.json` is PASS: Linux `usb-storage`, USB `3-1`, block device `/dev/sdb`, 4096 sectors, read-only FAT12/vfat. All 16 files in AlphaWord Plus and Keywords matched the native source capture exactly; System is empty and the clipboard is excluded. Live guest checks confirm native records/content unchanged, no I²C/errors, and no ROM USB servicing. The mount command took 193.269 seconds with this unoptimized emulation/transport; subsequent file verification completed successfully.

Mount point:

`/home/kirk/Projects/Alphasmart/.research-work/asma3k-msc-fs/runs/documents-vhci-v2/mount`

The normal-user emulator/USB-IP service remains running with no inspection timeout. Its PID and log are in that run directory. The mounted data is the **disposable historical AS3000 capture**, not a physical device or a user's live saved session. Native formatted-text files are raw exports.

When inspection is finished, run these in order (do not run them while still using the mount):

```sh
sudo umount /home/kirk/Projects/Alphasmart/.research-work/asma3k-msc-fs/runs/documents-vhci-v2/mount
sudo /usr/sbin/usbip detach -p 0
touch /home/kirk/Projects/Alphasmart/.research-work/asma3k-msc-fs/runs/documents-vhci-v2/release
```

The final marker lets the background service restore its disposable guest snapshot and exit. Port 0 above is the port recorded for this run; another run may use a different one.

## Shutdown and design review

The inspection session is now stopped. `runs/documents-vhci-v2/shutdown.json` records unmount/detach/restoration, and `shutdown-verified.json` independently confirms no mount, no bridge listener and no running service. The MAME log records guest restoration and normal termination. `src/unmount.py RUN` is the one-shot administrator helper for this sequence.

The 2 MiB geometry is a prototype virtual address-space allowance for generated metadata and cluster rounding, not a native capacity measurement. This particular AS3000 source capture is 256 KiB. Current FAT-free clusters describe unallocated **virtual** sectors, not available native RAM. A production read-only export should use compact geometry at mount. Writable capacity needs a separate allocator-budget and metadata/commit design; READ CAPACITY alone cannot report native free bytes to a FAT host.

The registered native `TextScanRead` interface already supports plain-text conversion, including gaps/format tokens, on reviewed AS3000/Neo test cases. Thus a device-side `.TXT` export/import adapter is possible without a new editor or mandatory bespoke host converter. Current USB exposure remains raw. The capture’s first AlphaWord buffer has eight ordinary bytes and 504 A7 bytes; seven other AlphaWord buffers are 512 A7 bytes, and Keywords files are empty. This validates byte-preserving exposure but is not rich document interoperability coverage. Next acceptance should use deliberately created native documents with paragraph/wrap/escape/formatting cases and nontrivial binary/app files.

Architectural choices remain open: read-only FAT is convenient for mounted export; arbitrary writable FAT needs retained allocation/directory state and an ordered native commit strategy. MTP matches file/object operations and native capacity more directly but has a different host client experience. CDC serial with an existing Kermit implementation can simplify transactional file transfer, while still requiring USB class support and host client software. Multiple MSC LUNs can expose separate document/app views, but app writes must perform validated installation rather than raw flash-sector copying. These are design findings, not newly implemented write/import/MTP/Kermit features.
