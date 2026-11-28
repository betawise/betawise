# Clang/LLVM M68k initial assessment

Research date: 2026-11-27. This records a completed, subsequently removed
Clang experiment. Production makefiles remain on GCC; this note does not
qualify a Clang toolchain for Neo firmware.

## Baseline and scope

The detached experiment used committed Betawise `c5629029f0d2ce7cb902c36ca3d3eea7777e5d2d`,
without copying concurrent uncommitted work. Compilers were Debian GCC
12.2.0-13 and Clang/LLVM 14.0.6. GNU M68k binutils assembled the output.
Both static builds used CPU 68000, `-Os -fomit-frame-pointer -fshort-enums`,
function/data sections, disabled fortify, and reserved A5. GCC separate-data
used `-msep-data`; Clang does not support that option.

## Measured HelloWorld code size

Sizes are raw object `.text.ProcessMessage` bytes, excluding header, footer,
string, runtime, GOT allocation, and our existing GCC link-time rewrites.
They are not final applet ROM measurements or cycle benchmarks.

| Variant | Bytes |
| --- | ---: |
| GCC static | 54 |
| GCC separate-data/GOT | 58 |
| GCC PC-relative | 54 |
| Clang static through GNU assembler | 76 |
| Clang static with three calls rewritten to `bsr.w` | 70 |

GCC uses compact `clr.l` and `moveq` sequences, a short conditional branch,
and a final tail call reusing incoming argument slots. Clang allocates a
12-byte outgoing-call area, uses larger immediates, and returns after its
last call. LLVM's direct object emitter produced 74 bytes: two bytes of the
76-byte result come from the assembly/GNU-as conditional-branch path.
This small example does not establish a general compiler ranking.

## Machine IR and rewriting probes

LLVM 14 successfully stopped at `finalize-isel`, `virtregrewriter`, and
`prologepilog`. A saved MIR file resumed through
`llc -O2 -verify-machineinstrs -start-after=prologepilog` into assembly.
MIR exposes CFG successors, virtual/physical register operands, memory
references, call-preserved mask `csr_std`, and dead/killed CCR annotations.

Observed transformations:

- Assembly `jsr Symbol` to `bsr.w Symbol` saved two bytes per call and emitted
  `R_68K_PC16`. No scratch register or CCR save is needed for this substitution.
  Final placement must prove signed-16-bit reach and a fixed target within
  the same relocated ROM image.
- MIR `CALLb @Symbol` to `CALLq @Symbol` emitted four-byte
  `jsr (Symbol,pc)`, not BSR, and passed the machine verifier.
- MIR pointer loads through A5 offsets 0/4/8 followed by `CALLj` through A0
  verified and assembled after declaring A5 live-in in the relevant blocks.
  This used a manually constructed function-pointer table, not automatic GOT
  allocation or linker integration.
- A separate volatile-global fixture was changed to `LEA32p 16,$a5` and
  `MOV32rp 16,$a5`. It verified and assembled as A5-relative data access.
  Offset 16 was assigned manually; automatic RAM symbol classification and
  offset resolution were not implemented.
- Stock static and PIC global-address probes still used PC-relative data
  references; PIC calls used PLT relocations. Neither supplies OS3K's split
  ROM/RAM relocation model automatically.

MIR annotations are not sufficient hardware flag proofs. LLVM 14 marks some
operations as CCR-defining although their emitted MOVEA/ADDA/SUBA forms
preserve flags, and CCR is represented collectively rather than as independent
X/N/Z/V/C proofs. Preserve independent instruction-level flag checks. Any
persistent machine pass must update liveness, memory operands and analyses.
Serialized MIR is release-specific, not a stable interchange contract.

## Validation and build limitations

Six variants passed a standalone `qemu-m68k -cpu m68000` harness: GCC static,
GCC PCREL, Clang static, assembly BSR rewrites, MIR PCREL calls, and MIR A5-table
calls. Each exited zero. Checks covered status clearing, no calls for a
nonmatching message, three calls for focus, cursor-mode argument, and centered
string arguments/content. These are limited compiler checks, not full ABI or
Neo acceptance tests. The A5 data probe was verifier/assembly-tested only.
No Neo screens, model inference or saved user sessions were involved.

The full Clang 14 SDK/runtime build failed on multiword-shift instruction
selection (`srl_parts`/`shl_parts`) and some generated CCR reads rejected by
GNU as for 68000. Existing inline assembly required GNU as because LLVM 14's
assembler rejected parts of its syntax. The experiment used static non-PIC
code with A5 reserved; OS3KApp packaging was blocked because correct split
ROM/RAM address lowering was absent.

## Newer LLVM: follow-up warranted

Do not extrapolate the LLVM 14 result to current releases. Upstream has active
M68k work relevant to these findings:

- [MOVEQ support, 2024](https://lists.llvm.org/pipermail/all-commits/Week-of-Mon-20240429/159037.html).
- [Additional immediate-load optimizations, August 2024](https://lists.llvm.org/pipermail/llvm-commits/Week-of-Mon-20240826/1440179.html).
- [CLR implementation recorded in August 2026](https://chromium.googlesource.com/emscripten-releases/+/be39f6e2eedc5d69954fa9a9c75d41a552a2ce2d).
- [MOVEM/PHI machine-verifier fixes, August 2026](https://llvm.googlesource.com/llvm-project/llvm/+/3d1f432289b654625bf9c5f3759135a189ed1d39%5E%21/).
- [CCR preservation design/performance issue](https://github.com/llvm/llvm-project/issues/213564).

These are upstream changes, not locally measured improvements. Check exact
release inclusion, especially for changes after a release branch. Rerun
HelloWorld, failing runtime sources and MIR probes on a recent pinned release
before investing in a custom LLVM pass. Keep GCC as the working baseline.
LLVM's structured machine representation looks useful for A5 lowering and
scratch allocation; final address/range decisions still need linker/loader
integration. See the [LLVM 14 MIR reference](https://releases.llvm.org/14.0.0/docs/MIRLangRef.html).

## Cleanup

At the user's request, the detached Clang worktree, modified experimental
makefiles, generated objects/assembly/MIR, harness, logs and Clang crash
reproducers were deleted. This note preserves the findings, not a retained
reproduction bundle. No production compiler change was adopted.
