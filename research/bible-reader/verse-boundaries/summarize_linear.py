#!/usr/bin/env python3
"""Record the single-pass linear seek comparison and deterministic validation."""
import json
from pathlib import Path
import struct
from summarize import scan_timings

HERE = Path(__file__).resolve().parent
BUILD = HERE / 'build'


def main():
    sizes = []
    for variant in ('fast', 'linear', 'lean', 'binary', 'marker', 'marker-bmh'):
        image = BUILD / variant / 'app/build/NKJV/BibleWise-NKJV.OS3KApp'
        rom, a5 = struct.unpack_from('>II', image.read_bytes(), 4)
        sizes.append(dict(variant=variant, rom=rom, a5=a5,
            rom_above_fast=rom-sizes[0]['rom'] if sizes else 0))
    suites = []
    for name in ('linear-bench', 'linear-kjv', 'lean-bench', 'lean-kjv', 'lean-headings', 'lean-interactions'):
        directory = BUILD / name
        result = json.loads((directory / 'results.json').read_text())
        assert result['status'] == 'passed'
        suites.append(dict(name=name, status='passed', checkpoints=result['checkpoints'],
            timings=scan_timings(directory)))
    report = dict(release_sizes=sizes, suites=suites,
        checkpoints=sum(suite['checkpoints'] for suite in suites),
        pattern_probe=dict(construction_text_bytes=184, comparison_wrapper_text_bytes=10,
            caveat='Isolated -Os object code, not marginal applet ROM. Excludes shared arithmetic and memcmp support and GOT. Applet inlining differs.'),
        scope='Research only. Lookup CPU timings exclude test observers, chapter decode and screen layout. No file index or added markers. All scan variants retain a ten-byte last-verse cache.')
    (BUILD / 'linear-results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Passed', report['checkpoints'], 'checkpoints')


if __name__ == '__main__':
    main()
