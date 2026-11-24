# Typing work and measured emulator time

The original prototype read the complete source, backed up encoded bytes, called
native scanning repeatedly to map the caret, deleted/reinserted the complete
formatted document, refreshed layout, read debug source/clipboard state, and
requested another redraw after each consumed edit. This was unnecessary work.

Current implementation:

* Ordinary appended letters update the source/style cache directly. Its guard
  checks the file, view mode, caret location, selection and expected font state.
* Non-append edits and syntax/prefix changes use a bounded C decoder. It reads
  the native file once, skips its explicit gap, and recognizes only the supported
  ASCII/style/escaped-bullet/soft-space representation.
* Existing per-character region flags and generated bullets are compared with
  the desired result. Matching styles require no rewrite or layout refresh.
* A formatting change can still rebuild the bounded document. That slow path is
  not yet an active-line-only patcher or fully incremental parser.
* Native editing already draws ordinary changes. The companion requests another
  redraw only after changing formatting or performing the empty-list exit edit.
* Source snapshots use the existing cache; clipboard data is read only for Copy.

## Measurement

MAME write taps record emulated time when the guest writes phase markers before
native editing, after native editing, after Markdown processing and before return.
Tests seed the same `word ` content at lengths 50, 500 and 1,500 through native
text routines. They then type `a`, followed by `bc`. First-key and steady-key
figures are separate; the steady figure is the mean of two actual letter events.
These are callback durations, not host wall-clock time or complete key-to-LCD
latency measurements. Host execution speed does not change emulated timestamps.

| Source characters before test | Original key (ms) | Current first key (ms) | Current steady key (ms) | Markdown portion, steady (ms) |
| ---: | ---: | ---: | ---: | ---: |
| 50 | 68.45 | 21.59 | 19.13 | 0.25 |
| 500 | 410.32 | 51.91 | 31.05 | 0.42 |
| 1,500 | 1,115.69 | 93.47 | 31.84 | 0.42 |

The original measurement includes the same phase instrumentation. At length
1,500 the new steady-key native-edit portion is about 31.4 ms. Counters separately
assert that the two steady keys perform **zero whole-file decodes, parses or
rewrites**, rather than inferring this only from elapsed time. First keys after
fixture seeding intentionally start with an uncached document; structural edits
have not been claimed to have steady-key performance.

Reproduce using new output paths:

```sh
python3 betawise/research/markdown/check-editor.py --live --case profile --output /tmp/neo-profile-new
python3 betawise/research/markdown/summarize-profile.py \
  /tmp/neo-markdown-profile-baseline /tmp/neo-profile-new /tmp/profile-comparison.json
```

The original guest applet and its source snapshot are retained with the baseline
run. `timings.json`, `perf-*.bin`, source checks, installed images, logs and hashes
are retained with each run. Summary:
`.research-work/cowriter-integration/typing-profile-v4.json`.

## Power

These measurements show a large reduction in processing work and active time;
they do not measure current, watts or battery life. MAME does not supply a physical
Neo power model. Establishing energy per key requires a hardware current trace
under controlled conditions, including idle and native AlphaWord comparisons.
No battery-life multiplier is inferred from the timing ratio.
