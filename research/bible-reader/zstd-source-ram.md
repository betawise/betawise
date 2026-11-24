# Zstd, formatted KJV source and decoder RAM review

2026-11-20 follow-up. These measurements do not replace the original pinned
corpus or silently change the 948,662-byte result's text.

The later [native prototype](mame-prototype.md) now measures an actual 68000
decoder and applet. Its results supersede this report's provisional native RAM
estimates: 1,524 bytes of decoder workspace and 2,416 bytes for all applet static
storage, with firmware/app stack still additional.

## Zstandard

Zstd had not been run in the earlier experiments. It has now been measured
using local libzstd **1.5.4**, at levels 3, 9, 19 and 22. Comparisons use the
same original normalized KJV. Every compressed block was decompressed and
compared byte-for-byte. Chapter images include actual book metadata, a 64-byte
header, a 16-byte record per chapter and any trained dictionary.

| Configuration | Complete bytes |
| --- | ---: |
| Zstd level 19, whole Bible | 914,643 |
| Zstd level 22, whole Bible | 914,645 |
| Zstd level 22, independent chapters | 1,654,016 |
| Zstd level 22, chapters + trained 16 KiB dictionary | 1,321,942 |
| Zstd level 22, chapters + trained 64 KiB dictionary | 1,251,332 |
| Refined custom model, independently seekable chapters | **948,662** |

Whole-file Zstd is smaller than our custom image but has no independent chapter
restart index. Its result is therefore an archive baseline, rather than an
equivalent random-seek reader. Even with a trained shared dictionary, chapter
Zstd was larger than the custom format. These are best *tested* settings, not
a claim about every possible Zstd parameter or block organization.

