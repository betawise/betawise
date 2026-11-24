# AlphaWord file/editor binding results

On original Neo 3.21 AlphaWord, all four file-record output bindings at
24/28/2C/30 remained zero in six states: empty, typed, selected, Home, File 2
and reopened File 1. Caret/anchor/selection state was independent of the file's
sequential position. results.json retains that compact table; the parent
report explains the version-limited conclusion. No raw RAM or log is required
to understand the finding.

With the hashed private ROM/AlphaWord, SDK and MAME dependencies from the
common reproduction guide, run from the workspace root:

```sh
python3 betawise/research/markdown/file-bindings/run.py /tmp/bindings-new
python3 betawise/research/markdown/file-bindings/verify.py /tmp/bindings-new
```

The generator prepares disposable state and emits raw records and assertions;
the verifier checks those freshly generated records. No saved user session or
screen-rendering inference is used. Generated files and logs stay in the new
output directory rather than in the source snapshot.
