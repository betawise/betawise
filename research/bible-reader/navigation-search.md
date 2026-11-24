# Directional search: full, compact, scan and zero metadata

Measured 2026-11-23 on pinned Neo 3.21 MAME, KJV, eight-bit phrase Huffman.
No wider-table or selective verse acceleration. All four variants have identical
Bible compressed bytes and query semantics. The reader now searches from its
reading cursor and stops at one occurrence; it does not populate an exhaustive
result list.

## Book/chapter menus from the index

Full is the original packed word/chapter index, enhanced for prefixes, not the
four-character grouping experiment. For a single query word prefix, unioning the
accepted words' postings gives an **exact list of matching chapters**. Book names
and chapter numbers already exist in navigation metadata. No Bible chapter text
needs decoding to build such a menu; query dictionary lookup still reads a few
front-compressed spellings. Its query setup in these God cases is about 0.15 s.

For phrases, the intersection proves only that each term occurs somewhere in the
chapter, not that they are adjacent or in one verse. These candidate chapters need
verification, either before listing or lazily after selection. Compact also needs
verification for single words: it has prefix buckets over eight-chapter groups.
A new book/chapter result menu is not implemented in this change.

## Implemented navigation

Both native and streaming frontends now:

- Begin a new Find at the current cursor, including its current word.
- Use Cmd+Find for the next occurrence and Shift+Cmd+Find for the previous one;
  Cmd+G / Shift+Cmd+G remain aliases. Native N/P aliases are retained; streaming
  N/P still page through text.
- Search relative to manual scrolling and verse jumps, rather than resuming an
  unrelated old scan position. Previous is no longer limited to 32 remembered hits.
- Preserve case-insensitive prefixes, punctuation handling, internal apostrophes,
  overlapping phrases and verse boundaries. Stop at Bible boundaries without wrap.
- Stop immediately after one result and place the caret on its first word.
  The 50 ms cooperative work slices and Esc cancellation remain.

Forward navigation can continue the live decoder when the cursor is still on its
last forward hit. Otherwise it starts at the current chapter and discards earlier
hits. Backward navigation scans each candidate chapter forwards, keeps the latest
qualifying occurrence, and moves to an earlier chapter only if necessary. It does
not scan from Genesis for every Previous. No result history or whole-Bible decoded
buffer is retained. The obsolete 32-hit arrays were removed.

## Four search policies

Full, Compact and Scan retain the word-ID matcher and grammar pruning. Scan has
no occurrence postings, but its 49,981-byte lexicon/map converts query prefixes
and compressed spelling variants into normalized word IDs. All chapters are
candidates for a known prefix.

`SEARCH_INDEX=none` is the new **true zero-search-metadata** option. It stores no
query lexicon, normalization map, postings, or search grammar summaries. It streams
`BibleReadByte` into character KMP matchers, checks word-start alignment, and uses
word-level Shift-And to combine accepted prefixes into phrases. Ordinary exact
KMP failure links alone are unsafe for overlapping word-prefix sets; this keeps
the same semantics as the other options. Tokenization is bounded state, not a
chapter buffer. The normal text dictionary and phrase grammar remain necessary
to decompress/display the Bible; they are not additional search metadata.

## Navigation latency

**Seconds, next / previous**, each from word zero of the stated verse. Each case
starts a fresh query, so it includes setup and a cold decoder; subsequent Next
operations can reuse both query setup and decoder state. Timings are emulated
backend service, excluding display, keyboard and idle scheduling. No LCD writes
occur during the timed loops.

| Origin | Query prefix | Full | Compact | Scan | None |
|---|---|---:|---:|---:|---:|
| Genesis 24:20 | God | 0.228 / 0.228 | 0.204 / 0.204 | 0.191 / 0.191 | 0.326 / 0.326 |
| Genesis 24:20 | believ | 0.210 / 0.189 | 0.684 / 0.225 | 2.472 / 1.004 | 9.313 / 3.568 |
| Genesis 24:20 | Methus | 0.105 / 0.167 | 1.621 / 0.362 | 30.912 / 1.657 | 127.198 / 6.192 |
| Psalm 119:80 | God | 0.349 / 0.401 | 0.325 / 0.377 | 0.312 / 0.364 | 0.771 / 0.980 |
| Psalm 119:80 | believ | 0.479 / 0.449 | 0.556 / 0.433 | 1.900 / 0.427 | 6.787 / 1.185 |
| Psalm 119:80 | Methus | 0.103 / 0.216 | 0.103 / 0.756 | 45.298 / 15.348 | 177.455 / 60.017 |
| John 3:16 | God | 0.184 / 0.184 | 0.160 / 0.160 | 0.147 / 0.147 | 0.152 / 0.152 |
| John 3:16 | believ | 0.176 / 0.176 | 0.160 / 0.160 | 0.154 / 0.154 | 0.159 / 0.159 |
| John 3:16 | Methus | 0.101 / 0.226 | 0.101 / 0.765 | 14.427 / 46.004 | 54.824 / 181.833 |

