#!/usr/bin/env python3
"""Summarize exact-validated marker-seek experiments and release sizes."""
import json
from pathlib import Path
import struct
from summarize import scan_timings

HERE = Path(__file__).resolve().parent
BUILD = HERE / 'build'


def measurements(name):
    directory = BUILD / name
    result = json.loads((directory / 'results.json').read_text())
    assert result['status'] == 'passed'
    rows = scan_timings(directory)
    trace = json.loads((directory / 'timings.json').read_text())
    for index, row in enumerate(rows, 1):
        observing = False
        start = None
        total = 0
        for event in trace:
            if event['check'] != index:
                continue
            phase = event['phase']
            if phase == 712:
                observing = True
            elif phase == 713:
                observing = False
            elif phase == 716:
                start = event['time']
            elif phase == 717:
                assert start is not None
                if not observing:
                    total += 1000 * (event['time'] - start)
                start = None
        row['marker_search_ms'] = total
    return dict(name=name, status=result['status'], checkpoints=result['checkpoints'], rows=rows)


def main():
    sizes = []
    for variant in ('fast', 'binary', 'marker', 'marker-bmh'):
        image = BUILD / variant / 'app/build/NKJV/BibleWise-NKJV.OS3KApp'
        rom, a5 = struct.unpack_from('>II', image.read_bytes(), 4)
        sizes.append(dict(variant=variant, rom=rom, a5=a5,
            rom_above_linear=rom-sizes[0]['rom'] if sizes else 0))
    suites = [measurements(name) for name in ('marker-bench', 'marker-bmh-bench')]
    validations = []
    for name in ('marker-kjv', 'marker-headings', 'marker-bmh-kjv', 'marker-bmh-headings'):
        result = json.loads((BUILD / name / 'results.json').read_text())
        assert result['status'] == 'passed'
        validations.append(dict(name=name, status=result['status'], checkpoints=result['checkpoints']))
    report = dict(release_sizes=sizes, suites=suites, validations=validations,
        checkpoints=sum(item['checkpoints'] for item in suites+validations),
        scope='Research only. Actual lookup CPU time excludes test observers; no whole-chapter decoding or layout included. Both marker variants retain neighboring boundary reconstruction and the ten-byte cache. No added file bytes. BMH adds a transient 256-byte stack table.',
        prior_comparisons='fast-bench-nkjv and binary-bench-nkjv timings use the same seek algorithm before the unrelated formatting-write batching change; release sizes above were rebuilt with that change.')
    (BUILD / 'marker-results.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(sizes, indent=2))


if __name__ == '__main__':
    main()
