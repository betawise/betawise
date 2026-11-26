#!/usr/bin/env python3
"""Summarize the compact binary/local-parser variant."""
import json
from pathlib import Path
import struct
from summarize import scan_timings

HERE = Path(__file__).resolve().parent
BUILD = HERE / 'build'


def main():
    sizes = []
    for variant in ('lean', 'tiny-binary', 'small-binary', 'direct-linear', 'direct-binary'):
        image = BUILD / variant / 'app/build/NKJV/BibleWise-NKJV.OS3KApp'
        rom, a5 = struct.unpack_from('>II', image.read_bytes(), 4)
        sizes.append(dict(variant=variant, rom=rom, a5=a5,
            rom_above_lean=rom-sizes[0]['rom'] if sizes else 0, application_rom=rom-1419827))
    suites = []
    for name in tuple(f'{variant}-{case}' for variant in ('direct-linear','direct-binary')
        for case in ('bench','kjv','headings','interactions')):
        directory = BUILD / name
        result = json.loads((directory / 'results.json').read_text())
        assert result['status'] == 'passed'
        suites.append(dict(name=name, status='passed', checkpoints=result['checkpoints'],
            timings=scan_timings(directory)))
    report = dict(release_sizes=sizes, suites=suites,
        checkpoints=sum(suite['checkpoints'] for suite in suites),
        scope='Research only. Actual lookup CPU time excludes observer work, chapter decode and layout. No new file data or offset tables; ten-byte cache retained.',
        gap_validation=json.loads((BUILD/'direct-gap-results.json').read_text()),
        resource_bytes=1419827,
        lifetime='FileBindState is called once per synchronous lookup with null output bindings. The returned pointer remains local; no editor/file mutation or allocation occurs while it is borrowed. Editor gap mapped directly, with a 15-byte seam buffer only for cross-gap records.')
    (BUILD / 'direct-results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Passed', report['checkpoints'], 'checkpoints')


if __name__ == '__main__':
    main()
