# Small contextual models: measured follow-up

Host research on the same pinned KJV corpus, 2026-11-20. All experiments are
local deterministic counting/encoding, without an LLM, network or device data.

The subsequent [native applet/MAME follow-up](mame-prototype.md) measures the
actual 68000 implementation. It supersedes the RAM estimates below with a
1,524-byte decoder workspace and 2,416-byte complete applet static allocation
(stack additional), plus timed display and seek results.

## Result

The best new self-contained container is **948,662 bytes** (926.43 KiB), a
**76,600-byte / 7.47% reduction** from the previous 1,025,262-byte best image.
It contains the entire source text, book navigation, chapter restart index,
all statistical tables and the compressed dictionary. Native decoder code,
fonts, UI and a full-text search index remain additional costs.

It uses **word symbols, previous-word context, arithmetic coding and a
Huffman-coded front dictionary**. It needs no phrase grammar. Each chapter
starts with fresh arithmetic and context state, so chapter seeking remains
independent. Every one of the 1,189 chapters was independently decoded in
reverse order and compared exactly against the source's normalized UTF-8 text.
The saved-container decoder does not receive the source or external models.

Best artifact in this workspace:
`.research-work/bible-compression/context-refined/word-ctx-65536-letters.bin`.
SHA-256:
`7d58ee4d28a80d530e1a1ca4c510cb55801ac387ba62927278ba4ab515a01c1c`.
A separate repeat run produced exactly the same container bytes and SHA-256.

## Comparison

All following totals include actual serialized resources and chapter framing.
Word/phrase rows use the Huffman-compressed dictionary except the historical
baseline. These are the best relevant tested settings, not universally optimal
choices for their algorithm families.

| Candidate | Complete bytes |
| --- | ---: |
| Previous best: 2,048 phrase pairs + Huffman + front dictionary | 1,025,262 |
| Byte contexts of up to three preceding bytes, ~128 KiB context budget | 1,217,062 |
| Previous-word model, initial simple selection, no exclusion | 971,047 |
| Up to two preceding words, initial selection, no exclusion | 983,584 |
| 2,048 phrase pairs + initial contextual arithmetic model | 971,293 |
| 8,192 trained / 8,140 reachable phrase pairs + arithmetic | 968,642 |
| 16,384 trained / 16,188 reachable phrase pairs + arithmetic | 983,932 |
| Previous-word model, exact wide base counts, initial selection | 994,945 |
| Refined previous-word model, 32 KiB context budget + exclusion | 957,748 |
| **Refined previous-word model, 48,900 actual context bytes + exclusion** | **948,662** |
| Refined context model on 2,048 phrase pairs + exclusion | 970,500 |

Word two-context selection was scored approximately against the base model,
not against its eventual shorter-context fallback. It did not beat the simpler
one-context model in these tests; this does not rule out a better PPM or other
higher-order design. Enlarging a model or grammar reduced the payload in some
cases while increasing total storage. All tables have been counted.

The best result is still well above 500 KB. These experiments do not establish
a lower bound or prove what is possible with other context models or grammars.

## Best image byte accounting

| Component | Bytes |
| --- | ---: |
| Arithmetic-coded chapter payloads | 800,411 |
| Statistical model, including dense base CDF and context tables | 77,746 |
| Front dictionary, letter-Huffman codebook and block directory | 50,120 |
| Chapter records, 16 bytes each | 19,024 |
| Outer header and compact book metadata | 1,345 |
| Arithmetic-container header | 16 |
| **Total** | **948,662** |

The statistical model includes a 12-byte model header, 28,834 bytes of base
cumulative frequencies and **577 sparse context models occupying 48,900 bytes**.
There are 14,417 terminal IDs. A context selects up to 512 likely followers;
all other words are represented by an ESC followed by the base model.

On ESC, the base model excludes the followers the context already ruled out.
This prevents spending probability on impossible choices. The refined selector
scores that conditional fallback, its actual quantized base distribution and
the full serialized table cost. It tries follower sets of 4, 8, 16, 32, 64,
128, 256 and 512 entries, rejects nonpaying contexts and fits the chosen
contexts into an explicit budget. Training statistics are computed directly
from this exact corpus; all resulting tables are in the image.

The contexts are not adaptive during reading. The only contextual state is
the preceding decoded word ID; the global ROM tables do not change at runtime.

## Dictionary letters

The original front-coded dictionary was 77,420 bytes. Huffman-coding its
prefix-byte/suffix-byte records in independent blocks reduces it to **50,120
bytes**, including the codebook and an eight-byte directory entry for each
of 902 blocks. Thus lookup does not require decompressing all earlier words.

Each block holds up to 16 front-coded word entries. The largest decoded block
is **148 bytes**. The experiment independently seeks each compressed block,
decodes it, rebuilds the exact original front dictionary, then verifies word
and chapter reconstruction. Prefix lengths refer to UTF-8 bytes; they are not
Unicode character counts.

This implements the suggestion to Huffman-code the dictionary's letters while
retaining direct access. It compresses prefix-length bytes as well as suffix
spellings. This experiment did not implement a DAWG or neural model.

## Decoder memory and speed implications

All cumulative frequencies, sparse context records and spellings can remain
in ROM, addressed through relative offsets. The decoder needs arithmetic
interval state and the previous word ID, rather than an adaptive model or LZ
sliding window in RAM. A target implementation can binary-search the sorted
context directory and cumulative arrays directly in ROM.

