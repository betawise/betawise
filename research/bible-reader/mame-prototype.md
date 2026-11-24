# Native Neo Bible Reader prototype: MAME speed results

2026-11-20. Built [BibleReader](prototype/README.md), embedding
the entire 948,662-byte previous-token/arithmetic-coded KJV resource. Ran it
against private Neo 3.21 firmware in disposable MAME flash/RAM sessions.

**Conclusion: the format is usable for a prototype with a seek index. Do not
use chapter-start decoding for arbitrary verse jumps.** Next-page rendering
takes about 0.39 seconds. Eight-verse decoder checkpoints reduce tested jumps
to roughly 0.3–1.94 seconds, including text decoding and full LCD painting.
The worst-case chapter scan tested fell from 17.33 seconds to 0.83 seconds.

## Measured device time

Times are MAME emulated elapsed time at the configured **33,161,216 Hz VZ CPU
clock**, not the host's execution time. A jump's total includes seek, page
decoding/layout and full-screen rendering. The display has a one-row reference
header and seven rows of hard-wrapped text, using the verified 44x8 font.

| Operation | Chapter-start baseline | Eight-verse checkpoints |
| --- | ---: | ---: |
| Next page within Genesis 1 | 0.392 s | 0.392 s |
| John 3:16 | 2.632 s | 1.309 s |
| Genesis 1:31 | 5.471 s | 1.742 s |
| Psalms 119:1 | 0.387 s | 0.387 s |
| Psalms 119:88 | 8.873 s | 1.018 s |
| Psalms 119:176 | **17.331 s** | **0.830 s** |
| Revelation 22:21 | 3.987 s | 0.990 s |
| Psalms 117:1 | 0.309 s | 0.309 s |
| Matthew 5:1 | 0.356 s | 0.356 s |
| Isaiah 53:5 | 1.217 s | 1.217 s |

Additional typed-reference checks on the indexed build:

| Reference | Total |
| --- | ---: |
| Matthew 22:21 | 0.863 s |
| John 3:23 | 1.347 s |
| Exodus 17:16 | 1.644 s |
| Exodus 32:32 | **1.943 s** |

Repeated John 3:16 and Psalms 119:176 jumps agreed with their first measured
times to the recorded precision. These measured references are not an exhaustive
upper bound over every verse and every possible page.

### Where the time goes

For John 3:16 with checkpoints: seek **0.926 s**, page decoding/layout **0.333 s**,
LCD paint **0.050 s**. For Psalms 119:176: seek **0.653 s**, page decoding/layout
**0.127 s**, paint **0.050 s**. For next-page reading: essentially no seek,
**0.342 s** decoding/layout and **0.050 s** paint.

The seven-row page and all 44 header cells are painted through the normal SDK
console/font renderer. Drawing is a small fraction of the time. Arithmetic
decoding, ROM dictionary lookup and software 64-bit multiplication/division
dominate. Profiling their individual shares is still needed before claiming
which individual operation is the bottleneck.

The simple conclusion is to retain the text representation for now and keep
the checkpoints. Further work can compare a 32-bit range coder or a faster
Huffman backend against this native baseline if subsecond arbitrary jumps are
required. More frequent checkpoints are another size/speed tradeoff. This
experiment does not establish that the present format is optimal.

## ROM and RAM

| Component | Bytes |
| --- | ---: |
| Compressed text, models, dictionary, original chapter records | 948,662 |
| Eight-verse state index | 62,732 |
| Reader/decoder code, navigation and SmartApplet overhead | 12,784 |
| **Complete indexed SmartApplet** | **1,024,178** |
| Original chapter-start SmartApplet | 960,860 |

The indexed applet remains **24,398 bytes below 1 MiB**, excluding the separate
NeoFontTerminal resource applet. Installed applet-space availability must be
considered separately from this image size.

The actual 68000 decoder structure is **1,524 bytes**, compared with 1,576 on
the 64-bit host ABI. The complete indexed applet's header requests **2,416 bytes
of initialized/BSS RAM**, including decoder, a 352-byte screen, UI state,
benchmark counters, GOT and SDK globals. The baseline requests 2,400 bytes.
Neither decoder nor UI uses heap allocation or a full chapter buffer.

Firmware/app stack is additional. Compiler `.su` reports for the final applet
include BibleReadByte at 80 bytes, consume at 56, target at 48 and show_page at
72 bytes per direct frame; nested calls, arithmetic helpers, firmware and
interrupts need separate accounting. No stack high-water measurement or proven
total stack upper bound is claimed. The prior rough 4-KiB decoder/reader budget
has become much more concrete, but static RAM alone is not total process RAM.

