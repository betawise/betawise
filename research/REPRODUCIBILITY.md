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

For current reproduction, use the commit that removes the support overlay,
or a later revision. Find the integration anchor with:

```sh
git log --diff-filter=D --format=%H -- research/reproduction-support.patch
```

That commit includes the frozen research sources and the SDK API corrections;
its parent `7758f4f` supplies the graphics and shared 65-row Neo-reader support.
No Betawise overlay is needed. Source identities and sibling repository
revisions are recorded in `reproduction-baseline.json`.

For an exact historical source snapshot, the original research commit above
still contains its frozen support overlay in Git history. Apply that overlay
only to that historical checkout, with `git apply --check` first; do not apply
it to the integrated source. The line implementation has since been replaced
by the tested run-slice version. Historical result tables are observations of
the recorded sources, not claims of identical timings on the newer code.
The matching MAME revision and its separate overlay are documented in the OS3K
reproduction guide. Manager transactions additionally use the recorded
neotools revision.

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
