# Reader ROM and maintenance costs

These are pre-prefix-search snapshots. Current search-option costs and the
shared prefix matcher are measured in [prefix-search.md](prefix-search.md).

The previous whole-applet ROM column hid the architectural difference behind
roughly 1.31 MB of identical Bible data. It also included an unnecessarily
dense native superscript font. Current figures below use the compact font.

## Comparable application cost

**App ROM** includes code, app headers/relocations/initialized data, UI strings
and bundled UI/font assets. It excludes **1,311,826 bytes** shared by every
variant: compressed text, dictionaries/Huffman/grammar tables, search index,
pruning/verse-count tables, and generated book metadata. These choices do not
change compression. **Executable** is the retained input `.text` sections in
the final linker map, including linked SDK/syscall/stdlib code, excluding data.
KiB means 1,024 bytes.

| Reader | App ROM KiB | Executable KiB | Superscript KiB | A5 bytes | C tokens | Functions | CC sum / max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Native, original wrapper | 19.71 | 13.05 | 3.50 | 3,122 | 10,164 | 58 | 523/60 |
| Native full chapter, optimized | 19.66 | 13.00 | 3.50 | 3,122 | 10,161 | 58 | 522/60 |
| Native moving window | 23.06 | 16.30 | 3.50 | 3,294 | 12,757 | 76 | 675/65 |
| Native append on demand | 22.77 | 16.02 | 3.50 | 3,282 | 12,553 | 75 | 663/65 |
| Native background completion | 22.95 | 16.19 | 3.50 | 3,290 | 12,657 | 75 | 672/74 |
| Native TextScanInsert lookahead | 23.03 | 16.27 | 3.50 | 3,546 | 12,802 | 75 | 680/74 |
| Native private viewport lookahead | 23.19 | 16.43 | 3.50 | 3,546 | 12,882 | 76 | 688/74 |
| Native prewrapped lookahead | 23.50 | 16.74 | 3.50 | 3,566 | 13,281 | 78 | 705/74 |
| Native prewrapped full chapter | 23.38 | 16.62 | 3.50 | 3,558 | 13,215 | 78 | 698/65 |
| Custom, full repaint | 20.02 | 18.77 | 0.00 | 3,862 | 14,316 | 87 | 725/57 |
| Custom, LCD roll | 20.20 | 18.98 | 0.00 | 3,834 | 14,518 | 87 | 723/57 |

The private viewport row is a research build with a known long-selection
regression; its measured ROM is not a claim of feature parity. See the
[layout investigation](native-layout-disassembly.md).

Native full-chapter uses less executable code than the custom viewer. Its
remaining assets narrow the total-ROM saving: 3,584 bytes of superscript data
and a 1,536-byte embedded terminal UI font, plus strings/headers/initial state.
The custom viewer uses the system UI font instead. The moving-window variants
add file residency, global/local offset conversion and selection export logic.

A full chapter is not stored uncompressed in ROM: it is decoded into a RAM
file. Full-chapter, on-demand and moving-window native builds therefore share
the same compressed Bible and most code. Their storage policies mainly change
RAM use and processing; the earlier full-ROM totals concealed the few-KiB
application-code difference.

## Maintenance metric definition

No single number measures maintenance effort. The table uses two repeatable
proxies rather than an invented weighted score:

* **C tokens**: lexical tokens after preprocessing the actual production flags,
  restricted to our implementation files. This measures active code volume
  without rewarding the existing dense one-line formatting. Generated assets,
  SDK headers/implementation, firmware, tests and host tools are excluded.
* **CC sum / max**: summed structural cyclomatic complexity and the largest
  function. Each function starts at 1; each `if`, `for`, `while`, `do`, `case`,
  conditional operator, `&&` and `||` adds 1. The same rule is applied to every
  variant. This counts active preprocessed definitions, before compiler dead
  code elimination. Function splitting can increase the sum while improving
  the maximum, so both are shown.

