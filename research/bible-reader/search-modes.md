# Same verse, Exact phrase and Nearby

Implemented and measured 2026-11-23. Search modes share the existing compression,
word dictionary, chapter index and 6,144-byte grammar summaries. No text retraining,
new postings or extra Bible resource bytes. Full remains the default; Compact is
still an optional size tradeoff, with more pronounced slow cases for these queries.

## User behavior

Find opens the query field. **Tab** cycles modes; **Shift+Tab** cycles backwards.
The visible title shows the selected mode. Cycling preserves typed text; the mode
persists in A5 until restart. Enter searches from the current reading cursor,
including its current word. Cmd+Find / Shift+Cmd+Find find the next/previous result;
Cmd+G aliases remain. Esc cancels. Chapter and Bible boundaries do not wrap.

| Mode | Match rule | Result grouping |
|---|---|---|
| Same verse (default) | Every term in the same verse, any order | One result per matching verse |
| Exact phrase | Consecutive terms in the specified order, within one verse | Each occurrence, including overlapping phrases |
| Nearby | Every term within a span of at most 20 words, any order | Nonoverlapping matching windows; can cross verses, not chapters |

Words are **exact and case insensitive** unless explicitly suffixed with `*`.
`show` does not implicitly match `showest`; `show*` does. Each term controls its
own wildcard, including in phrases. `t d` is literal; `t* d*` requests prefixes.
Leading and infix stars are rejected, not silently discarded. Synonyms,
stemming and incomplete-word completion menus are not implemented.

The 20-word span includes both endpoint words (at most 18 intervening words).
Repeated terms require distinct occurrences. A word accepted by two wildcard
terms cannot satisfy both at once: `be* bel*` needs two words. Unordered results
jump to the earliest word of the newest cover at the first point of completion.
Nearby clears its cover after reporting, preventing a series of overlapping
windows around the same passage. Results are deterministic from chapter start,
so reverse searches return the same passage anchors as forward searches.

The implementation uses a maximum-cardinality, newest occurrence assignment
between at most eight occurrences and eight query terms. Alternating-path
assignment handles repeated/nested prefixes; redundant older occurrences are
replaced. No full-verse or 20-word text buffer is needed. Grammar contains bits
cover all query terms for unordered modes, rather than only the first phrase
term. Rules without any accepted word can still be skipped, updating word/verse
positions from the existing summaries. Nearby expires old state by global word
position; Same verse clears state at verse boundaries. Chapter opens reset both.

`SearchBegin(..., mode)` is the current API; `SearchStart` defaults to Same verse.
Legacy `SearchStartMode(..., prefix_match)` remains a phrase iterator for older
experiments. Nearby result coordinates can precede the decoder's current verse;
a separate resume verse preserves correct continuation after such a result.

## Backend timing: Full versus Compact

KJV, pinned Neo 3.21 MAME, native frontend, original eight-bit Huffman lookup,
no selective verse accelerator. **Seconds, Next / Previous**, from word zero of
each stated verse. Every case includes fresh query/index/pruning initialization
and a cold decoder; no drawing, user typing or idle scheduling. ∅ means the range
was exhausted without a match. Every coordinate was checked against an independent
source-token oracle; timed loops made no LCD writes.

