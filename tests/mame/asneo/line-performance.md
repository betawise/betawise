# Neo line drawing: algorithm and measured cost

DrawLine uses run-length-slice Bresenham: quotient/remainder are computed once,
then the minor axis advances once per span. Interior span lengths are the
quotient or quotient+1; the endpoint spans are partial. Directional half-way
ties preserve the former pixel-at-a-time implementation exactly. This avoids
counting every pixel before emitting a horizontal/vertical run.

The established technique is described in Michael Abrash's
[run-length-slice discussion](https://www.phatcode.net/res/224/files/html/ch36/36-02.html).
The implementation here retains the SDK's endpoint/tie convention. On the
68000, 16-bit deltas/quotient/remainder compile to a single DIVU.W; signed
coordinate advances use addition/subtraction rather than software multiply.
All slopes share one drawing loop. Axes and points start with a complete span;
diagonals start with quotient 1 and remainder 0. Both avoid division.

## Native-ROM measurement

Measured 2026-11-24 using real Neo 3.21 RasterOp calls in the local emulator,
not a host RasterOp stub. Original source baseline is
`b8c5e945749b27f9eb40d4f1987f325089bce339`. The RAM probe is compiled for the
68000 at -Os. Emulated machine time is sampled at volatile marker writes around
ten repetitions; interrupts are masked, and clearing is outside the measured
region. Both versions include the same small loop/marker overhead. These are
emulator measurements, not physical-device or complete-app performance claims.

| Line case | Original µs/line | Run-sliced µs/line | Speedup |
| --- | ---: | ---: | ---: |
| horizontal | 14597.38 | 1524.40 | 9.58× |
| vertical | 3589.40 | 174.99 | 20.51× |
| shallow | 14597.75 | 1582.30 | 9.23× |
| steep | 3578.25 | 219.50 | 16.30× |
| moderate | 14641.89 | 4640.93 | 3.15× |
| diagonal | 3592.78 | 3521.13 | 1.02× |
| short diagonal | 130.85 | 132.78 | 0.99× |
| short shallow | 242.90 | 150.45 | 1.61× |

The benchmark records source/ROM/emulator identities, flags, exact coordinates
and timings in its disposable output. Results change with the implementation,
compiler or firmware/model; rerun rather than treating this table as a timing
acceptance threshold.

## Reproduce and verify

From the workspace root, with the ordinary m68k compiler, original private ROMs
and the matching Neo emulator installed:

```sh
python3 betawise/tests/mame/asneo/benchmark-lines.py --output /tmp/line-benchmark-new
python3 betawise/tests/mame/asneo/test_graphics.py
python3 betawise/tests/mame/asneo/check-repl.py --case logo-graphics \
  --output /tmp/line-graphics-new
```

The host suite compares 75,517 lines against independently rounded geometry,
including every panel slope/all octants, directional ties, translated endpoints,
points, maximal call counts, and erasing without touching surrounding pixels.
The native Logo regression compares the complete graphics pane against authored
geometry/references using raw LCD RAM. It does not infer results from screenshots.
Logs, captures, binaries and raw timing streams are generated in the new output,
not committed alongside this summary. Run one emulator at a time.

## Types and module boundary

DrawLine requires on-screen endpoints (Neo x=0..263, y=0..64) and does not
clip. Coordinates, deltas, advances, counts and errors use int16_t. Major is at
most 263, minor at most 64, and the inclusive count at most 264. The doubled
error calculation comfortably fits int16_t. Supporting arbitrary uint16_t
coordinates is unnecessary for this display helper.

The GCC ABI uses 32-bit int, so small operands still promote. Unsigned 16-bit
casts only at division/modulo preserve one native DIVU.W; signed int16_t
operands alone generated __divsi3 and __modsi3 helpers with this compiler.

32-bit arithmetic is native but not always equally fast on the original 68000.
For example, ADDQ to a data register takes 4 clocks for word versus 8 for long;
TST takes 4 for either. See the manufacturer's
[68000 timing tables, chapter 8](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf).
Small C types also undergo integer promotion, so inspect generated code rather
than assuming each uint16_t expression becomes word arithmetic.

Abrash's [reference C implementation](https://www.phatcode.net/res/224/files/html/ch36/36-03.html)
uses the same quotient/remainder, doubled error increments and partial endpoint
runs. It has separate axis/diagonal paths and duplicated major-axis loops;
ours shares the drawing loop and preserves the previous directional halfway
rule instead of sorting endpoints. Its direct VGA writes are not a comparable
rendering cost to Neo ROM RasterOp calls.

`os3k_display_gfx.c` implements geometry in the existing `os3k_display.h` API;
`os3k_display.c` owns font/cursor/text state. A separate `os3k_graphics.h` would
be justified by a distinct graphics API (surfaces, clipping, shapes), rather than
just these two existing display helpers. The prefixed implementation filename
expresses this current boundary without moving public declarations.

### TI-89/M68K comparison

Reviewed Olivier Armand/Lionel Debroux's ExtGraph
[FastDrawLine_R.s](https://github.com/debrouxl/ExtGraph/blob/experimental/src/lib/Line/FastDrawLine_R.s)
(experimental branch, retrieved 2026-11-24). This is bidirectional pixel-at-a-time
Bresenham, not run-length-slice: it plots both ends toward the center, updates a
word-sized error and uses DBF. It directly modifies packed bitmap bytes, rotates
pixel masks, assumes a 30-byte scanline, and patches its instruction stream for
mode/direction. It has no division. Its narrow arithmetic fits calculator-sized
coordinates, not arbitrary uint16 endpoints. These choices reduce per-pixel
cost on that framebuffer; Neo's expensive ROM calls make reducing call count
more useful here. This source is an architectural comparison, not a measured
cross-device speed comparison or evidence of a TI run-slice implementation.

Reviewed source SHA256: `32c4e69fd8dd22c2a2f846f0a94f53bdac27be1968f42cfd86970367ec278e05`.
The published run-slice comparison above is Abrash's implementation; no verified
TI-89 run-slice implementation was found in this review.

## Signed 16-bit versus previous 32-bit working variables

Measured with the same probe, compiler and eight cases above. The baseline uses
32-bit signed x/y, sx/sy, remaining/run and error, and uint16_t deltas,
major/minor, quotient/remainder. The current version uses int16_t for all of
these, with unsigned casts at division/modulo. Public parameter types remain
uint16_t. Results are emulated µs/line:

| Case | Previous 32-bit | Signed 16-bit | Reduction |
| --- | ---: | ---: | ---: |
| horizontal | 1526.45 | 1524.40 | 0.13% |
| vertical | 176.56 | 174.99 | 0.89% |
| shallow | 1585.38 | 1582.30 | 0.19% |
| steep | 221.37 | 219.50 | 0.84% |
| moderate | 4757.39 | 4640.93 | 2.45% |
| diagonal | 3635.30 | 3521.13 | 3.14% |
| short diagonal | 136.58 | 132.78 | 2.78% |
| short shallow | 153.52 | 150.45 | 2.00% |

To reproduce this type comparison from the current source, generate a wide
baseline, then pass it to the benchmark (all files are disposable):

```sh
python3 - <<'PYTHON'
from pathlib import Path
s = Path('betawise/os3k/os3k_display_gfx.c').read_text()
for name in ('x', 'sx', 'sy', 'remaining', 'run', 'error'):
    s = s.replace('int16_t ' + name + ' =', 'int32_t ' + name + ' =')
for name in ('dx', 'dy', 'major', 'minor', 'whole'):
    s = s.replace('int16_t ' + name + ' =', 'uint16_t ' + name + ' =')
s = s.replace('(uint16_t)major', 'major').replace('(uint16_t)minor', 'minor')
s = s.replace('if (error >= 2 * minor)', 'if ((uint32_t)error >= 2 * minor)')
Path('/tmp/line-wide.c').write_text(s)
PYTHON
python3 betawise/tests/mame/asneo/benchmark-lines.py \
  --baseline-source /tmp/line-wide.c --output /tmp/line-types-new
```

This reconstructs the baseline variable types, not its original comments or
source hash. The report records both exact source hashes. Run the native Logo
regression separately, after the benchmark exits.
