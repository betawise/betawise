#!/usr/bin/env python3
"""Summarize the trimmed binary/local-parser variant."""
import json
from pathlib import Path
import struct
from summarize import scan_timings

HERE = Path(__file__).resolve().parent
BUILD = HERE / 'build'


def main():
    sizes = []
    for variant in ('lean', 'binary', 'compact-binary', 'tiny-binary'):
        image = BUILD / variant / 'app/build/NKJV/BibleWise-NKJV.OS3KApp'
        rom, a5 = struct.unpack_from('>II', image.read_bytes(), 4)
        sizes.append(dict(variant=variant, rom=rom, a5=a5,
            rom_above_lean=rom-sizes[0]['rom'] if sizes else 0))
    suites = []
    for name in ('tiny-binary-bench', 'tiny-binary-kjv', 'tiny-binary-headings', 'tiny-binary-interactions'):
        directory = BUILD / name
        result = json.loads((directory / 'results.json').read_text())
        assert result['status'] == 'passed'
        suites.append(dict(name=name, status='passed', checkpoints=result['checkpoints'],
            timings=scan_timings(directory)))
    report = dict(release_sizes=sizes, suites=suites,
        checkpoints=sum(suite['checkpoints'] for suite in suites),
        scope='Research only. Actual lookup CPU time excludes observer work, chapter decode and layout. No new file data or offset tables; ten-byte cache retained.',
        rejected_release_candidates={'uint16_record_rom':1458726,'scalar_return_rom':1458712,'noinline_marker_rom':1458760,'noinline_marker_a5':1576},
        tradeoff='Generic binary anchoring also runs for verse 1; cold first-verse lookup is slower than the linear special case. Caret lookup shares the binary routine and seeks one additional preceding verse for heading context.')
    (BUILD / 'tiny-binary-results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Passed', report['checkpoints'], 'checkpoints')


if __name__ == '__main__':
    main()