The main table includes the shared decoder/search implementations. The
following isolates the reader/frontend logic whose design is being chosen:

| Reader | Frontend tokens | Functions | Frontend CC sum / max |
|---|---:|---:|---:|
| Native, original wrapper | 5,375 | 29 | 307/60 |
| Native full chapter, optimized | 5,372 | 29 | 306/60 |
| Native moving window | 7,968 | 47 | 459/65 |
| Native append on demand | 7,764 | 46 | 447/65 |
| Native background completion | 7,868 | 46 | 456/74 |
| Native TextScanInsert lookahead | 8,013 | 46 | 464/74 |
| Native private viewport lookahead | 8,093 | 47 | 472/74 |
| Native prewrapped lookahead | 8,492 | 49 | 489/74 |
| Native prewrapped full chapter | 8,426 | 49 | 482/65 |
| Custom, full repaint | 9,211 | 56 | 498/57 |
| Custom, LCD roll | 9,413 | 56 | 496/57 |

Native full-chapter has substantially less owned reader logic. Moving-window
native still has fewer tokens/branches than the custom engine, but also has
gap/viewport/selection invariants tied to the native editor. Those integration
risks are not captured by CC. The custom engine owns wrapping/checkpoints/
selection/rendering and relies on specific cursor/font RAM state and LCD-roll
behavior. Consequently these are structural measurements, not a claim that
the lowest number is automatically the easiest design to maintain.

Counts are per configuration, not the cost of keeping all experimental variants
in the repository simultaneously. The JSON retains per-function results and
separate frontend/shared-code totals. A known two-function fixture checks
the counting rule: CC 5 each, sum 10.

## Superscript packing

The old face had null width and offset maps. `max_width=4` made all 256 code
positions fixed-width slots, even when their pixels were zero. Eight complete
height-band arrays therefore occupied **36,864 bytes**.

The replacement has **zero width for all 246 unused characters**, a shared
256-byte width map, a shared 512-byte offset map, and one combined 2,816-byte
bitmap containing eight bands of ten digits plus a safe blank slot. Total:
**3,584 bytes**, saving **33,280 bitmap/map bytes**; removal of the old pointer
table and small code changes save a little more overall.

Codes remain 0x90..0x99. Mapping them to the first ten codes would encounter
native control bytes; truncating a fixed-stride font at those high codes is
not safe. Sparse indexed storage avoids both problems without changing file
encoding or Bible compression. One private font descriptor selects the current
height band. No new font registration is needed.

The original 294,912 pixels across all 256 glyph codes and eight bands were
compared exactly (including 11,520 digit pixels); unused widths are checked zero.
MAME validation adds 200 checked screen/state checkpoints: a complete Psalm 119
page traversal; Small, Very Large, Extra Large and Tiny fonts; font switching;
selection across eviction, exact clipboard/citations, backward movement, search,
number visibility and applet return. Native cached-hyphen byte 0xAD is explicitly
recognized by the file-slice verifier, alongside cached-space 0x81; visible glyph
checks still use independent source expectations. No screenshots/model vision
are used as an oracle.

The prior [timing/RAM comparison](native-streaming.md) retains its measured
timing matrix and now uses these application-only ROM/complexity columns.
A fresh compact-font native page traversal took 4.121 s versus 4.123 s before.
The default custom NKJV demo is restored byte-identically after measurement.

## Reproduction

```sh
python3 betawise/research/bible-reader/measure-reader-builds.py --output OUTPUT
python3 betawise/research/bible-reader/report-reader-costs.py --production OUTPUT --output betawise/research/bible-reader/reader-costs.md
```

The build script captures production images, ELF files, final link maps, source
snapshots, actual GCC-preprocessed inputs, Clang ASTs, per-function metrics and
stack-usage files. GCC supplies the real m68000/short-enum flags; Clang parses
with two-byte struct packing to match that ABI. No estimation from ROM size or
physical line count is used for complexity. [Machine-readable costs](reader-costs.json).
