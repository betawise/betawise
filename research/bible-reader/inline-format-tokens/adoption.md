# Production inline-formatting adoption

BibleWise now uses one HUF04 text/formatting stream, with generated superscript
verse numbers and the existing full search index. The sidecar decoders, learned
word defaults, sidecar resources and build encoders are removed from production.
The previous implementation is preserved in `sidecar-reference/`.

## Actual release sizes

| | Sidecars | Inline | Saved |
|---|---:|---:|---:|
| KJV complete applet ROM | 1,311,244 | 1,309,208 | **2,036** |
| NKJV complete applet ROM | 1,457,244 | 1,439,734 | **17,510** |
| Release A5, either translation | 1,570 | 1,530 | **40** |

Numbers are bytes from actual release headers and image lengths. Subtracting
word-aligned Bible resources leaves 35,246 bytes of application ROM (including
SDK routines, headers and non-Bible data), down from 37,414 KJV / 37,416 NKJV:
**2,168–2,170 bytes saved**, with a two-byte resource/alignment difference between
translations. KJV resources grow by 132 aligned bytes; NKJV resources shrink by
15,340 aligned bytes. Net applet savings above include both code and data.

The `.ram` state section stays at 352 bytes. The initialized RAM/address section
falls from 1,218 to 1,178 bytes, accounting for the 40-byte A5 reduction. No search
or formatting workspace has been moved into persistent A5. The compiler-reported
`BibleFormatChapter` stack frame drops from 1,596 to 624 bytes: 972 fewer local
frame bytes. This is not a measurement of total peak call-stack usage.

## Emulated Neo decode/write time

Measured with the same Schoolbook font, firmware, instrumented harness and
chapter/navigation sequence. Times are emulated CPU milliseconds, not host time.
Decode/write includes generating native text/formatting and superscript numbers.

| Translation/chapter | Sidecars | Inline | Faster |
|---|---:|---:|---:|
| KJV Genesis 1 | 422.747 | 345.397 | 18.3% |
| KJV 1 Corinthians 13 | 159.990 | 131.697 | 17.7% |
| KJV John 3 | 419.980 | 344.756 | 17.9% |
| KJV Psalm 119 | 1,463.728 | 1,232.673 | 15.8% |
| NKJV Genesis 1 | 452.761 | 368.281 | 18.7% |
| NKJV 1 Corinthians 13 | 172.702 | 136.857 | 20.8% |
| NKJV John 3 | 449.016 | 362.576 | 19.3% |
| NKJV Psalm 119 | 1,532.286 | 1,305.252 | 14.8% |

Total Psalm 119 load/layout/display time falls from **1,796.819 to 1,565.776 ms**
for KJV and **1,892.137 to 1,665.104 ms** for NKJV. Initial Genesis phase 1 occurs
before the timing tap attaches; use the final Reload Genesis row for comparable
whole-load figures. Reopening the decoded Psalm reproduces the decode timings
within 0.014 ms. No battery consumption claim is inferred from CPU timing alone.

## Format and reader changes

The encoder emits an atomic dictionary terminal `02, 10|style, layout+1` when
source style or next-atom layout needs updating. State bytes are nonzero, so
controls use the ordinary front dictionary, word cache, grammar expansion and
Huffman decoder. There is no new control-dispatch table or secondary stream.
Header byte 44 stores the translation's default verse layout; chapter records
retain their existing native capacity bound and source length. HUF04 rejects
accidental use by the old HUF03 decoder.

The formatter consumes the three-byte controls and emits the same native chapter
events. Search treats controls as nonwords; grammar pruning includes their zero
word/verse contribution. Existing canonical text IDs and postings remain intact.
Verse counts remain the small chapter-count table; verse labels are generated.

Bold/italic records and italic provenance now survive regular-font fallback.
Only small-caps glyph substitution depends on private-face availability. Vendor
Small tests independently assert the retained source styles/provenance, normal
fallback font pointers and exact pixels. The former source oracle expected all
styles to be discarded for these fonts; that expectation was corrected. Source
text, glyph, cursor, three-sample LCD and exact bitmap checks remain independent.

Alignment-to-spaces behavior is unchanged by this migration. This is the chosen
semantic inline format, not the rejected precompiled superscript-label variant.

## Acceptance and reproduction

**208 MAME checkpoints**: 28 archived baseline, 28 matched production benchmarks,
53 KJV reader, 73 NKJV usage, 14 vendor Small formatting interactions and 12 partial
clipboard cases. Every benchmark chapter is byte-identical after removing the
EOF gap across all 28 old/new snapshots. Font applet binaries are identical.

Host checks cover all 1,189 chapters per translation, 798 source-search cases,
640 matcher property cases, reverse-order C decoding and all source formatting
events. Formatting-event hashes are unchanged from sidecar production. Capacity
checks pass all **38,048 font/style/chapter profiles** without overflow.
All MAME storage is disposable; screen validation is local and deterministic.

```sh
# From betawise. Prepare immutable old sources/data before baseline runs.
python3 research/bible-reader/inline-format-tokens/prepare_sidecar.py --build
python3 research/bible-reader/inline-format-tokens/benchmark.py --app research/bible-reader/inline-format-tokens/build/sidecar/app --version NKJV --case formatting --vendor-font schoolbook --output research/bible-reader/inline-format-tokens/build/recheck-sidecar-nkjv
python3 research/bible-reader/inline-format-tokens/benchmark.py --version NKJV --case formatting --vendor-font schoolbook --output research/bible-reader/inline-format-tokens/build/recheck-inline-nkjv
python3 tests/biblewise/check-formatting.py --version nkjv --output research/bible-reader/inline-format-tokens/build/recheck-host-nkjv
python3 tests/mame/asneo/check-biblewise.py --version NKJV --case usage --vendor-font schoolbook --output research/bible-reader/inline-format-tokens/build/recheck-usage-nkjv
```

Repeat with KJV/kjv for the other translation. `report_adoption.py` regenerates
`adoption-results.json` from the original named accepted artifacts. Raw LCD RAM,
fonts, cursor samples, chapter files, traces and failure diagnostics remain under
ignored `build/`. Historical failed source-oracle checks are not counted twice.