| Origin | Query | Mode | Full next / previous | Compact next / previous |
|---|---|---|---:|---:|
| Psalm 119:80 | faith works | Same verse | 0.734 / 0.147 ∅ | 21.195 / 11.440 ∅ |
| Psalm 119:80 | faith works | Exact phrase | 2.332 ∅ / 0.139 ∅ | 30.174 ∅ / 11.211 ∅ |
| Psalm 119:80 | faith works | Nearby | 0.729 / 0.147 ∅ | 21.040 / 11.346 ∅ |
| Psalm 119:80 | kingdom God | Same verse | 1.037 / 0.281 | 18.537 / 3.269 |
| Psalm 119:80 | kingdom God | Exact phrase | 9.292 ∅ / 5.751 ∅ | 45.307 ∅ / 41.149 ∅ |
| Psalm 119:80 | kingdom God | Nearby | 1.035 / 0.278 | 18.441 / 3.224 |
| Psalm 119:80 | Jesus Jesus | Same verse | 2.547 / 0.161 ∅ | 2.923 / 0.948 ∅ |
| Psalm 119:80 | Jesus Jesus | Exact phrase | 19.282 ∅ / 0.151 ∅ | 23.094 ∅ / 0.922 ∅ |
| Psalm 119:80 | Jesus Jesus | Nearby | 0.390 / 0.161 ∅ | 0.383 / 0.940 ∅ |
| Psalm 119:80 | be* bel* | Same verse | 1.227 / 1.040 | 1.596 / 1.008 |
| Psalm 119:80 | be* bel* | Exact phrase | 17.697 / 3.614 | 35.624 / 11.419 |
| Psalm 119:80 | be* bel* | Nearby | 1.095 / 0.965 | 1.234 / 0.665 |
| John 3:16 | faith works | Same verse | 0.435 / 0.455 ∅ | 3.780 / 28.525 ∅ |
| John 3:16 | faith works | Exact phrase | 2.039 ∅ / 0.441 ∅ | 13.099 ∅ / 27.968 ∅ |
| John 3:16 | faith works | Nearby | 0.433 / 0.452 ∅ | 3.756 / 28.307 ∅ |
| John 3:16 | kingdom God | Same verse | 0.256 / 0.245 | 2.433 / 0.224 |
| John 3:16 | kingdom God | Exact phrase | 2.210 ∅ / 12.937 ∅ | 14.050 ∅ / 72.182 ∅ |
| John 3:16 | kingdom God | Nearby | 0.255 / 0.244 | 2.413 / 0.223 |
| John 3:16 | Jesus Jesus | Same verse | 0.377 / 0.443 | 0.350 / 0.416 |
| John 3:16 | Jesus Jesus | Exact phrase | 12.035 ∅ / 7.502 ∅ | 14.697 ∅ / 9.423 ∅ |
| John 3:16 | Jesus Jesus | Nearby | 0.245 / 0.308 | 0.218 / 0.281 |
| John 3:16 | be* bel* | Same verse | 0.672 / 0.672 | 0.373 / 0.373 |
| John 3:16 | be* bel* | Exact phrase | 9.675 / 11.410 | 13.832 / 32.984 |
| John 3:16 | be* bel* | Nearby | 0.672 / 0.672 | 0.373 / 0.373 |

These are 48 operations per index, not exhaustive lists of every match. Full's
ranges are 0.147–2.547 s (Same verse), 0.139–19.282 s (Exact phrase), and
0.147–1.095 s (Nearby). Compact ranges are 0.224–28.525 s, 0.922–72.182 s, and
0.218–28.307 s respectively. These are selected-case ranges, not universal bounds.

The modes change the answer usefully. From John 3:16, `faith works` finds Romans
3:27 in Same verse/Nearby, although the query words occur in reverse order. Exact
phrase exhausts the range. `Jesus Jesus` finds John 4:50 in Same verse and John
4:1 in Nearby; there is no following adjacent phrase. Mere chapter co-occurrence
cannot establish phrase order, proximity or distinct repeated occurrences.

Compact's four-character buckets and eight-chapter groups can admit many false
candidate chapters. For example, the bucket shared by king/kingdom is much less
specific than the full word postings. This explains why the earlier short-prefix
navigation cases underestimated its worst multiword cost. Full is preferable for
this feature set; no enlarged index was introduced to compensate.

## Frontend scheduling adjustment and visible latency

The old reader did 50 ms of work per sparse idle callback. It now permits up to
**200 ms**, checking `IsKeyReady()` after every 64 search steps. A queued key ends
the slice, letting the event loop handle Esc. The timer cap is cooperative; one
64-step block can overrun it. Backend benchmark loops are unchanged and isolate
SearchBegin/From/Step, so frontend scheduling does not change the table above.

Native KJV **Enter-to-visible-result seconds**, including idle scheduling, chapter
construction and display, excluding typing. These use existing matching queries,
not the deliberately absent phrase variants from some backend cases:

| UI query | Full 50 ms | Compact 50 ms | Full 200 ms | Compact 200 ms |
|---|---:|---:|---:|---:|
| faith works | 3.604 | 35.585 | 1.657 | 9.725 |
| kingdom of God | 1.586 | 21.579 | 1.146 | 6.431 |
| God loved | 0.805 | 0.802 | 0.706 | 0.638 |
| be* bel* | 1.125 | 1.138 | 1.576 | 1.075 |

All start from John 3:16; respective modes are Same verse, Exact phrase, Nearby,
and Same verse. Idle phase alignment makes small differences noisy; the larger
improvements on longer searches are clear. The new mode does not promise that
every query is faster. An Esc key injected during an active Compact phrase scan
returned to an idle, stable original screen in **0.233 s**, including firmware
key handling and the harness stability condition. Cancellation was not simulated
by directly changing reader state.

