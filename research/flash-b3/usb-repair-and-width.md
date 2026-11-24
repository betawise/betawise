# Flash bus width and USB repair boundaries

Read-only source/datasheet inspection and disposable NEO13 control-flow probes,
2026-11-20. No physical programming or erasure and no successful USB reflash
are claimed.

## Part capabilities versus board wiring

| Family | Byte-wide parts (x8) | Word-capable counterparts |
|---|---|---|
| AMD | Am29LV004B, Am29LV008B | Am29LV800B: x8/x16 |
| ST | M29W004, M29W008 | M29W800A: x8/x16 |
| Fujitsu | MBM29LV004, MBM29LV008 | MBM29LV800: x8/x16 |
| Micron | MT28F008B3 | MT28F800B3: x8/x16 |
| Intel Advanced Boot Block B3 | 28F008B3 | 28F800B3: x16 |
| Older Intel SmartVoltage | 28F008BV/BE | 28F800BV/CV/CE: x8/x16 |

These are device capabilities from the manufacturer documents linked in the
[device catalog](updater-chip-geometries.md), not a measurement of fitted-chip
wiring or active mode. A CPU MOVE.W/MOVE.L does not establish the flash's
programming width, command atomicity, or even a single external bus operation.

## USB is a transport, not a raw flash programmer

`neotools/neotools/message.py` names block-upload command 02, program-buffer
command 0B, clear-segment-map 16, erase-segment 17 and SmallROM-updater request
18. Block upload alone does not select an arbitrary flash address. Firmware
protocol state, current destination, segment descriptors, chip command support
and protection determine what is programmed.

In NEO13 SmallROM the packet handler at 401A80 dispatches command 17 to 401C24.
That path records up to four destination/length segments and invokes RAM erase
wrapper 4022B8. Command 0B at 401DB4 programs buffers through RAM wrapper 402262
and advances through the configured segments. The observed handler supports
addressed firmware segments, rather than just normal applet append. This is not
a complete range-validation audit or proof that every physical block is writable.

The current neotools installer explicitly rejects non-applet ROM images before
transfer, stating ROM installation is untried. Vendor Manager's ability to update
SmallROM does not prove the currently executing SmallROM updater can erase and
rewrite its own executing sector. The inspected small worker wrappers return
to SmallROM after programming/erasing; self-update needs a separately verified
RAM-resident or full-ROM-resident orchestration path. Merely finding RAM flash
workers does not establish that complete path.

## Failure of a handoff address versus failure of updater code

The candidate patches alter only the operand of the final normal-system JSR,
not the reset vector, key scanner, password routine, protocol handler or flash
workers. In NEO13 the manual recovery decision precedes that JSR: 401252 checks
the service chord, 40125A calls the password routine, and accepted entry calls
40148E then 401730 before the normal path can reach 40143E. This is a static
reason for recoverability if only the intended operand becomes invalid.

The service chord decoded from the native key checks is Right Shift + Comma +
Period + Slash; the password scan-code array spells ERNIE. The familiar Left
Shift + Tab is not sufficient in these fixtures: both the stock and broken
handoff cases still took the normal handoff. Do not confuse normal firmware
updater mode with SmallROM's independent recovery path.

A deliberately unusable normal handoff can prevent normal boot while leaving
these earlier instructions unchanged. Reaching SmallROM recovery and completing
a USB repair are separate acceptance criteria. Physical brownout behavior and
whether an interrupted program affects only the expected byte/word still need
the actual chip contract. General NOR interrupted-operation guidance does not
justify an unconditional no-brick guarantee.

See `recovery-hook/fallback/` for the fixture runner. It uses a copy of a stock
fixture from `recovery-hook/run.py`, never saved user NVRAM. These tests observe
CPU/memory control flow, not UI text, and do not exercise USB transport or erase
any sector.

## Executed fallback observations and present limit

On disposable NEO13 images, both stock and a handoff changed to the unusable
405F98 target reached the original SmallROM service-password routine when the
service chord was held. The broken target without successful forced entry
prevented normal boot (sampled PC 0008E698). This supports independence of the
password gate from the modified handoff operand.

The automated password-entry attempts did NOT establish arrival in updater
entry 401730 or USB setup 402EC4. Longer attempts also failed to establish those
endpoints. These are incomplete/inconclusive fallback tests, not repair PASSes.
A changed operand being outside those routines does not prove that physical
power failure leaves all required bytes reliable, nor that a self-reflash can
complete. The release gate remains an end-to-end demonstration: deliberately
unusable handoff, manual SmallROM entry, real USB dialogue, restoration of the
original image through the vendor-supported path, and normal subsequent boot.
Repeat for each supported model/revision before relying on this as a no-brick
installation strategy. No erase/program commands were sent by these probes.

## Address-based access versus object-based access (2026-11-21)

The neotools protocol notes suggest addressed **flash update** operations, not
a general-purpose memory debugger. In `message.py`, 02 is a length/checksum
buffer upload (not an address), 0B programs the current destination, 16 clears
the segment map and 17 configures/erases a firmware segment. SmallROM dispatch
at 401C24 records a host-supplied 32-bit segment base and a 16-bit length scaled
by 1024 before invoking the erase worker. That is an address-based capability
below applet installation, although actual allowed ranges, chip support and
safe self-update remain to be qualified. Current normal-firmware notes report
8F for 16/17; they are updater-mode commands, not normal applet operations.

Documented 0F/10 reads operate on a selected applet/read cursor; 12 and 1C read
files (1C means native/raw file representation). They do not establish arbitrary
physical-address reads. Fetching applet ID zero can obtain a firmware image,
not a whole-RAM or necessarily whole-chip dump. 01/03 remain unknown and were
reported to return 8F; their presence is not evidence of memory peek/poke.
The separate one-byte protocol hello 01 in device.py is a framing-level command,
not the eight-byte packet command 01. No implemented generic READ_MEMORY or
WRITE_RAM operation was found in the local neotools code/documentation.

A custom neotools maintenance command could therefore potentially drive the
existing flash-segment backend without replacing the whole device protocol.
That would require updater entry, full range/geometry checks, backups and an
executed transfer/repair test. It is not available merely by adding a CLI
address argument to the existing applet installer. All such USB accesses remain
firmware-executed; USB itself does not provide bus-master access to CPU memory.

If independent recovery becomes qualified, moving FileManager first and doing
compaction on-device is a coherent architecture. Recovery must run before the
vendor scanner encounters torn headers, and must not depend on FileManager's
current registration, A5 state or a source block already erased by relocation.
After migration, keep the recovery-critical first prefix outside recyclable
blocks; journal transactions with a spare block and preserve a committed source
until its replacement verifies. Bootstrap installation and updates remain separate
transactions. This is a design direction, not an implemented migration engine.
