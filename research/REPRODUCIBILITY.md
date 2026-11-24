# Reproducing retained research

Keep conclusions, scope/limitations, input identities, reproducible probe
sources, compact result tables and notable illustrative figures. Generated
logs, packet streams, raw RAM/LCD captures, per-run geometry dumps, duplicated
diagnostics and deletion inventories do not belong in this historical research
snapshot. Generate them again in disposable output directories when validating
new work. Authored test inputs and independently reviewed expected references
remain inputs, rather than disposable outputs.

## Source baseline

The parent source anchor is Betawise commit
`b8c5e945749b27f9eb40d4f1987f325089bce339`. Obtain the research sources from
the commit introducing this guide:

```sh
git log --diff-filter=A --format=%H -- research/REPRODUCIBILITY.md
```

Use that research commit, rather than the parent alone. The source consolidation
includes the frozen experimental reader and historical probe sources. Optional
SDK and shared Neo-reader edits needed by some probes are captured in
`reproduction-support.patch`; their identity and sibling repository revisions
are in `reproduction-baseline.json`. Apply the overlay only to a fresh checkout
of this research snapshot, with `git apply --check` first. It is a source input,
not a dump of generated validation output or a separately qualified SDK release.
The matching MAME revision and overlay are documented in the OS3K reproduction
guide. Manager transactions additionally use the recorded neotools revision.

Provide the original private ROM/applet/installer inputs at their documented
workspace paths and verify their hashes. No saved user session and no retained
`.research-work` output is a reproduction input. Topic runners create fresh
fixtures; where a prototype requires a logical-file fixture, the topic explains
how to capture a new disposable input before starting the experiment.

## Results and validation

Git commits and paths identify repository source files; do not duplicate
those identities in source-hash inventories. Keep hashes for original external
firmware, applet packages and downloadable tools where exact input bytes matter.
Generated binary, disassembly, log and capture hashes are not reproduction
inputs; regenerate these outputs from the recorded sources and commands.
Historical run-directory labels identify measurements, not required retained
directories.

Dates and result tables describe historical observations. Repeating a workload
does not reproduce incidental host timing, timestamps, compiler diagnostics,
or a user's exact browsing sequence. Preserve notable failures and limitations:
interactive dialog behavior remains incomplete, and synthetic transport tests
do not certify physical hardware. Raw captures can be produced and inspected
locally during active validation without committing them to this snapshot.

For Neo execution, follow workspace AGENTS.md: exact local LCD/font/pixel
assertions, independent cursor checks, firmware-mediated cursor hiding, three
identical RAM samples, bounded predicates and disposable state. Do not use
screenshots or a model as the screen-validation oracle. Verifiers accepting an
output directory operate on a newly generated run; archived output is not
required. Source and summary syntax/link checks do not rerun historical emulator
acceptance suites.