MAME exposed that Tab arrives through the character path on this firmware;
handling only its raw-key path left the mode unchanged. The corrected reader
handles character Tab and reads shift modifiers there. Final tests validate both
cycling directions, preserved input, explicit-star typing and a cross-verse
Nearby result (`life God` across John 3:16–17 in the NKJV fixture as applicable).

## Production ROM/RAM

Native full-chapter production build, PROFILE=0, no test font/counters, optimized
native open and page commands. All values are bytes. Code/assets exclude Bible,
navigation, grammar summaries and the search index; fonts are included. A5 excludes
stack, firmware/dialog allocations, and the native chapter file.

| Index | Complete applet | App code/assets | A5 | Search metadata |
|---|---:|---:|---:|---:|
| Full | 1,293,366 | 23,102 | 3,118 | 252,739 |
| Compact | 1,168,544 | 23,102 | 3,118 | 127,917 |

Relative to the preceding directional reader, Full adds **1,290 ROM bytes** and
**132 A5 bytes**. The Bible/navigation resources and 252,739-byte full index are
unchanged. Full/Compact application code and A5 are identical. Compact saves
124,822 ROM bytes (121.9 KiB), entirely from search metadata/name alignment.

Streaming NKJV production grows from 1,333,968 to **1,335,238 ROM bytes** and from
3,732 to **3,862 A5 bytes**: +1,270 ROM / +130 A5. There is still no native chapter
file in Streaming. The shared matcher uses eight ten-byte assigned-occurrence
records plus scalar state on 68000. Assignment recursion is bounded by the eight
terms; compiler reports 52 bytes per recursive frame (a conservative nine-frame
budget is 468 bytes), additional to caller/firmware stack. This is not a measured
whole-stack high-water or a statement of total device RAM consumption.

## Acceptance and reproduction

- 1,071 source-oracle cases across Full, Compact and Scan, including every result
  tuple, exact/prefix terms, repeated and overlapping terms, both directions,
  strict/inclusive origins, unknown words and verse/chapter boundaries.
- 320 randomized matcher cases compare arbitrary overlapping acceptance sets
  against an independent full subset-DP matching oracle; five invalid wildcard
  inputs must be rejected.
- 168 legacy prefix/whole-word phrase tests still pass, including the research-only
  no-index matcher. No-index is not proposed as a normal installation option.
- 96 MAME backend operations and 36 deterministic UI checkpoints in their runs.
- After scheduling adjustment: 17 native Full, 18 native Compact (including active
  cancellation), and 36 production NKJV streaming mode/input/result checkpoints.
- Additional native 42-state and streaming 69-state regressions passed during this
  change; those preceded the frontend budget adjustment. Matching/decoder code is
  unchanged between the backend timing and final UI runs.

All tests use disposable flash/RAM, exact source/font bitmap expectations, cursor
geometry and stable controller samples. No screenshots were sent to a model or
used as a model-driven oracle. Failures, logs and raw records are retained. The
final streaming acceptance is `search-modes-stream-budget`; final native UI runs
are `search-modes-ui-full` and `search-modes-ui-compact`. [Structured results](search-modes-results.json)
retain timing, production and validation paths under `.research-work/bible-compression`.

From the workspace root, with a fresh output directory:

```sh
python3 betawise/tests/mame/asneo/check-bible-reader.py \
  --version KJV --search-index full --search-modes-bench --system-font --profile \
  --native-open-test direct --native-page-test --experiment huffman-prune \
  --output /tmp/bible-modes-full
```

Repeat with `compact`. Use `--search-modes-ui` instead of `--search-modes-bench`
for the final UI/cancellation fixture without all backend cases. For streaming:

```sh
python3 betawise/tests/mame/asneo/check-bible-stream.py \
  --version NKJV --production --no-terminal-font --search-modes \
  --output /tmp/bible-modes-stream
```

`check-search-modes.py` runs host oracles; `search_modes_cases.py` and the KJV-only
`SearchModesBench.h` define the profiling origins. `measure-search-builds.py`
produces sizes; `summarize-navigation.py` checks every timed result and LCD silence.
The normal KJV native and KJV/NKJV streaming binaries are rebuilt; NKJV streaming
is restored byte-identically to its final accepted production artifact.
