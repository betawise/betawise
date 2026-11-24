# ASCII Huffman: size, chapter speed and RAM

The preferred Neo profile is word/phrase Huffman with a front-compressed
**direct-ROM dictionary**, without Huffman-compressing its spelling bytes.
It spends 6.47% more resource ROM than refined contextual arithmetic and decodes
Psalm 119 about 19.1 times faster. The default prototype now uses this profile.

The stock AS3000 applet interval is 0x408000–0x4c0000: 753,664 bytes total,
shared by applets. These resources do not fit; this design targets Neo.
See [firmware boundaries](../flash-b3/firmware-boundary.md).

## Measured comparison

All four profiles use the same explicitly mapped ASCII corpus, chapter restart
boundaries and native decoder API. Sizes include metadata, indexes, dictionaries
and models; they exclude native code, font and any optional verse checkpoints.
Timings are emulated device time at 33,161,216 Hz, not host wall time.

| Profile | Resource bytes | Psalm 119, 13,019 bytes | Genesis 1, 4,088 bytes | Psalm 117, 175 bytes |
| --- | ---: | ---: | ---: | ---: |
| Refined previous-token arithmetic | 947,900 | 17.092 s | 5.338 s | 250 ms |
| Word Huffman, letter-Huffman dictionary | 1,109,216 | 9.269 s | 2.866 s | 136 ms |
| Word/phrase Huffman, letter-Huffman dictionary | 981,842 | 9.299 s | 2.873 s | 136 ms |
| **Word/phrase Huffman, direct-ROM front dictionary** | **1,009,276** | **894 ms** | **283 ms** | **12 ms** |

These full-chapter timings include decoding and copying into a bounded 16 KiB
RAM cache. They exclude validation hashing and painting the diagnostic summary.
Psalm 119 was repeated in each run, with matching timings and byte-for-byte
cache contents. This is not a benchmark of plain character/byte Huffman.

The next page takes 384 ms with arithmetic, 238–239 ms with the letter-Huffman
variants, and **70 ms** with the preferred dictionary: about 20 ms decoding and
50 ms painting. John 3:16 takes **187 ms** including a scan from chapter start
and painting, versus 2.589 s for the uncheckpointed arithmetic comparator.

The main bottleneck was repeatedly decoding dictionary spelling blocks.
Removing that layer adds just **27,434 bytes**. Prefix compression remains:
lookups start at one of the 16-entry block offsets and reconstruct the short
word from prefixes and suffixes read directly from ROM. Word/phrase indexes
remain Huffman-coded, with an eight-bit first-level ROM lookup table and a
canonical fallback. Phrase pairs also remain in ROM.

## Memory and battery implications

The preferred decoder has **566 bytes** of fixed m68k workspace and no allocator.
The diagnostic build requests 17,796 bytes of initialized/BSS RAM, including its
16,384-byte chapter cache, UI, screen buffer, SDK globals and GOT. Firmware stack
is additional; compiler frame reports are not a stack high-water measurement.
The ordinary build streams pages and omits the chapter cache. Its complete
applet is **1,019,468 bytes**; the diagnostic applet is 1,020,060 bytes.

Less decoding work is promising for power: Psalm 119 uses roughly 95% less
active decoding time than this arithmetic implementation. This is **not** a
measured battery-life improvement. Physical current measurements must include
CPU idle/sleep behavior, display updates and reader usage. No device current
or battery discharge measurement has been made.

## ASCII and validation

`device_ascii.py` maps typography, ligatures and explicitly supported accented
characters before tokenization and model training. Anything unmapped fails ASCII
encoding. The mapped KJV is 4,144,456 text bytes; the longest chapter is 13,019
bytes. The JSON SHA-256 is
`8561624cc248ba13ca053baee8de09c6ecad3cb403e134e6c6f9afe6c84289f9`.
Each probability model is rebuilt from this mapped corpus. The preferred native
path has no UTF-8 decoder. Mapping is not an automatic OCR correction system.

All four current native backends reconstruct all 1,189 chapters exactly in
reverse order. MAME comparison runs each pass 11 exact page/cache checks;
the final default streaming build passes all 17 original screen checks.
Captured full chapter RAM is compared byte-for-byte with independently generated
source expectations, in addition to hash and display assertions.

