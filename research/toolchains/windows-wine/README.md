# Windows m68k GCC compatibility experiment (2026-11-20)

MinGW m68k-elf GCC 13.1.0, Tranaptic-2023/06/16-13:17:25, was tested
under Wine 11.0 with a fresh 32-bit prefix, against SDK commit
`f23b40d2bf6be3bc6eabbfea9edbc714a8b2624a`.
SDK, HelloWorld, DebugTool, FileManager, three terminal variants, QEMU startup,
18 ABI bridges, setjmp at three optimization levels and compiler arithmetic
passed. MicroPython failed with an internal compiler error in `gc_setup_area`;
UCBLogo failed on newlib standard-stream macros. This does not certify native
Windows. `results.json` retains build results and limitations; the reproducible diagnostics are summarized below. Generated logs and the old
workspace-specific environment dump are not retained.

## Reproduce

Use Linux with Wine 11.0 (32-bit support), Make, Python 3, qemu-m68k, and the
normal SDK build prerequisites. Obtain `MinGW-m68k-elf-13.1.0.zip` from
<https://sourceforge.net/projects/mingw-gcc-68k-elf/>. Its SHA256 must be
`ed6d151b7f02070048a464b578681d41182923dfa65f2a69a2edeccd691da0e6`.
The archive and extracted compiler are replaceable dependencies.

Run from the AlphaSmart workspace root. Keep all generated outputs isolated:

```sh
mkdir -p .research-work/windows-toolchain-test
cd .research-work/windows-toolchain-test
# Put the verified archive here and extract its compiler tree into toolchain/.
unzip MinGW-m68k-elf-13.1.0.zip
# If extraction creates a version-named parent, rename that directory toolchain.
# toolchain/bin/m68k-elf-gcc.exe must exist before continuing.
git clone --no-hardlinks ../../betawise source
git -C source checkout f23b40d2bf6be3bc6eabbfea9edbc714a8b2624a
git -C source submodule update --init --recursive
mkdir -p wrappers logs tmp
cp ../../betawise/research/toolchains/windows-wine/wrappers/* wrappers/
# Wrappers locate the sibling toolchain directory without a fixed home path.
export WINEARCH=win32
export WINEPREFIX="$PWD/wine32"
export TMPDIR="$PWD/tmp"
export WINEPATH="$(winepath -w "$PWD/toolchain/bin")"
export CROSS_COMPILE="$PWD/wrappers/m68k-elf-"
export QEMU_M68K="$PWD/wrappers/qemu-windows-output"
wineboot -u
cd source
make -C os3k -j4 > ../logs/sdk-build.log 2>&1
make -C applets/HelloWorld > ../logs/hello-build.log 2>&1
make -C tests/qemu check > ../logs/qemu-check.log 2>&1
os3k/compiler-rt/check.sh > ../logs/arithmetic-check.log 2>&1
make -C applets -j4 > ../logs/applets-build.log 2>&1
make -C applets/UCBLogo > ../logs/logo-build.log 2>&1
```

Fresh builds are required: Wine writes Windows drive-letter paths into `.d`
files that Linux Make cannot read on an incremental retry. The QEMU wrapper
adds the execute bit to Windows-produced ELF files. Compiler DLL lookup needs
WINEPATH. Expect the two documented applet failures; compare diagnostics,
pass/fail results rather than incidental Wine log addresses.
No rerun was performed during disk cleanup.

## Notable diagnostics

MicroPython failed in `upstream/py/gc.c`, `gc_setup_area`, during RTL expansion
with GCC reporting an internal compiler error/segmentation fault. UCBLogo
failed where newlib `stdin`, `stdout` and `stderr` macros expanded in its
`FILE *` declarations. DLL lookup and Linux execution permissions required the
WINEPATH and QEMU-wrapper adaptations above. Incremental retries hit Windows
drive-letter dependency paths. Regenerate logs with the redirected commands;
compare these outcomes and results.json, not transient Wine addresses.
