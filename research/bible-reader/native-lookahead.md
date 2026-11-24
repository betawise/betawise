# Native page lookahead through TextScanInsert

Measured 2026-11-23, NKJV Psalm 119, the current dynamic-clock MAME binary,
original system 6x16 font, visible superscript verse numbers, identical Huffman
resource and full packed exact search index. No shared-library mechanism added.

## Result

**Off-screen insertion without repainting works. It does not eliminate the
processing cost that grows with the loaded prefix.** Keep this as an optional
prototype, not the default reader.

`NATIVE_STREAM=4` decodes a conservative page-sized prefix (256 encoded bytes,
rounded to a source word boundary for this font), draws it with the native
editor, then prepares roughly another page during idle. Lookahead stops when
there is sufficient text ahead of the caret; it resumes after navigation.
The prefix remains in the file. No `TextEditorRefresh` or
`TextEditorSetScanPosition` is called after an append in this mode.

Each append initializes a scan from the current caret, scans forward to EOF,
and inserts encoded text with `TextScanInsert`. The writable input contains
complete superscript formatting markers. Initial decoding still uses the raw
file append path before the first native layout. A 512-byte staging buffer
coalesces a page and its trailing word into one native insertion. Pending or
held keys prevent starting idle work, but an insertion already running is not
preemptible.

## Comparison

Service times include initial load, every traversal operation, final End to
prove EOF, and all idle decoding/insertion work. They exclude keyboard gaps,
capture work, reading time and firmware idle scheduling delays. They are not
physical battery measurements. Existing rows below reuse accepted unchanged
implementations from [native-streaming.md](native-streaming.md); lookahead was
newly measured. Stack, clipboard, file metadata and shared OS workspace are
additional to A5/file figures.

| Reader | First screen | Entire chapter by line | Entire chapter by page | App ROM KiB | A5 bytes | File peak bytes |
|---|---:|---:|---:|---:|---:|---:|
| Native optimized whole chapter | 1.414 s | 8.487 s | 4.123 s | 19.66 | 3,122 | 14,860 |
| Native moving window | 0.370 s | 11.850 s | 7.562 s | 23.06 | 3,294 | 4,250 |
| Native raw append on demand | 0.370 s | 18.550 s | 14.233 s | 22.77 | 3,282 | 14,860 |
| Native background completion | 0.370 s | 8.606 s | 4.230 s | 22.95 | 3,290 | 14,860 |
| Native TextScanInsert lookahead | 0.350 s | 16.157 s | 11.657 s | 23.03 | 3,546 | 14,860 |
| Custom full repaint | 0.068 s | 23.453 s | 5.980 s | 20.02 | 3,862 | 0 |
| Custom LCD roll | 0.044 s | 6.002 s | 4.077 s | 20.20 | 3,834 | 0 |

Background completion's comparison row lets decoding finish before traversal;
its immediate-input result is 6.345 s by page. Lookahead never drains to EOF
before scrolling: it stops when its local lookahead budget is satisfied.

New lookahead traversal itself took **2.711 s by page** or **7.077 s by line**.
Idle work adds **8.596 s / 8.730 s** respectively, making total service worse.
Its additional 256 staging bytes account for most of the A5 increase over the
previous native append prototype. It still ultimately holds the whole chapter.

## What the append taps prove

The page run performed 55 post-display native insertions. All 55 idle slices,
including decoding, tail scanning and insertion, produced **zero LCD data
writes**. Insertions preserved the raw native caret offset. Deterministic
subsequent source/bitmap/cursor assertions verify navigation and layout.

`TextScanInsert` alone, measured separately from file selection and scanning:

| Loaded prefix before insertion | Insert service time |
|---|---:|
| 257 bytes | 12.171 ms |
| 14,253 bytes | 234.799 ms |

Total native insertion service was **6.888 s**; the largest complete idle slice
was **266.683 ms** (line run: 268.057 ms). These are visible responsiveness risks
even though there is no repaint. Batching page inserts reduced total page
service from **18.509 s** with 256-byte staging to **11.657 s** with 512-byte
staging: the smaller buffer often caused both a full-buffer insert and a tiny
trailing insert, each paying the prefix-dependent cost.

