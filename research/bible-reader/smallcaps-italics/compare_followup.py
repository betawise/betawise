#!/usr/bin/env python3
"""Report the chapter-rebuild and shared provenance-pass experiment."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT/'applets/BibleWise'
MODES = ('alias', 'rebuild', 'integrated')
RESOURCES = ('container', 'search', 'verses', 'pruning', 'styles', 'layouts')


def release_sizes():
    rows = []
    for version in ('KJV', 'NKJV'):
        baseline = None
        data = APP/'build/data'/version.lower()
        resources = {name:hashlib.sha256((data/(name+'.bin')).read_bytes()).hexdigest()
                     for name in RESOURCES}
        resource_bytes = sum((data/(name+'.bin')).stat().st_size for name in RESOURCES)
        for mode in MODES:
            directory = APP/'build'/(version+('' if mode=='alias' else '-italics-'+mode))
            stem = 'BibleWise'+('' if version=='KJV' else '-'+version)
            elf = directory/(stem+'.elf')
            output = subprocess.check_output(['m68k-linux-gnu-nm', str(elf)], text=True)
            names = {fields[2]:int(fields[0],16) for line in output.splitlines()
                     if len(fields := line.split())==3}
            row = dict(version=version, mode=mode, a5_bytes=names['__os3k_ram_size'],
                       got_bytes=names['__os3k_got_size'], image_bytes=names['__os3k_rom_size'],
                       application_rom_bytes=names['__os3k_rom_size']-resource_bytes,
                       bible_resource_bytes=resource_bytes, bible_resource_hashes=resources,
                       elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest())
            if baseline is None:
                baseline = row
            row['a5_saved_bytes'] = baseline['a5_bytes']-row['a5_bytes']
            row['rom_added_bytes'] = row['image_bytes']-baseline['image_bytes']
            rows.append(row)
    return rows


def suite(directory):
    report = json.loads((directory/'results.json').read_text())
    assert report['status']=='passed', directory
    assert 'PASS BibleWise suite' in (directory/'mame.log').read_text(), directory
    checks = json.loads((directory/'checks.json').read_text())
    trace = json.loads((directory/'timings.json').read_text())
    metadata = json.loads((directory/'source-version.json').read_text())
    toggles = []
    for index, check in enumerate(checks, 1):
        times = {event['phase']:event['time'] for event in trace if event['check']==index}
        if 669 not in times:
            continue
        assert 672 in times, check['name']
        toggles.append(dict(check=index, name=check['name'], italics=check.get('italics',True),
            total_ms=1000*(times[672]-times[669]),
            operation_ms=1000*(times.get(671,times[501])-times.get(670,times[501]))))
    return dict(path=str(directory.resolve()), checkpoints=report['checkpoints'],
                status=report['status'], **metadata, toggles=toggles)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent/'build/followup-results.json')
    args = parser.parse_args()
    suites = []
    for version in ('kjv', 'nkjv'):
        for mode in MODES:
            suites.append(suite(args.evidence/('final-'+version+'-'+mode)))
    suites.append(suite(args.evidence/'final-times-rebuild'))
    suites.append(suite(args.evidence/'times-integrated-interactions'))
    summary = []
    for item in suites[:6]:
        for chapter in ('Gen 1', 'Exod 33', 'Ps 119', 'Ps 3'):
            selected = [row for row in item['toggles'] if row['name'].startswith(chapter+' selected ')]
            scrolled = [row for row in item['toggles'] if row['name'].startswith(chapter+' scrolled ')]
            assert len(selected)==len(scrolled)==2
            summary.append(dict(version=item['version'], mode=item['italics_prototype'],chapter=chapter,
                selected_off_ms=selected[0]['total_ms'], selected_on_ms=selected[1]['total_ms'],
                scrolled_off_ms=scrolled[0]['total_ms'], scrolled_on_ms=scrolled[1]['total_ms']))
    evidence_hashes = json.loads((args.evidence/'final-source-hashes.json').read_text())
    for name, digest in evidence_hashes.items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest, ('source changed',name)
    result = dict(scope='Research only. Neo 3.21, Century Schoolbook Tiny main comparison; Times Tiny selection/copy/visibility interactions. Alias remains default.',
                  timing_scope='Guest emulated time from before source-anchor capture/busy/font setup through final redraw; excludes the test-only offset reconstruction probe.',
                  release_sizes=release_sizes(), toggle_summary=summary, suites=suites,
                  total_passed_checkpoints=sum(item['checkpoints'] for item in suites),
                  source_hashes=evidence_hashes,
                  provenance='0x10 permanently mirrors original italic on body and private small-cap letters. Only 0x1C-marked glyphs are XORed by 0x2B when the global preference toggles. No provenance index or separate rewrite scanner.',
                  rebuild='Three transient stack-only (verse, word, byte delta) anchors restore viewport, caret and selection after padding changes. Uses existing word scanners and normal chapter decoding.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')


if __name__=='__main__':
    main()
