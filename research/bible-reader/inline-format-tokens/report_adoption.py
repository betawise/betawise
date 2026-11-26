#!/usr/bin/env python3
"""Collect accepted production/reference ROM, A5, native output and CPU timings."""
from pathlib import Path
import hashlib
import json
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
APP = ROOT / 'applets/BibleWise'
BUILD = HERE / 'build'
FILES = ['container.bin', 'search.bin', 'verses.bin', 'pruning.bin']
SUITES = ['bench-sidecar-kjv', 'bench-sidecar-nkjv', 'bench-inline-kjv', 'bench-inline-nkjv',
    'accept-reader-kjv', 'accept-usage-nkjv', 'accept-vendor-small-nkjv', 'accept-partial-copy-kjv']


def measure(app, version, sidecar):
    stem = 'BibleWise' + ('' if version == 'KJV' else '-' + version)
    image = (app / 'build' / version / (stem + '.OS3KApp')).read_bytes()
    rom, a5 = struct.unpack_from('>II', image, 4)
    assert rom == len(image)
    data = app / 'build/data' / version.lower()
    names = FILES + (['styles.bin', 'layouts.bin'] if sidecar else [])
    resources = {name: (data / name).stat().st_size for name in names}
    aligned = sum(size + (size & 1) for size in resources.values())
    frame = next(int(line.split('\t')[1]) for line in
        (app / 'build' / version / 'Formatting.su').read_text().splitlines()
        if ':BibleFormatChapter\t' in line)
    return dict(rom_bytes=rom, a5_bytes=a5, resources=resources,
        aligned_resource_bytes=aligned, application_rom_bytes=rom - aligned,
        formatter_stack_frame_bytes=frame, sha256=hashlib.sha256(image).hexdigest())


def chapter_bytes(path, i):
    raw = (path / f'chapter-{i:02}.bin').read_bytes()
    start, end = struct.unpack_from('>II', (path / f'editor-{i:02}.bin').read_bytes(), 40)
    return raw[:start] + raw[end:]


def timings(path):
    checks = json.loads((path / 'checks.json').read_text())
    trace = json.loads((path / 'timings.json').read_text())
    rows = []
    for i, check in enumerate(checks, 1):
        events = [event for event in trace if event['check'] == i]
        def span(first, last):
            start = next((event['time'] for event in events if event['phase'] == first), None)
            end = next((event['time'] for event in events if event['phase'] == last
                and start is not None and event['time'] > start), None)
            return round(1000 * (end - start), 6) if end is not None else None
        rows.append(dict(name=check['name'], decode_write_ms=span(3, 2), load_display_ms=span(1, 4)))
    return rows


def main():
    suites = []
    for name in SUITES:
        result = json.loads((BUILD / name / 'results.json').read_text())
        assert result['status'] == 'passed', name
        suites.append(dict(name=name, checkpoints=result['checkpoints'], translation=result['translation']))
    report = dict(status='passed', suites=suites, checkpoints=sum(row['checkpoints'] for row in suites),
        production_checkpoints=sum(row['checkpoints'] for row in suites if not row['name'].startswith('bench-sidecar')),
        release={}, timings={}, host={}, bounds={}, identical_native_chapters={})
    archive = json.loads((HERE / 'sidecar-reference/archive.json').read_text())
    for version in ('KJV', 'NKJV'):
        old = measure(BUILD / 'sidecar/app', version, True)
        new = measure(APP, version, False)
        assert old['sha256'] == archive['release'][version]['sha256']
        report['release'][version] = dict(sidecar=old, inline=new,
            rom_saved=old['rom_bytes'] - new['rom_bytes'],
            a5_saved=old['a5_bytes'] - new['a5_bytes'],
            application_rom_saved=old['application_rom_bytes'] - new['application_rom_bytes'],
            resource_rom_saved=old['aligned_resource_bytes'] - new['aligned_resource_bytes'])
        lower = version.lower()
        before = BUILD / ('bench-sidecar-' + lower)
        after = BUILD / ('bench-inline-' + lower)
        assert len(json.loads((before / 'checks.json').read_text())) == 14
        for i in range(1, 15):
            assert chapter_bytes(before, i) == chapter_bytes(after, i), (version, i)
        for path in (before / 'artifacts').glob('*.OS3KApp'):
            if not path.name.startswith('BibleWise'):
                assert path.read_bytes() == (after / 'artifacts' / path.name).read_bytes()
        report['identical_native_chapters'][version] = 14
        report['timings'][version] = dict(sidecar=timings(before), inline=timings(after))
        report['host'][version] = {
            case: json.loads((BUILD / ('host-' + case + '-' + lower) / 'results.json').read_text())
            for case in ('codec', 'format')}
        assert all(item['status'] == 'passed' for item in report['host'][version].values())
        previous = ROOT / 'research/bible-reader/preallocated-output/build'
        bound = json.loads((previous / ('production-bound-check-' + version + '.json')).read_text())
        assert bound['status'] == 'passed'
        report['bounds'][version] = bound
        (BUILD / ('bound-' + lower + '.json')).write_text(json.dumps(bound, indent=2) + '\n')
        for obsolete in ('styles.bin', 'layouts.bin'):
            assert not (APP / 'build/data' / lower / obsolete).exists()
    report['notes'] = [
        'Times are emulated Neo milliseconds, not host wall time. Decode/write includes native markup generation.',
        'Load/display includes allocation, native layout and painting; initial Genesis starts before the phase-1 tap attaches.',
        'Application ROM subtracts word-aligned Bible resources from actual release image bytes; includes SDK, headers and non-Bible data.',
        'Formatter stack frames are compiler-reported local frames, not total peak call-stack measurements.',
        'Old fallback-font source assertions discarded style records. Updated source oracle requires bold/italic provenance to survive regular-face fallback; pixel/cursor/LCD assertions remain exact.'
    ]
    (HERE / 'adoption-results.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS', report['checkpoints'], 'MAME checkpoints, both releases, host events/search and capacity bounds')
    for version, sizes in report['release'].items():
        print(version, sizes['rom_saved'], 'ROM saved;', sizes['a5_saved'], 'A5 saved;', sizes['application_rom_saved'], 'application ROM saved')


if __name__ == '__main__':
    main()
