# OS3K ABI/syscall results and reproduction

This preserves the findings, input identities, complete final coverage table
and reproducible sources from the retired `os3k-clean` experiment. Generated
MAME logs, RAM/NVRAM images, repeated listings and deletion inventories are not
repository inputs.

## Notable results

The final 2026-11-19 run observed 264/264 defined syscalls, including 219/219
populated AS3000 3.01 entries and 264/264 Neo 3.21 entries. All 21 empty slots
were checked statically. Neo 3.01 was table/hash checked, not live-tested by
the complete runner. QEMU adapter/startup and public-API documentation checks
passed. The compact totals are in coverage-summary.json; coverage.tsv records
the slot-to-suite mapping. Its log paths describe generated output locations.

The parent ABI audit documents eighteen D0-to-A0 pointer bridges, two already
compatible pointer services, six hidden-A1 aggregate returns, and unsupported
ROM `ll` formatting. Dispatch coverage plus directed assertions does not prove
every branch, firmware version, physical peripheral, installation workflow or
callback lifetime. Earlier shifted LCD captures belong to the old emulator
model, rather than being a firmware defect or a later-binary result.

## Reproduce

Use the research source commit and support overlay described in
[the common reproduction guide](../../REPRODUCIBILITY.md). The durable parent
anchor is `b8c5e945749b27f9eb40d4f1987f325089bce339`; the research sources are
in the consolidation commit, not in that parent alone. Main-ROM identities and
tables are in [the canonical inventory](../rom-inventory.json).

Dependencies include Python 3, Make, host C/C++, QEMU m68k, Debian
m68k-linux-gnu GCC 12.2.0-13/binutils 2.40, Doxygen 1.9.4 and MAME build
prerequisites. The recorded MAME fork revision is
`53bcc26e4e5a6300a8742cffdc215290f3224a37` plus mame-working-tree.patch.
In a separate fresh sibling MAME checkout, apply that overlay and build:

```sh
make -C mame -j2 SUBTARGET=asma3k SOURCES=src/mame/skeleton/alphasma3k.cpp
make -C mame -j2 SUBTARGET=neodiag SOURCES=src/mame/skeleton/alphasneo.cpp
# Only in the fresh checkout where this executable name does not exist:
ln -s asma3k mame/mame
python3 betawise/research/syscalls/coverage/run.py /tmp/os3k-validation-new
```

Supply original private boot/applet ROMs at their inventory paths; never reuse
a user's saved NVRAM. The gate rebuilds SDK/probes, runs suites sequentially,
checks ROM hashes/tables and produces fresh logs, summary.json and coverage.tsv.
A directory with stale MAME logs is rejected. See the
[maintained coverage guide](../../syscalls/coverage/README.md) for group limits.

All 38 old objdump listings were reproducible from their hashed inputs;
disassembly-recipes.json preserves exact options, including historical load
bases that must not be mistaken for the current ROM map. Regenerate with:

```sh
python3 betawise/research/abi-audit/os3k-clean-20261124/regenerate-disassembly.py \
  --output /tmp/os3k-disassembly-new
```

The old system3.bin was a byte-identical AS3000 main-ROM copy. The old manual
text is regenerated with pdftotext from the private Neo 2 user manual named in
provenance.json. Neither duplicate belongs in this source snapshot. Source and
input provenance is retained; repetitive raw output is deliberately regenerated.