For the best model, exclusion has up to **512 followers**. The initial algorithm
built cumulative removed frequencies in a scratch array: **2,048 bytes** at
four bytes per follower. The subsequent RAM review reduced that to **1,024
bytes** at two bytes per follower, since the best model's base CDF total cannot
exceed 65,535. Wider experimental base CDFs still use four-byte scratch entries.
This changes no encoded bits or probability calculations. Add the small dictionary-block buffer, word buffers,
Huffman summaries, arithmetic state and UI/layout storage. This is a design
budget, not a measured target allocation. A smaller-follower or no-exclusion
variant trades a few more ROM bytes for less scratch/work. One could scan
followers instead of building this scratch array, at additional CPU cost.

The host C++ verifier uses `std::map` and vectors to simplify measurements;
its allocation behavior is not a native Neo implementation. In particular,
the dictionary verifier can materialize the entire dictionary on the host;
the proposed target lookup decodes only the chosen 148-byte-or-smaller block.
There is no claim that this host program currently operates within Neo RAM.

Arithmetic coding uses 32-bit intervals with 64-bit intermediate multiplication
and division. The Neo's 68000 will pay for software arithmetic. Host timings
recorded in the JSON are not predictive of Neo speed. Before choosing this
over Huffman, implement the small native decoder and measure chapter jumps,
page rendering, stack and scratch use on the target. A 7.47% ROM saving may or
may not justify that CPU cost; the previous Huffman format remains a simpler
candidate.

Chapter seeking is still direct. Seeking a particular verse requires decoding
from its chapter restart and counting explicit LF boundaries. No constant-time
per-verse access is claimed.

## Formats and validation

The new code is `context_models.py` plus `context_codec.cpp`. The C++ backend
implements static integer arithmetic encoding/decoding and independent chapter
seeks; Python trains models, serializes resources and checks the expanded text.

`KJVCTX01` uses the original front dictionary; `KJVCTX02` uses the independently
letter-Huffman-coded front dictionary. Its 64-byte outer header contains eight
big-endian uint32 fields after the magic: book metadata bytes, terminal count,
dictionary bytes, phrase rule count, dataset kind, arithmetic-container bytes,
normalized text bytes and chapter count. Sections are book metadata, dictionary,
phrase pairs and the arithmetic container. Dataset kinds 0..4 are byte, word,
phrase, word-two-context and phrase-two-context, respectively.

`CTXAR001` contains a uint32 model-byte count and chapter count, then the model,
16-byte chapter records and payloads. Records hold byte offset, compressed
length, decoded symbol count and FNV-1a hash over big-endian uint16 symbol bytes.
These new records use a symbol hash, not the original format's text CRC-32.

The model has uint32 alphabet size, order/flags and context count. The order is
the low byte; flag 256 means a wide uint32 base CDF and flag 512 enables
one-context exclusion. Otherwise base cumulative frequencies are uint16. Each
12-byte context record contains key, entry-relative byte offset, entry count
and cumulative total. Entries contain uint16 symbol ID and cumulative end.
The ESC ID equals the alphabet size. Context keys are seeded with 1, then
extended in chronological order by `key*(alphabet+1)+symbol+1`.

The `KJVCTX02` dictionary starts with uint16 block and alphabet counts, then
byte symbols in sorted order and their one-byte Huffman lengths. Each eight-byte
block record contains a uint32 payload offset, uint16 compressed byte length
and uint16 decoded byte length. Block payloads follow the directory. It decodes
to the prefix-length/suffix records of the original front dictionary.

Production hardening and whole-container integrity/version handling are still
required. The experiment asserts exact decoder output, every source chapter
and dictionary block, and deterministic repeat hashes. It is not a security
review of malformed-input handling.

Five backend regression tests passed: uniform binary coding with an independently
known bit cost; zero-frequency/single-symbol cases; sparse escapes with/without
exclusion and wide frequencies; large alphabets and multilevel fallback; and
512-entry exclusion sets. A changed payload byte was rejected by its symbol
hash. The standalone decode test receives no original source or training model.

## Reproduce

The original source and baseline grammar paths below are generated/obtained as
described in [the baseline report](README.md#reproduce). A host C++17 compiler
and Python standard library are sufficient. From the workspace root:

```sh
python3 betawise/research/bible-reader/test_context.py
python3 betawise/research/bible-reader/context_models.py \
  .research-work/bible-compression/kjv.json \
  --grammar .research-work/bible-compression/results/kjv-front-grammar.bin \
  --output .research-work/bible-compression/context-refined \
  --datasets word phrase --exclusion --max-followers 512 \
  --budgets 8192 32768 65536 131072
```

The best file is `word-ctx-65536-letters.bin`; 131072 yields identical bytes
because all paying contexts already fit at 65536. Run into a different output
directory to repeat independently. For the main comparison, omit exclusion and
the follower override and select `--datasets byte word word2 phrase`; default
budgets are 0, 8192, 32768 and 131072. `--wide-base` measures exact base counts
with uint32 CDFs. `--extend-phrases 8192` or `16384` with `--datasets phrase`
repeats the larger-grammar comparisons, including pruning unreachable rules.

`context-results.json` in this research directory consolidates the baseline,
wide-CDF, larger-grammar and refined-context results with their parameters and
artifact hashes. Intermediate artifacts remain under `.research-work`.
`context-validation.json` records the independent repeat and test outcomes.

No firmware, applet installation or saved session was changed. No display was
used as a validation oracle. Native Neo tests are pending a native decoder.