## Seek index design

The compressed stream is **unchanged**. Host-side code records the arithmetic
decoder state at the start of verses 9, 17, 25, etc. On a jump, the reader restores
the nearest checkpoint and decodes at most seven intervening verses. Sequential
page reading simply continues the live decoder state.

There are **3,220 checkpoints**, each **18 bytes**:

* arithmetic low, high and value: three uint32 values;
* symbols remaining and chapter-relative compressed byte offset: two uint16;
* bit count/padding state and current input byte: two uint8.

Newline is terminal zero in this pinned dictionary. Every saved state is exactly
after that token, so previous-symbol state and the empty word buffer are implicit.
The 16-byte `KJVSEEK1` header records group size, chapter count and point count.
Each chapter directory entry holds uint16 first-point index and verse count:
`16 + 1189*4 + 3220*18 = 62,732 bytes`.

`seek_prepare.c` builds this from the exact native decoder and validates each
saved state by restoring it and comparing its **entire remaining chapter suffix**
with a separate sequential decode. This is decoder-state replay, not an expected
screen derived from a capture. The index adds no large RAM structure.

## Validation and retained evidence

* The fixed-storage native C decoder reconstructs **all 1,189 chapters and
  4,148,450 source UTF-8 bytes** exactly, visiting chapters in reverse order.
* Every one of the **3,220 checkpoint suffixes** replays exactly on the host.
* The indexed MAME run passes **17 exact full-screen assertions**. These include
  paging, chapter starts, middle/end jumps, repeated jumps, numeric Goto input,
  and all five documented non-ASCII display conversions.
* Screen verification uses `NeoLCD.lua` raw controller RAM and flags, three
  identical samples and `neo_reader.py` exact glyph matching. Unknown/ambiguous
  glyphs fail. Every LCD controller is independently asserted on, non-reset,
  non-inverted, without all-points or scroll-origin changes.
* The harness checks cursor x=0/y=56 before calling the normal firmware hide
  API, observes its return and restores the original mode. Guest registers and
  the harness's scratch RAM are preserved around these test calls.
* No screenshot or model inference is used as a test oracle. No saved user
  session or physical device was read or modified.

Raw runs under `.research-work/bible-compression`:

* `mame-prototype-07`: passing 13-screen chapter-start baseline;
* `mame-seek-01`: passing first checkpoint benchmark;
* `mame-seek-final`: passing final 17-screen scenario;
* `native-final`: native output records and full checkpoint replay.

These retain LCD RAM/flags, decoded text, explicit source-derived expectations,
phase events, firmware counters, source/input hashes, build logs and assertion
results. The final session also retains the exact BibleReader and font applets
under `artifacts/`. Compact results are in `mame-results.json` in this research
directory. Each new run stages newly created disposable flash/RAM/configuration.

### Timing instrumentation and limitations

Read-only MAME write taps timestamp applet phase markers using emulated time:
start, verse located, page decoded and LCD painted. The running clock is recorded
from the emulated VZ PLL configuration. These phases exclude native key-delivery
latency, the chooser/boot workflow and subsequent capture stabilization time.

The first launch's earliest phases finish before the observer discovers the
applet's RAM. Its full MAME duration is therefore omitted; the 4-ms initialization
and 379-ms initial-page firmware counts are retained only as secondary data.
Later chapter-start and repeated jumps have complete MAME phase events.

The firmware millisecond counter went backwards once in the long baseline run.
That record is marked invalid. Primary conclusions use monotonic MAME emulated
time, not the suspect firmware delta. No cause or SDK fix is inferred here.
The physical Neo's flash wait states, power management and timing accuracy still
need hardware confirmation; these results establish the behavior in this MAME
configuration.

During the initial port, GCC folded nominal bytewise big-endian readers into
unaligned 68000 word/long loads. Odd offsets inside the compact container caused
address faults. Explicit volatile byte reads fix this without changing the data.
The passing native and MAME tests use those reads. Initial failed harness/port
captures are retained separately and are not included as passing measurements.

See [the applet README](prototype/README.md#verification-and-prior-experiments)
for build, run and offline verification commands. No common SDK or emulator
source was changed, so the new applet-specific tests were used rather than
rerunning unrelated REPL/Logo acceptance cases.
