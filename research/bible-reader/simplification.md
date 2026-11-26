# BibleReader production simplification

The selected production display is the **native editor, with one whole chapter
in an app-owned temporary file**, as explicitly chosen for this cleanup. The
production representation is ASCII phrase Huffman (KJVHUF02), a raw front-compressed
dictionary, eight-bit lookup and grammar pruning, with the Full packed
word/chapter index (IDXEXP02). There are no selectable alternative representations.

## Production boundary

The reader, decoder and search are separate readable C modules. Names describe
operations and state; the conversion pipeline is five standalone Python modules
using the standard library and no research imports. Generated navigation/font
headers, payloads and objects live under ignored build directories. Test probes
and font overrides compile only into separate testing images.

The [manual and complete feature inventory](../../applets/BibleWise/README.md)
describe the retained controls, three search modes, native selection, citation
copying and A5/native-file position preservation. Copying deliberately includes
whole touched verses, rather than arbitrary selected character substrings.
There is no all-results UI, streaming viewport, continuous chapter scrolling,
notes, annotations, cross-references, interlinear display or general ebook loader.

The sparse private superscript face remains part of the native editor path. It
is not a second installed font or a selectable experimental renderer. Native Go
To and its overlay fallback remain for firmware compatibility.

## Archived work

[The frozen prototype and regeneration guide](prototype/REPRODUCE.md) preserve
32 original implementation/build files, their SHA-256 manifest, applet-specific
harnesses, descriptions and links to measured results. The restore helper creates
an isolated original directory layout, rather than restoring research flags in
production. Historical research drivers now use that workspace when needed.
The restored full-index KJV native prototype rebuilt byte-for-byte identically
to the earlier accepted image. Old generated payloads and binaries remain private
under `.research-work/bible-compression/pre-simplification`.

This includes arithmetic/context models, dense word coding, alternative Huffman
lookups/dictionaries, Compact/Scan/no-index search, selective verse postings,
custom streaming layout/LCD roll, native lookahead/prewrap and private layout
entrypoints. Earlier result tables are retained as historical evidence, not
rewritten to describe the simplified application.

## Format preservation

Fresh KJV and NKJV container, index, grammar summaries, verse counts and normalized
source JSON are byte-identical to the earlier reader-viewer resources. Each
translation still trains its own model. All six source translations build.

For NIV/NASB/CSB, the number of spelling variants exceeds 16,384, although normalized
vocabulary fits the Full index. Canonical spellings are placed below its 14-bit
record limit by exchanging overflowing canonical entries with noncanonical slots.
This keeps the same dictionary/index schema and removes the old fallback to a
second index format. KJV/NKJV/ESV dictionary ordering is unaffected.

## Acceptance

All paths below are relative to private `.research-work/bible-compression/`.
No screenshot/model inference was used: MAME validation uses local source/font
bitmaps, exact pixel comparisons, cursor/controller assertions and saved RAM
records, with disposable flash/RAM.

- `simplify-host-kjv-v3` and `simplify-host-nkjv`: exact reverse-order decoding of
  all 1,189 chapters, 360 source-oracle search/directional cases, 320 matcher
  property cases and five invalid-query checks per translation.
- `simplify-mame-kjv`, `simplify-mame-small` and `simplify-mame-tiny`: 42 native
  reader cases each, including jumps, verse-number toggles, selection/citation
  copying, font changes and position recovery after an AlphaWord round trip.
- `simplify-mame-search-nkjv-final`: 18 search cases including modes, prefixes,
  next/previous, repeated terms, cross-verse proximity and cancellation. A short
  Escape press cancels in 0.150 emulated seconds. Cooperative search yields when
  a key is queued or physically held, avoiding lost short presses without costly
  repeated keyboard scans.
- `simplify-translations`: exact full-text reverse-chapter decode for ESV, NASB
  and CSB, all using IDXEXP02. Additional NIV and large-vocabulary index results
  are recorded in the accompanying final acceptance JSON.
- `simplify-resource-identity.json`: KJV and NKJV resources covered by the byte-comparison checks.
- Python syntax checks, warning-enabled production builds and `git diff --check`.

See [machine-readable final measurements](simplification-results.json) for final
applet and A5 sizes and the additional translation checks. A5 excludes the native
chapter file, clipboard and firmware editor allocations; this cleanup does not
remove the whole-chapter RAM cost of the chosen renderer.

## Final size comparison

| Native KJV build | Applet bytes, including Bible | A5 bytes |
|---|---:|---:|
| Before simplification | 1,293,366 | 3,118 |
| Simplified release | 1,291,170 | 2,972 |
| Reduction | 2,196 | 146 |

The final KJV Bible resources occupy 1,268,416 bytes. Everything else in the
applet occupies 22,754 bytes (22.2 KiB), including application code, linked SDK
helpers, navigation data, glyphs and headers/relocations. This is not a claim
that all of those bytes are executable instructions. The native chapter file,
firmware editor state, stack and clipboard remain additional RAM requirements.

The source cleanup is intentionally larger than the byte reduction: removal of
unselected conditional implementations and research coupling is its primary
maintenance benefit. KJV/NKJV resource sizes did not change.
