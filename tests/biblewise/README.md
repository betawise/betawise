# BibleWise validation

All tests use local source/glyph assertions; native tests use disposable flash
and RAM. Generated executables, reports and evidence belong under `build/`.
Historical aggregate snapshots were moved to `build/history/` and are not
committed or treated as current release measurements.

Run from the repository root, choosing fresh output directories:

```sh
python3 -m unittest discover -s tests/biblewise -p 'test_*.py'
python3 tests/biblewise/check.py --output tests/biblewise/build/host
python3 tests/biblewise/check-formatting.py --version kjv --output tests/biblewise/build/format-kjv
python3 tests/mame/asneo/check-biblewise.py --case family-picker --output tests/biblewise/build/picker
python3 tests/mame/asneo/check-biblewise.py --case default-font --vendor-font vlarge --output tests/biblewise/build/default
```

Each report-producing runner writes its `results.json` inside the supplied
output directory. Full native suites and optional experiments are described in
[the applet manual](../../applets/BibleWise/README.md) and
[reader research](../../research/bible-reader/README.md).

The italic comparison reports can be regenerated from retained raw suite
folders with `research/bible-reader/smallcaps-italics/summarize.py` and
`compare_followup.py`. Their default outputs are in the helpers' own `build/`
directory. Reports requiring historical evidence are not recreated from current
captures or used as test oracles.