The installed 64-bit library estimates **95,992 bytes for DCtx** and a maximum
**266,185 bytes for DStream** on the chapter frames. The latter is a streaming
workspace estimate, not extra space to add to the former. These figures are
for this stock host library and do not establish 68000 memory consumption.
Dictionary decoder state may add further costs, depending on how it is loaded.
Stock Zstd is a substantially heavier decoder than the proposed custom ROM
reader. See the [upstream API](https://github.com/meta/zstd/blob/dev/lib/zstd.h)
for the distinction between single-pass DCtx and buffered streaming DStream.

`zstd_measure.py` uses the local C library through ctypes; no new package was
downloaded. Two runs (default levels and level 22) are retained in
`zstd-results.json`. The serialized experimental chapter-record checksum field
is currently zero: it is a sizing container, not a hardened production format.

```sh
python3 betawise/research/bible-reader/zstd_measure.py \
  .research-work/bible-compression/kjv.json \
  --output .research-work/bible-compression/zstd-results
python3 betawise/research/bible-reader/zstd_measure.py \
  .research-work/bible-compression/kjv.json \
  --output .research-work/bible-compression/zstd-ultra --levels 22
```

## jburson/bible-data

Inspected [jburson/bible-data](https://github.com/jburson/bible-data), revision
`93ff30bbb530c53cd2ab26e42ee555d3938ded14`. Downloaded the KJV text and footnotes,
and checked their Git blob hashes against the repository tree. Exact hashes
and inspection counts are retained in `formatted-source-provenance.json` and
`formatted-source-results.json`.

The repository's [format documentation](https://github.com/jburson/bible-data#bible-text)
defines word suffix markers for paragraph/line layout, small caps, italics,
bold and red-letter text. The **actual inspected KJV**, however, uses only:

| Marker | Occurrences in verse records |
| --- | ---: |
| `p`, paragraph start | 31,102 |
| `s`, small caps | 6,883 |
| `r`, red letters | 41,809 |

There are **no italic markers** in these verse records, despite support in the
general schema. The file contains 31,102 verses, 1,327 heading records and
789,631 whitespace-delimited verse words. Footnotes are separate: 6,956 records
with 218,700 UTF-8 bytes of note text before their metadata/indexing costs.
The separate interlinear resource is not needed for formatting support.

This is technically a useful source for the proposed reader: parse its text
and formatting offline and pack text, headings and styling into our resources,
without retaining JSON object keys/repeated references. Edition/provenance and
the desired semantics of headings/paragraphs should be reviewed when choosing
the final corpus. This inspection did not import the new text into the codec.

The new source's plain verse text is **4,140,141 bytes**, compared with
4,148,450 for our previous source. It is not the identical text stream, so the
948,662-byte result must not be presented as its measured compressed size.

### Formatting overhead experiment

All 31,102 `p` markers occur exactly on the first word of each verse. They can
be represented by a rule in the format instead of a flag on every word, with
no loss of this source's paragraph semantics. Headings remain separate records.

Small-caps and red-letter attributes form a two-bit state per word. Store only
state changes: a varint delta word index followed by one state byte. A single
global experiment produces **15,108 events occupying 31,406 bytes**, before any
additional compression. The serialized event stream was reopened and verified
against every source word's style flags.

This suggests formatting can cost tens of kilobytes, rather than a large
per-word JSON overhead. **31,406 is not a complete shipping formatting budget**:
independent chapter restarts, chapter style-state records, headings and optional
footnotes need additional representation. The sidecar's implicit default state
and global word numbering are recorded by the experiment, not yet integrated
with the reader's chapter container.

`inspect_formatted_source.py` reproduces the word-flag analysis and exact
sidecar round-trip from the downloaded KJV file. It deliberately rejects
unexpected flags rather than discarding them silently.

```sh
python3 betawise/research/bible-reader/inspect_formatted_source.py \
  .research-work/bible-compression/jburson-kjv.json \
  --output .research-work/bible-compression/source-inspection
```

## What exclusion scratch means

When the previous-word model emits ESC, its explicitly listed followers have
been ruled out. Their global probability mass must be removed from the fallback
distribution. The decoder computes cumulative sums of those removed frequencies
in a temporary array to make subsequent searches efficient. That array is
**exclusion scratch**; it contains probabilities, not text or dictionary words.

The earlier figure was 512 followers times four bytes = **2,048 bytes** for
that array alone, not total decompressor RAM. The best model's global cumulative
total is at most 65,535, so all removed-prefix sums fit in uint16. The host
backend now uses **512 times two bytes = 1,024 bytes** for this model, reserving
the allocation once. Wide experimental CDFs retain uint32 scratch when needed.

After this change, all five arithmetic/backend tests passed again, including
the 512-follower exclusion test. A fresh full-corpus encode and independent
decode produced the identical 948,662-byte container and hash. The representation
and compression ratio are unchanged.

## Total decoder RAM: estimate versus measurement

There is still **no native fixed-storage 68000 decoder**, so an exact native RAM
total or measured stack high-water mark is not available. The C++ host verifier
uses vectors/maps and materializes tables/output; its process RAM is not the
proposed embedded decoder's footprint. A direct-from-ROM implementation can use:

| Proposed native working storage | Budget |
| --- | ---: |
| Exclusion cumulative sums, 512 uint16 entries | 1,024 bytes |
| One decoded front-dictionary block | 148 bytes |
| Two short spelling buffers (18 bytes each) | 36 bytes |
| Letter-Huffman summaries and canonical symbol order | about 220 bytes |
| Arithmetic interval, ROM cursors, chapter/context bookkeeping | about 100–200 bytes |
| **Estimated persistent workspace** | **about 1.5–1.6 KiB** |
| Compiler stack and software arithmetic allowance | **provisionally 0.5–1 KiB** |

That suggests **roughly 2–3 KiB for the decompressor alone**. Reserving **4 KiB**
while implementing it is a reasonable initial engineering budget, not a proven
upper bound. Only the native build and stack measurement can establish that.
The software 64-bit arithmetic helpers and exact C layout must be included.

The 77,746-byte statistical model, 50,120-byte dictionary, chapter index and
compressed text remain in ROM. Compressed input can be read directly from
memory-mapped flash; neither a compressed-input copy nor a whole chapter buffer
is inherently required. The callback can stream one decoded word at a time.

UI storage is additional, and was not part of the exclusion figure. For
example, a 44-by-8 character screen buffer uses 352 bytes; a byte of styling per
cell adds another 352. An optional private native 264-by-64 monochrome framebuffer
would cost 2,112 bytes. Those are alternative renderer design costs, not buffers
the decompressor necessarily needs. The final reader must separately budget its
navigation state, firmware/API requirements and rendering implementation.
