# Emulator readiness timing study (2026-11-19)

Historical result: expected-state predicates reduced emulated completion time
from 428.520 to 152.100 seconds for the AS3000 full EXTRA REPL; Neo history
from 60.600 to 26.883; Neo Logo graphics from 193.067 to 51.467 (51.367 with
the direct-RAM backend). See REPORT.txt for scope, failures and qualifications.
Keep physical key holds separate from completion waits and require explicit
expected text/pixels, independent cursor checks and bounded deadlines.

This directory preserves experimental scripts, job definitions, original
source snapshots, consolidated measurements and external input identities. The original report
predates the current workspace validation requirements. It is historical
evidence; its two-observation prototype is not today's acceptance harness.

## Reproduce

Run from the AlphaSmart workspace root. The historical scripts assume this
workspace is at /home/kirk/Projects/Alphasmart; adjust ROOT if relocated.
Install the ordinary SDK/MAME test dependencies and use disposable NVRAM.
Restore this directory's files into .research-work/timing-study-20261119/.
`init.py` copies current test sources, builds EXTRA images, and creates a
new Neo fixture; it replaces historical source snapshots, so use a fresh
experiment directory or preserve the snapshots separately first.

```sh
python3 .research-work/timing-study-20261119/init.py
python3 .research-work/timing-study-20261119/bench.py \
  .research-work/timing-study-20261119/baseline-jobs.json
python3 .research-work/timing-study-20261119/bench.py \
  .research-work/timing-study-20261119/ram-jobs.json
python3 .research-work/timing-study-20261119/analyze.py
```

Other *-jobs.json files preserve follow-up and failure experiments. The runner
writes runs/*/measurement.json, MAME logs and measurements.jsonl into the new output tree. Source filenames and external input identities are in metadata.json. Host wall times and load vary; compare
emulated durations and assertions. Reproducing exact historical behavior also
requires the source snapshot from this Git revision, matching ROMs and emulator build;
current sources may produce different numbers.

For current Neo acceptance use `python3 betawise/tests/mame/asneo/check.py`.
Apply the workspace AGENTS.md rules to any historical rerun: local deterministic
LCD decoding only, three identical cursor-free RAM samples via the firmware
API, exact glyphs/expected text, and independently authored graphics assertions.
Update historical runners to those rules before treating new results as passes.
Do not use screenshots or model inference as an oracle.

No timing-study LCD records, RAM, or assertion evidence were deleted in the
2026-11-24 cleanup. The separately retired USB per-packet traces are documented
under ../usb/mtp-prototype/. No emulator tests were rerun during cleanup.

Only the report, compact result tables, source snapshots and job definitions
are retained. Per-invocation timing streams and logs are regenerated. Snapshot
README links are adjusted for their retained repository location; metadata
continues to record the original pre-relocation source identities.
