# Research notes

Investigations, evidence, and reproducible probes for Betawise and AlphaSmart firmware.

[Reproduction and source-baseline policy](REPRODUCIBILITY.md) explains retained
evidence, private input dependencies and disposable output locations.

- [Runtime allocation and scratch-memory re-audit](memory-allocation/README.md):
  56-image vendor census, original scratch allocator execution on three ROMs,
  and limits of shared transport buffers versus independently owned RAM.

- [Markdown editing and viewing](markdown/README.md): live formatting prototypes,
  fonts, AlphaWord integration, standalone editor options and export considerations.

- [Device-side USB protocol](usb/README.md): Manager read/write packets,
  AlphaWord Send callbacks, file selectors and structures, and offline capture audits.

- [Syscall investigations](syscalls/README.md): subsystem findings, unresolved
  questions, test sources, captured results, and historical probes.
- [OS3K / GCC ABI audit](abi-audit/README.md): cross-subsystem calling
  conventions, pointer-return remediation, firmware inventory, and maintained
  integration runner.
- [NEO Manager 3.9.3 and Wireless Server](wireless-server/README.md): extracted
  firmware/app inventory, receiver update package, SDTP/markup and USB HID leads.
- [Control Panel comparison](control-panel/README.md): hidden diagnostics gate,
  wireless security and LCD trim callers, controller RAM test, and profile usage.
- [Character repertoire comparison](syscalls/localization/README.md): syscall
  #91 and the AS3000 3.01/Neo glyph comparison.
- [Dormant firmware multi-user mode](multi-user/README.md): named profiles,
  AS3000 runtime qualification, fourth-profile creation failure, and AlphaWord
  cross-profile document reopening. Not recommended for exposure.

- [Applet installation and warm registration](applet-installation/README.md):
  AS3000 3.01 Manager finalization, directory registration, and
  file-preservation experiments.

- [MicroPython port](micropython/README.md): build instructions, REPL
  implementation, profile constraints, firmware tests, and time-porting work.

- [UCBLogo port](ucblogo/README.md): build instructions, OS3K backend, emulator
  tests, and memory measurements.

- [Dictionary and Thesaurus services](dictionaries/README.md): packed message
  contracts, native API probes, synonyms/antonyms, CW blob replies, SpellCheck
  selector correction and rhyming-dictionary feasibility.
