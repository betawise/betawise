# Archived BibleReader implementations

This is the complete source snapshot immediately before production was simplified.
`README.md` is the historical prototype README, not the shipped applet's manual.
`snapshot.json` lists the retained source/build inputs; Git identifies their
contents. Generated Navigation.h is rebuilt. Modern Bible
images remain private in `.research-work`; redundant generated binaries were
retired in the [2026-11-24 cleanup](../cleanup-20261124/README.md).

The production applet now has one native whole-chapter viewer, one ASCII phrase
Huffman codec and one Full packed chapter index. Alternatives are intentionally
not production flags or published applets.

| Experiment | Retained implementation | Description and measured results |
|---|---|---|
| Arithmetic / contextual compression | `Decoder.c`, `Benchmark.c`, `resource.asm` | [Context models](../context-models.md), [initial MAME prototype](../mame-prototype.md) |
| Word SCDC / compressed dictionary | conditional paths in `HuffmanDecoder.c`, original builder | [Codec comparison](../device-comparison.md), [search space](../search-space.md) |
| Compact / Scan / true no-index search | `search_options.py`, `NoIndex.h`, original `Search.c` | [Directional search](../navigation-search.md); Compact saves 121.9 KiB but has worse multiword latency |
| Wider Huffman lookup / early matcher clearing | `wide_huffman.py`, decoder/search switches | [God profile](../god-search-profile.md); 10/12-bit table tradeoffs retained |
| Selective verse postings | `verse_boost.py`, `VerseBoost.h` | God-prefix-only experiment: [cost and speed](../god-search-profile.md) |
| Verse Bloom filtering | original `build_data.py` and research `SearchBloom.c` | [Search-space experiments](../search-space.md) |
| Custom streaming layout, checkpoints, selection and LCD roll | `Streaming.c`, checkpoint paths in decoder | [Streaming viewer](../streaming-viewer.md), [LCD behavior](../lcd-and-controls.md), [read-through](../readthrough.md) |
| Native streaming / lookahead | `NativeFeed.h`, `NativePrewrap.h`, original `BibleReader.c` | [Native streaming](../native-streaming.md), [lookahead](../native-lookahead.md), [prewrapped text](../native-prewrap.md) |
| Private viewport/layout calls | native mode 5 and related helpers | [Disassembly](../native-layout-disassembly.md); known selection limitation, not a production API |
| Profiling hotkeys / benchmark loops / font overrides | original reader files and `tests/` | [Latest mode results](../search-modes.md), earlier result JSON files |

## Restore the original directory layout

From the workspace root:

```sh
python3 betawise/research/bible-reader/prototype_support.py
```

This creates `.research-work/bible-compression/prototype-private-workspace`, copies this
snapshot, and links the SDK, pinned source submodule, canonical shared test tools,
firmware and emulator. Frozen applet-specific harnesses are copied over the shared
test tools. Nothing is copied back into production. Use `--output /tmp/bible-lab`
for another disposable workspace.

For example, reproduce the old full-index native production build:

```sh
make -C .research-work/bible-compression/prototype-private-workspace/betawise/applets/BibleReader \
  READER=BibleReader VERSION=KJV PRUNE=1 SEARCH_INDEX=full \
  PROFILE=0 TEST_FONT=0 NATIVE_OPEN_TEST=1 NATIVE_PAGE_TEST=1 \
  PREBUILT_DATA=1
```

Use the restored `betawise/tests/mame/asneo/check-bible-reader.py` or
`check-bible-stream.py` for historical MAME options. All current workspace
AGENTS.md rules apply: disposable sessions and deterministic local RAM/font/pixel
assertions; no model/vision oracle. Private payload caches are referenced through
`.research-work`; to retrain, omit PREBUILT_DATA and use the snapshot builder with
the original research conversion modules.

Historical research scripts use `prototype_support.prototype_app()` and
`prototype_test()` where they require removed production options. Existing JSON
results retain their original paths/hashes and should not be rewritten merely
because source moved. For a new run, always choose a new result directory.

The removed SDK rectangle helper is retained in research `LegacyGraphics.h`.
The restore helper supplies a GNUmakefile wrapper that force-includes it only
for the frozen Streaming build. Original snapshot sources and hashes remain
unchanged; the production SDK no longer exposes that helper.

New builds use separate private IDs: Benchmark FF20, BibleReader FF21 and
Streaming FF22. This is a header-metadata migration only. Original source bytes remain at commit
`940e1c126921578cc8f6769749593a47c141fdf2`. Historical measurements are unchanged.
A separate restored directory avoids overwriting an old restored prototype.
