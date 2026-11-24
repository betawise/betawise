# Formatting CPU and heading storage trials

Research only; production BibleWise has not gained rich formatting from these
trials. Numeric results are in `results.json`. Timing is guest Neo CPU time in
MAME, four repetitions per cell. It includes main-stream decode, atom boundaries,
word defaults, metadata decode/merge, and a checksum of rich events. It excludes
FileWrite, native editor layout, display, and native control encoding. Do not
compare the raw text baseline directly with rich output as if the difference
were solely compression: rich output does substantially more work and emits
more bytes.

## Findings

Formatting sidecars have no inherent large speed penalty compared with inline
style/layout controls. In the first same-build comparison, no-heading timings
were 367/373 ms (sidecar/inline) for Genesis 1, 353/350 for John 3, 139/133 for
1 Corinthians 13, and 1159/1232 for Psalm 119. Sidecars are also smaller for NKJV
styling/layout. Against the same formatter with predecoded metadata, compressed
style/layout sidecars added approximately 11–17% in these examples.

The smallest heading pool was costly because a front-compressed block needs up
to fifteen preceding strings reconstructed. Smaller blocks exchange ROM for
speed. The final build also tested literal heading text inside the main Bible
stream, with body styling/layout still using the smallest sidecars:

| NKJV chapter | Sidecar headings, block 16 | Sidecar headings, block 4 | Literal inline headings |
|---|---:|---:|---:|
| Genesis 1 | 396.50 ms | 391.00 ms | 379.00 ms |
| John 3 | 398.50 ms | 382.00 ms | 369.75 ms |
| 1 Corinthians 13 | 163.00 ms | 151.75 ms | 143.50 ms |
| Psalm 119 | 1496.75 ms | 1264.75 ms | 1222.50 ms |

Heading-only storage costs (not all formatting):

| Scheme | Additional bytes |
|---|---:|
| Front-16 + small Huffman sidecar | 51,713 |
| Front-4 + small Huffman sidecar | 55,536 |
| Front-1 + small Huffman sidecar | 70,397 |
| Front-16, uncompressed bytes | 72,164 |
| Literal heading text in main grammar/Huffman stream | 46,769 |

The inline total includes 43,259 bytes of container growth, 3,200 bytes of
normalization/index growth, 256 bytes of marker-rule flags and 54 bytes of
additional 68000 search code (Search.o text/rodata delta 310 bytes). Linking,
alignment and future rendering glue can alter the final installed applet delta.
This is about 4.8 KiB smaller than the smallest heading sidecar. Combined with
58,194 bytes of body style/layout metadata, it is approximately 104,963 bytes
above the plain Bible resources, before final integration. The existing combined
all-sidecar candidate was 109,775 bytes.

The trial inserts begin/level/end controls around heading text at its source
atom boundary, retrains the existing grammar/Huffman codec, and keeps postings
based on the original canonical verse text. Header marker rules always expand;
while inside a heading, other rules skip without advancing verse/word counts.
This avoids false Bible matches and citation shifts. New heading vocabulary has
a valid normalization map, but headings are excluded from search. The extra
heading state is an unsigned field in the research search struct. These details
are a storage experiment, not a finalized on-device rich text format.

For display, the proposed behavior is bold heading paragraphs in the chapter's
normal native text flow, without verse numbers. The event oracle marks heading
text bold and preserves its level; no native editor bold rendering was tested.
A literal heading embedded in a verse's sentence is not required by this storage
choice. Copy/selection-to-verse offset mapping must account for headings at
integration time.

## Validation and reproduction

Every rich variant produces exactly the same event hash, byte count, atom count
and heading count as an independently generated source oracle. Four chapters ×
ten variants were checked on host and MAME, with three identical guest RAM
records retained. No screenshot/model oracle is used. ASan/UBSan pass with leak
checking disabled (LeakSanitizer is unsupported under the execution ptrace).
The inline heading search copy passes all 366 existing production C search cases
against the unmodified verse-text oracle. Production files remain unchanged.

With the preceding NKJV formatting artifacts already generated:

```sh
python3 betawise/research/bible-reader/formatting/speed/inline_headings.py \
  --output /tmp/nkjv-inline-headings
python3 betawise/research/bible-reader/formatting/speed/prepare.py \
  --small-headings --inline-headings-path /tmp/nkjv-inline-headings \
  --output /tmp/nkjv-format-speed --repetitions 1000
python3 betawise/research/bible-reader/formatting/speed/mame.py \
  /tmp/nkjv-format-speed --output /tmp/nkjv-format-speed-mame
```

Without `--inline-headings-path`, the small-heading run instead compares inline
body style/layout controls. Without `--small-headings`, it additionally tests the
learned italic/small-caps inline predictor. The two full inline-body assets and
additional heading candidates cannot all fit in the disposable flash at once.

Original artifacts, logs, source hashes and raw samples are retained under
`.research-work/bible-compression/format-speed-mame`,
`format-speed-small-heads-mame`, `format-headings-inline`, and
`format-speed-inline-heads-mame`. Host preparation saves generated source,
resources, checksums and independently calculated expectations beside them.
