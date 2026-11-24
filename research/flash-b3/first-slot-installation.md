# First-slot sizing, scanner validation and host installation

Read-only disassembly/source checks plus a normal FileManager build,
2026-11-21. No device installation, erasure, firmware patch or compaction.

## Size and geometry

AS3000's first applet starts at 408000: offset 8000h = 32 KiB, not 64 KiB.
With the Micron/older-Intel bottom-boot map C, the sector starting there is
96 KiB, 408000..41FFFF. A 64-KiB image ends at 418000 and fits in that sector,
but the first independently recyclable following sector begins at 420000.
Protect/reserve the whole 96-KiB extent from the applet start, not only 64 KiB.

For bottom-boot Intel B3 map D, a <=32-KiB prefix can stop at 410000 before
the main-block region. A 64-KiB prefix crosses into 410000..41FFFF, so its
next safe main-block boundary is again 420000. Top-boot geometry differs.
The correct layout follows sector boundaries, not just executable length.

The current prototype built with `make -C applets/FileManager -j2` produces
5,246 bytes (4,746 text + 500 data; 630 BSS is RAM, not image bytes). Its
unused experimental flash backend is garbage-collected from this build. This
is not a size measurement of the proposed USB/FAT installer, compressor or
recovery engine. A 64-KiB budget is plausible but should be enforced explicitly.

## Native scanner and validator

AS3000 System 3.01 validator: 4C3248..4C32D0. NEO13 equivalent:
41330C..4133A8. The observed checks are:

* Header longword C0FFEEAD.
* ROM size no greater than the applet-region capacity.
* Optional strict check: flags' high byte equals FFh (used for registration).
* Header address plus ROM size does not exceed the applet-area end.
* Footer CAFEFEED at end-4, with a compatibility alternative at end-6.
* Requested RAM fits both a platform ceiling and the caller's remaining budget.
* Relative entry longword at offset 84h is nonzero and no greater than the
  applet-region capacity. This is not a check that the entry lies inside the
  declared individual image.

No applet-body checksum is calculated by these validators. No explicit minimum
ROM size or even-size check appears before the calculated footer dereference.
In particular, a still-valid magic plus an odd torn size below the capacity
limit can cause an odd-address longword read rather than clean rejection. This
is a static fault-path inference, not an executed odd-size fault experiment.

AS3000 registration at 4C3038..4C3246 and NEO13 at 4130FC..41330A traverse
consecutive header-declared extents. The generic validation gate stops at the
first invalid image, retaining earlier registered entries. A stricter flags
check can exclude an entry while traversal advances past its valid extent.
There is no resynchronization search at the next erase-block boundary.

Consequently, a valid first FileManager and a clearly invalid next magic can
leave FileManager discoverable. This does NOT guarantee boot after every partial
erase/program: a malformed surviving header may fault, or valid header/footer
with incomplete body may register executable garbage. Writing magic last after
full image verification helps programming interruption, but does not establish
the contents of a sector during an interrupted erase. A safe resumable installer
must address every scanner-visible intermediate state and callback ordering.

## Manager and neotools

The manufacturer's [AlphaSmart Manager 2 manual](https://www.daneel.franken.de/alphasmart.neo/ALSMUserManual.pdf),
printed p.34, documents choosing a set to keep/install and deleting SmartApplets
outside that list. Disabling an applet does not remove its allocation. The
manual does not establish an explicit force-compaction command or a guarantee
that the logical install-list order equals physical flash order. Selecting only
FileManager is a plausible GUI workflow to investigate, not a qualified way to
ensure first physical placement. Existing deleted headers can retain extents.

Current local neotools source (`neotools/neotools/applet/manager.py`) uses the
firmware applet abstraction: request 06 begins append installation, 02 uploads
a buffer, 0B programs it, and 07 finalizes it. No argument supplies a destination
flash address. `--force` removes an existing same-ID applet and installs the new
image; it is not an overwrite-in-place option. The CLI explicitly notes that
individual removal does not free space. `applets remove-all` uses command 11,
which erases the applet area; installing FileManager immediately afterward is
the controlled first-slot setup route.

Thus a normal neotools upgrade does not guarantee preservation of the first
physical location. A backup/rebuild/restore workflow, or a small immutable boot
component with updateable implementation elsewhere, is required. A new targeted
writer/maintenance protocol would be additional functionality, not something
current neotools already exposes. Low-level firmware segment-update commands
are separate and not a qualified general block-writing interface.