Tests use `NeoLCD.lua`, the local exact glyph reader, independent cursor/flag
checks and firmware cursor hide/restore with three identical samples. No model
vision or screenshot oracle is used. Each run stages disposable flash/RAM.
Read-only phase taps measure emulated elapsed time; the firmware millisecond
counter can wrap in long runs and is not the primary timing source.

## Evidence and reproduction

[huffman-speed-results.json](huffman-speed-results.json) records resource sizes,
hashes and measured results. Raw evidence is retained under workspace
`.research-work/bible-compression/` in `mame-ascii-arithmetic`,
`mame-huffman-word`, `mame-huffman-phrase`, `mame-huffman-raw`, and
`mame-preferred-huffman`. These include ROM/app artifacts, manifests, controller
records, decoded screens, cache binaries, logs and phase timing records.
Native final checks are in `native-ascii-{word,phrase,arithmetic}-final` and
`native-preferred-huffman`.

See the [applet instructions](prototype/README.md) for resource
builders, build flags and deterministic tests. For comparative full-chapter runs,
select `--codec arithmetic` or `--codec huffman`, the profile `--dataset`, the
mapped `--source`, and `--full-chapters`. Use new output directories per run.
These are implementation-specific measurements, not a proof of optimal size
or a claim that arithmetic coding must always be slower than Huffman coding.

## Reader implementation direction

Historical feature research: Franklin IC-119 KJV and NIV-1440 manuals document
reference navigation, concordance/phrase search, selecting a word for lookup,
bookmarks, font sizes, and on-demand location. NIV-1440 adds wildcard completion,
spelling correction, inflections, related words and synonyms. Sources:
https://bookmanarchive.com/manuals/dbs-cartridges/IC-119.pdf and
https://bookmanarchive.com/manuals/bookman-systems/NIV-1440.pdf.

The requested next iteration targets Neo, with applet ID 0xA1B1. Default output
is BibleReader (KJV); optional repo translations use BibleReader-VERSION names
and the same ID, as alternative installations. Compression models must be
trained independently per mapped translation. Notes are deferred.

Evaluate the firmware read-only file-backed editor for a temporary decoded
chapter, native wrapping, installed-font selection and clipboard selection.
The SDK exposes APPLET_FLAG_ALLOW_FONT_DIALOG (0x080), TEXT_EDITOR_READ_ONLY,
ClipboardSet, and Neo font-aware dialogs. Their presence is not proof that the
combined UX, superscript encoding or selection behavior works; qualify these
with disposable MAME state and exact bitmap/font fixtures. Fall back to a custom
read-only layout if the native editor cannot satisfy the required behavior.

Prefer chapter-stable word wrapping, retaining a verse anchor after font changes,
optional superscript verse numbers, and on-demand reference display without a
permanent status bar or polling animation. Implement reference entry using a
reviewed dialog template if suitable. Search must be cancellable and avoid a
whole-Bible decoded scan per keystroke; investigate ROM postings/filter indexes
against added ROM cost. Offer exact words/phrases and optional conservative
inflection expansion; do not describe stemming as semantic synonyms.

Confirmed preferences: include reference and translation by default when copying;
search is exact matching only. The implemented native-editor reader and current
resource/RAM budgets are documented in the applet README.

## Completed native-editor reader

The [reader applet](prototype/README.md) now uses the native
file-backed editor with navigation/selection-only input, installed font selection,
local full-height padded superscript faces, chapter-stable wrapping, reference
entry, exact word/phrase search, whole-verse copying with citations, and saved
reading position/number visibility. Personal notes and bookmarks remain deferred.
Partial fixed-font overlays avoid a permanent status row. Fonts are borrowed;
no additional font is registered with AlphaWord.

The production default is repo KJV, applet ID **0xA1B1**, **1,587,200 bytes** of ROM
and **2,694 bytes** of static applet RAM. Its raw-dictionary-only decoder needs
**232 bytes**. File allocation and native stack are additional; one decoded
chapter lives in the applet's own file, with native gap/formatting overhead.
There is no duplicate whole-chapter RAM cache. Same-chapter jumps reuse the file.
Search adds a 527,821-byte word-to-chapter filter and proceeds in cancellable
256-byte steps, retaining a 32-result navigation history rather than building
an entire result list in RAM. This is not a positional verse index.

