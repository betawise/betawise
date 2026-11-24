# KJV, NKJV and ESV storage comparison

Local compression experiment, 2026-11-20. Source is the new
`applets/BibleReader/upstream` Git submodule, pointing to
[jburson/bible-data](https://github.com/jburson/bible-data) at
`93ff30bbb530c53cd2ab26e42ee555d3938ded14`.

## What the MAME prototype included

The original 948,662-byte KJV resource includes everything literally present
in its verse strings, including some embedded annotation fragments. The MAME
test actually visits Exodus 17:16, which contains one such fragment. The reader
displays that material as ordinary text. It **does not** have separately indexed
footnotes, cross-reference navigation, headings from the new source, italic or
red-letter rendering. The test is not evidence of an annotation UI.

This comparison uses all three editions from the same new submodule. The
existing MAME prototype and its pinned legacy resource were not replaced.

## Complete resource sizes

All numbers are bytes. Verse-text resources include the full dictionary,
statistical tables, book metadata and independent chapter framing. Extra
resources use separate dictionaries/models, also fully counted.

| Edition | Raw normalized verse UTF-8 | Verse-text resource | Text + formatting/headings/anchors | Text + all supplied annotations |
| --- | ---: | ---: | ---: | ---: |
| KJV, new source | 4,140,141 | **944,016** | 1,245,559 | 1,498,282 |
| NKJV | 4,067,442 | **972,830** | 1,478,533 | 2,541,222 |
| ESV | 3,968,619 | **951,659** | 1,383,053 | 2,904,764 |

NKJV's verse-text resource is **3.05% larger** than the new-source KJV; ESV is
**0.81% larger**. The new-source KJV is 4,646 bytes smaller than the old 948,662-byte
MAME corpus. Differences in underlying transcription and book-name metadata
are retained rather than normalized away to force equality.

The last two columns are **conservative source-preserving sidecar experiments**,
not an optimized native annotation format or finished applets. They include
source row IDs, part boundaries and original footnote/cross-reference records
serialized as compact JSON, with exact chapterwise arithmetic-code round trips.
They therefore include administrative/anchor costs as well as readable notes.
They are not a claim that formatting alone intrinsically needs 300–500 KiB.
The earlier 31,406-byte KJV style-transition experiment did not include headings,
source-part anchors, chapter framing, dictionaries or footnotes.

Each verse-text edition would add **62,732 bytes** for the same eight-verse state
index scheme. The snapshot count follows each edition's reference slots, and
has the same byte cost for these three editions. That gives:

| Edition | Text resource + eight-verse index |
| --- | ---: |
| KJV | 1,006,748 |
| NKJV | 1,035,562 |
| ESV | 1,014,391 |

Those index sizes are calculated from the proven 18-byte snapshot/directory
format, not newly generated or timed native indexes for NKJV and ESV. They
exclude applet code, edition UI and font resources. The three text+index
resources sum to **3,056,701 bytes**, before reader code. No claim is made about
fit alongside a particular device's other installed applets.

## Supplied annotations

| Edition | Headings | Annotation records | Records with readable note text | Records with cross-references |
| --- | ---: | ---: | ---: | ---: |
| KJV | 1,327 | 6,956 | 6,956 | 0 |
| NKJV | 4,181 | 32,519 | **0** | 32,519 |
| ESV | 3,753 | 49,220 | 3,846 | 45,374 |

In this repository, the NKJV `footnotes` file supplies cross-references, not
readable translator-note text. The comparison preserves what the source
actually contains; it does not establish completeness against any publisher
edition. KJV word flags are paragraph starts, small caps and red letters.
NKJV also has italics, bold and several poetry/indentation flags. ESV has
paragraph, poetry, small-caps, red-letter and some italic/right-alignment flags.

Every source word's semantic style/layout flags was independently reconstructed
from the stored change events. Layout flags are one-word events; style flags
persist until changed. The KJV paragraph-start default is omitted from events
only after proving that every verse starts a paragraph in this source. The
other editions retain explicit paragraph/line events.

## Reference fidelity

Each translation is indexed by its explicit references, not by assuming every
source record is a new verse. NKJV has **12 split verses**; ESV has **17 split
verses**, with headings between parts. Text parts sharing a verse reference
are joined with an explicit space. Their source IDs, byte boundaries and word
counts remain in the sidecar so headings and footnote anchors can be resolved.

ESV has **31,086 populated verse references**, **17 empty reference slots** in
the KJV numbering and **3 John 1:15** beyond the KJV's fourteen-verse chapter.
It therefore uses 31,103 slots in this normalization. Empty slots retain LF
boundaries, and the extra final verse is preserved. This avoids silently shifting
verse numbers or discarding text. The exact empty references are recorded in
`translation-results.json`.

Headings are preserved with their original levels and text; this includes five
ESV heading levels of **2.5**, not an assumed integer-only schema. Every note
record is preserved, including original cross-reference labels and target IDs.
The sidecar omits verse wording because it already lives in the text resource.

## Method and verification

`compare_translations.py` uses the same tokenizer and refined previous-token
model as the MAME corpus: 65,536-byte context budget, up to 512 followers,
exclusion on escape, narrow base CDF, independently restartable chapters, a
front-coded dictionary and Huffman-coded dictionary blocks. Each edition and
sidecar is trained independently, so no uncounted external model is required.

As a control, the generic pipeline re-encoded the original MAME KJV and produced
**the identical 948,662-byte image and SHA-256**. All three editions' 1,189 verse
chapter blocks, 1,189 formatting sidecar blocks and 1,189 full-annotation sidecar
blocks were saved, independently decoded and compared byte-for-byte. Semantic
format flags and source reference/part mappings were checked separately.

These are host compression results, **not new MAME speed or native-memory
measurements**. The current applet remains pinned to the legacy KJV profile.
New edition profiles, Unicode rendering and annotation UI still need work.
For example, NKJV needs terminals up to 19 UTF-8 bytes, whereas the measured
native KJV spelling buffer allows 17 plus NUL. Encoded modern-edition corpora
and decoded intermediate data remain in the local experiment directory; this
report and result JSON contain aggregate sizes/hashes rather than verse text.

## Reproduce

From the Betawise checkout initialize the applet's data submodule:

```sh
git submodule update --init --depth 1 applets/BibleReader/upstream
```

From the workspace root, with the original control KJV available as documented
in the earlier research:

```sh
python3 betawise/research/bible-reader/compare_translations.py \
  --output .research-work/bible-compression/translations-new
```

Use a new output directory. Python standard library and host C++17 suffice.
`--repo` and `--legacy` override local source paths. The script pins the upstream
revision and checks the legacy control's exact size/hash. A `--resume` option
retains completed corpora after a source-validation failure, checking their
source hashes before reuse. The original run stopped on the ESV versification
difference; the corrected parser resumed that run without altering the completed
KJV or NKJV measurements.

Raw aggregate results and source hashes are retained in `translation-results.json`.
The private local run is `.research-work/bible-compression/translations-01`, with
the log at `.research-work/bible-compression/translations-01.log`.