There is no following Methus match after the Psalm or John origins; those Next
times measure reaching the end with no match. The previous match there is in
1 Chronicles 1:3. The next Methus after Genesis 24 is also 1 Chronicles 1:3;
the previous is Genesis 5:27. Exact expected (chapter, verse, word) tuples for
all cases are preserved in the structured results.

God near John 3 is slightly faster without the index because it is nearby and
avoids index setup. This does not generalize to missing or distant matches.
Full's worst case here is 0.479 s, Compact's 1.621 s, Scan's 46.004 s and None's
181.833 s. These are the selected cases, not worst-case guarantees for all queries.

## Production ROM and A5

Native full-chapter front end, PROFILE=0, no test font, optimized native open/page.
All sizes below are **bytes**. Separate production builds exclude benchmark code.
Common Bible/navigation resources are 1,017,525 bytes in the first three options
and 1,011,381 in None, which also drops 6,144 search grammar-summary bytes.
Application code/assets exclude all these resources and search metadata; they
include fonts. A5 excludes stack, OS/dialog allocations and native chapter files.

| Option | Search metadata | Complete applet | App code/assets | A5 |
|---|---:|---:|---:|---:|
| Full | 252,739 | 1,292,076 | 21,812 | 2,986 |
| Compact | 127,917 | 1,167,254 | 21,812 | 2,986 |
| Scan | 49,981 | 1,089,318 | 21,812 | 2,986 |
| None | 0 | 1,030,174 | 18,793 | 2,744 |

Compact saves 124,822 bytes (121.9 KiB) relative to Full; Scan saves 202,758 bytes
(198.0 KiB). None saves a further 59,144 bytes (57.8 KiB) and 242 A5 bytes against
Scan: the lexicon/map, grammar summaries and some matching code are removed.
The full search object is 822 bytes; the no-index object is 644 bytes. They are
already included in A5. The no-index applet is smaller than 1 MiB, but its slow
rare/no-following searches are a substantial tradeoff for that final saving.

The previous published production A5 was 3,168 bytes. Full is now 2,986 because
removing the old history arrays more than offsets the new directional state.
Streaming uses the same backend, but these complete-app/A5 totals describe the
native frontend only; they must not be reused as streaming totals.

## Recommendation

Keep Full as the default for predictable Find Next/Previous latency. Compact is
a strong ROM-saving alternative: about 122 KiB less and all tested operations
below 1.7 s backend time. Scan is usable if the user accepts longer rare searches.
I would not choose the zero-metadata matcher merely to save the last 58 KiB:
it can spend minutes proving that no later match exists. A full match-count or
all-results sweep is unnecessary for ordinary reader navigation.

## Validation and reproduction

- 18 exact directional result checks and eight deterministic source/font bitmap,
  cursor and stable-DDRAM checkpoints for each MAME search option: 72 backend
  cases and 32 checkpoints. Disposable flash/RAM only; no model/vision oracle.
- Final production native KJV: 42 deterministic UI checks; final production
  streaming NKJV: 69, including cursor/selection, copied text/citations, fonts,
  modified Find, manual jumps and search exhaustion/backwards navigation.
- `check-navigation.py`: 576 host cases across four options, validating strict and
  inclusive origins, three successive hits, direction reversal through fresh
  origins, overlaps, unknown terms and both ends of the Bible against source text.
- `check-prefix-search.py`: 168 host prefix/whole-word cases, all occurrence tuples,
  including the true no-index matcher.
- Whitespace cleanup after measurement rebuilt byte-identically to the production
  Full and None artifacts. Final NKJV streaming demo matches its accepted binary.

From the workspace root, use a fresh output directory:

```sh
python3 betawise/tests/mame/asneo/check-bible-reader.py \
  --version KJV --search-index full --navigation-bench --system-font --profile \
  --native-open-test direct --native-page-test --experiment huffman-prune \
  --output /tmp/bible-navigation-full
```

Repeat with `compact`, `scan`, or `none`. `measure-search-builds.py` produces
production sizes for all four; `summarize-navigation.py` verifies every timed
result and absence of LCD writes before emitting tables. The benchmark origins
are shared by `navigation_cases.py` and the KJV-only profiling `SearchBench.h`.

Raw records, logs, source-based expected results and private test images are under
`.research-work/bible-compression/navigation-*`. [Structured results](navigation-search-results.json)
retain the exact run and production artifact paths. The final accepted UI runs
are `navigation-native-final` and `navigation-stream-final`.