All six source-repo translations build using independently trained resources;
only KJV is produced/published by default. Headers and exact embedded resource
pairs were checked after incremental translation switches. All 1,189 chapters
of every translation passed native byte-for-byte reconstruction. Fourteen search
queries matched independent whole-corpus expected verses, including overlaps and
inflection distinctions. Legacy letter-Huffman resources still round-trip.

The final production binary passed **26 exact MAME screen/state checks**, including
font selection, reference jumps, Psalm 119, superscript toggles, native selection,
clipboard contents/citations, empty searches, and a round trip through AlphaWord
with a separately inspected saved-state file. A complementary terminal-to-system
font run passed 25 checks. Verified font profiles cover the 6x8 terminal and
original 6x16 system font; other installed fonts use the same native editor API
but have not all been individually qualified. No physical power/current tests
were performed.

[reader-results.json](reader-results.json) records results and hashes. Raw evidence
is in `.research-work/bible-compression/reader-mame-acceptance`,
`reader-mame-production`, `reader-mame-resume`, `reader-builds`, and `reader/*-native`.
Tests preserve three identical controller captures, independent source/cursor
geometry, firmware hide/restore returns, registers, scratch RAM, exact bitmap
assertions and raw clipboard/state data. No screenshots/model inference serve
as test oracles.


## Reader refinement: fonts, startup and word search

These measurements supersede the complete-reader totals above; earlier codec
experiments remain historical. KJV now occupies **1,431,648 ROM bytes** and
requests **2,828 static RAM bytes**, including the **236-byte** decoder. File
storage and firmware stack are additional. The chapter container is 1,007,155
bytes; the exact word-to-chapter index is 368,039 bytes.

| MAME measurement | Previous reader | Refined reader |
| --- | ---: | ---: |
| Psalm 119 pure decode | 0.919 s | 0.612 s |
| Load Psalm 119 and display verse 176 | 3.407 s | 2.528 s |
| Genesis pure decode | 0.285 s | 0.179 s |

A 2,626-byte ROM spelling cache reduces repeated front-dictionary reconstruction
without a new RAM cache. File writes are buffered through the existing 256-byte
chunk. Empty-file initialization installs the local superscript face before
text insertion; refresh and final positioning avoid duplicate paints. Layout and
painting still dominate much of the largest-chapter latency. No battery/current
measurements have been made.

Search consumes Huffman/grammar terminal IDs directly and compares normalized
IDs. Removing duplicate index strings saves ROM. Each hit records its word
ordinal, so the editor moves to the actual match, including multiple occurrences
in a verse. Cmd+G / Shift+Cmd+G navigate a 32-occurrence history. The first KJV
`believe` hit uses about 7.22 ms of search CPU; its next hit about 10.54 ms.
Loading/painting the destination and native idle scheduling are additional. A
complete no-hit `Jesus Jesus` scan uses 17.325 s CPU and remains cancellable.

The optional research verse Bloom filter uses 429,146 bytes versus 368,039 for
the shipped chapter index. False positives and repeated verse restarts make it
slower: first `believe` hit 1.457 s, no-hit scan 26.489 s. It is rejected for the
applet. `SearchBloom.c` and `--search-index verse-bloom` preserve the experiment;
all 31,102 independent verse restart points were verified. Production defaults
to `chapter` / BIBSRCH2.

Lower superscripts have no inserted trailing space. Native G entry uses the
partial bottom input field with typing/backspace; native field arrows cycle
focus rather than edit text. Five original proportional vendor font profiles
(11/13/16/21/32 px) and Tiny (6 px) each pass 36 independent exact bitmap/state
checks, including the real system font picker. Whole-row viewport sizing fixes
a clipped/stale bottom row in proportional fonts. Dense fonts remain selectable.

Current evidence is summarized in
[reader-refinement-results.json](reader-refinement-results.json). Raw captures
and original font assets remain under `.research-work/bible-compression/`, in
`reader-vendor-*-release`, `reader-native-dialog-accepted`,
`reader-profile-chapter-final`, and `reader-refinement-production`.