This establishes growing-prefix processing inside the insertion syscall. It
**does not identify all of that work as word wrapping or prove that every
previous line is laid out again**. The public API avoids the explicit caret
reconciliation used by the raw-append prototype, but does not make incremental
insertion constant-cost. No private editor-cache patch is used to bypass it.

## ROM, static linking and fonts

Production lookahead: 23,586 application ROM bytes, including 16,662 executable
bytes and the existing 3,584-byte superscript asset. Active owned C metrics:
12,802 tokens, 75 functions, CC sum/max 680/74; frontend-only 8,013 tokens,
46 functions, CC 464/74. The common Bible/navigation resources (1,311,826 bytes)
are excluded from application ROM. See [reader-costs.md](reader-costs.md).

The superscript asset is still 3.50 KiB: 256 width bytes + 512 offset bytes +
2,816 bitmap bytes for eight height bands, each containing ten digits and a
safe blank slot. It is sparse, but not a minimal ten-digit master. Generating
only the selected height from digit patterns could trade additional RAM and
font-change code for smaller ROM; that separate change was not mixed into this
experiment. Font pixels and translation compression are unchanged.

Reusable code remains statically linkable. No dynamic/shared-library dependency
is needed. A generic viewer should only link the layout/display pieces it uses;
Bible search, verse navigation and corpus decoding are separate concerns.

## Validation and reproduction

All tests use disposable MAME flash/RAM, independent source-derived expected
bitmaps, native cursor checks before hiding, three identical LCD RAM samples,
and normal firmware cursor-mode restoration. No vision/model screenshot oracle.
The full chapter contains 176 verses, 12,873 source bytes, 14,348 native encoded
bytes and 314 wrapped lines; final EOF and exact resident file slices are checked.

Accepted artifacts under `.research-work/bible-compression/`:

* `native-insert-coalesced-page`: 83 checked states and append audit.
* `native-insert-coalesced-line`: 317 checked states and append audit.
* `native-insert-features`: 49 states covering navigation, exact search,
  chapter-global selection/copy/citations, number visibility and applet return.
* `native-insert-small-final`: 17 vendor Small-font states, including paging,
  forward/backward verse jumps and return to the system font.
* `native-insert-production`: PROFILE=0 binary, ELF/map, preprocessed sources,
  compiler AST/function complexity and stack-usage records.

The earlier `native-insert-page-final` and `native-insert-line-final` preserve
256-byte staging measurements. Rejected `v1`..`v6` retain setup failures and the
split-format-token error, not accepted timing inputs. `v7` is the first accepted
page run, before detailed insertion instrumentation.

```sh
python3 betawise/tests/mame/asneo/check-bible-reader.py --version NKJV --native-stream lookahead --system-font --profile --readthrough page --experiment huffman-prune --output OUTPUT
python3 betawise/research/bible-reader/profile-readthrough.py OUTPUT --output SUMMARY.json
python3 betawise/research/bible-reader/check-native-lookahead.py OUTPUT --output AUDIT.json
python3 betawise/research/bible-reader/measure-reader-builds.py --only native-lookahead --output PRODUCTION
```

Use `--readthrough line` for line traversal. Build the optional applet directly:

```sh
make -C betawise/applets/BibleReader READER=BibleReader NATIVE_STREAM=4 NATIVE_PAGE_TEST=1 PRUNE=1 VERSION=NKJV PROFILE=0 TEST_FONT=0
```

Output: `BibleReader-NativeLookahead-NKJV.OS3KApp`, ID 0xA1B1. KJV remains the
default translation. Other reader configurations retain their existing defaults.

The normal custom NKJV demo was rebuilt after testing and is byte-identical to
`reader9-release` (SHA-256 `05cf770bee349c3d0c3046e4ae366b219769b62ff990099e99abddc48c20337f`).
The optional lookahead binary in the applet directory was restored from its
PROFILE=0, TEST_FONT=0 production build, rather than the font-test image.
