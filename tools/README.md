# Stock m68k build adapters

The build uses stock GCC/binutils. Normal `make` automatically
records GOT references, evaluates a bounded set of object orders, and packages
the selected image using one discovery link and one checked final link.
No GCC or binutils patches are required.

ELF inspection uses the `pyelftools` Python API (not parsed `readelf`/`nm`
output). Install `python3-pyelftools` on Debian/Ubuntu, or `python3 -m pip
install pyelftools` in your Python build environment. The shared reader requires
big-endian m68k ELF32 and explicit-addend relocations; GNU ld still applies
relocations and validates the final link. Linker map/`--cref` parsing remains
necessary to check archive symbol providers.

## Build controls

- `make`: automatic fixups, internal order evaluation, and single-stage packaging.
- `make OS3K_INTERNAL_ORDERS=0`: previous fixed-layout iterative GOT fixups and
  two relocation-table sizing stages, useful for debugging.
- `make OS3K_FIXUPS=0`: ordinary compiler/linker output without the adapters.
  `RELATIVE_CALLS=0` remains a compatibility alias.
- `OS3K_PACKAGE_SOLVER=0`: retain the old packaging stages independently.
- `OS3K_ORDER_SEED=path.json`: optionally include a saved object-order candidate.
  No seed is required by the default build.
- `CROSS_COMPILE=...`: select another compatible m68k tool prefix.

Compiler-mode stamps rebuild objects when fixup mode, adapter source, or the
cross prefix changes. Link-mode stamps track layout and packaging settings.
Unchanged builds do not relink. `ORDER_ASM_CACHE=directory` optionally caches
reassembly using the compiler identity, working directory, original object
hash, and rendered assembly.

Automatic ordering applies only to the supplied OS3K linker templates. Custom
linker scripts retain their layout. Explicit `OBJECT_ORDER` remains available
for existing experiment commands.

## Fixups and fallback

The compiler adapter retains original GOT assembly and objects, with records
keyed by object-content hash. Each link operates on private object/archive
copies. Original command input and archive member order are preserved, so
placement changes do not change archive resolution.

Eligible transformations are:

- Adjacent GOT-load/indirect-call pairs become `BSR.W`.
- RAM addresses become A5-relative address formation.
- ROM addresses in the same output section become PC-relative address formation.
- Address-register destinations use `LEA`. Other destinations use `PEA` and
  `MOVE.L (SP)+,destination`. Direct pushes use `PEA` and `TST.L (SP)` to preserve
  the original MOVE condition flags. General transfers need four transient
  stack bytes and can add two instruction bytes.

Large MicroPython and Logo heaps follow ordinary globals in `.os3k.heap`.
Remaining GOT slots hold full 32-bit addresses and use short A5 displacements.
An object modified after compilation, such as MicroPython's renamed printf.o,
is conservatively skipped when its content hash no longer matches a record.

The discovery ELF supplies exact symbol indices, selected input groups, and
relocations. Python evaluates input/reverse/graph orders and an optional seed,
ranking estimated RAM first, then ROM, with deterministic tie-breaking. The
model approximates alignment and assembler relaxation and uses a 128-byte range
guard; it is not a complete linker or a guarantee of globally optimal placement.

Only the chosen order is assembled and linked. A normal checked GNU ld link,
signed-displacement validation, callable alignment checks, and symbol-provider
comparison must pass. A failed prediction returns to the established iterative
adapter, which restores all overflowing sites together. Its bounded safety cap
can restore all original GOT sequences.

## Packaging

Initialized-data relocation count is taken from the discovery ELF. The selected
final link reserves that exact count. Packaging then recomputes the final RAM
offsets, verifies the count, writes the big-endian zero-terminated table, and
extracts the flat image. A changed count uses the established sizing retry.
Successful modeled builds use two linker calls total; fallback can use more.

Per-image `.elf.calls.json`, `.elf.order.json`, and `.elf.package.json` files
record choices, validation, and actual linker-call counts.

Fonts use the common script and packaging. Their direct C entry bypasses CRT;
`-mpcrel` compilation and linker assertions forbid GOT/implicit initialization.
Descriptors are filled on demand, including before MSG_INIT. Descriptor RAM is
16 or 80 bytes. The common format retains a four-byte unused table terminator.

## Validation

The optimizer is exercised by the m68k relocation tests and deterministic Neo
regressions. Font execution tests cover all shipping faces at two ROM/RAM
placements, dirty descriptor RAM and getters before MSG_INIT.

The prototype comparison covered all four MicroPython variants, UCBLogo,
BibleWise, HelloWorld, DebugTool, FileManager and all 19 fonts. The bounded
candidate set saved 164 more RAM bytes and cost 34 ROM bytes against the saved
per-applet bests. Those numbers describe the historical experiment; source
changes and toolchains can change the selected layout and resulting sizes.
