#!/usr/bin/env python3
"""Summarize release sizes and emulated CPU timings from the small-cap trials."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / 'applets/BibleWise'
MODES = ('alias', 'metadata', 'rom-index', 'offsets', 'marker')
RESOURCES = ('container', 'search', 'verses', 'pruning', 'styles', 'layouts')


def symbols(path):
    output = subprocess.check_output(['m68k-linux-gnu-nm', str(path)], text=True)
    return {fields[2]: int(fields[0], 16) for line in output.splitlines()
            if len(fields := line.split()) == 3}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent/'build/results.json')
    args = parser.parse_args()
    sizes = []
    for version in ('KJV', 'NKJV'):
        data = APP/'build/data'/version.lower()
        resource_bytes = sum((data/(name+'.bin')).stat().st_size for name in RESOURCES)
        baseline = None
        for mode in MODES:
            build = APP/'build'/(version+('' if mode == 'alias' else '-italics-'+mode))
            stem = 'BibleWise'+('' if version == 'KJV' else '-'+version)
            elf = build/(stem+'.elf')
            table = symbols(elf)
            row = dict(version=version, mode=mode, a5_bytes=table['__os3k_ram_size'],
                       got_bytes=table['__os3k_got_size'], image_bytes=table['__os3k_rom_size'],
                       application_rom_bytes=table['__os3k_rom_size']-resource_bytes,
                       bible_resource_bytes=resource_bytes,
                       elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest())
            if baseline is None:
                baseline = row
            row['a5_saved_bytes'] = baseline['a5_bytes']-row['a5_bytes']
            row['rom_added_bytes'] = row['image_bytes']-baseline['image_bytes']
            sizes.append(row)
    toggles = []
    summaries = []
    suites = []
    for directory in sorted(args.evidence.iterdir()):
        if directory.name.endswith('-original') or not directory.is_dir() or not (directory/'checks.json').exists():
            continue
        if not (directory/'timings.json').exists():
            continue
        report_path = directory/'results.json'
        if not report_path.exists():
            continue
        report = json.loads(report_path.read_text())
        assert report['status']=='passed', directory
        checks = json.loads((directory/'checks.json').read_text())
        trace = json.loads((directory/'timings.json').read_text())
        metadata = json.loads((directory/'source-version.json').read_text())
        suites.append(dict(name=directory.name, checks=len(checks), status=report['status'], **metadata))
        for index, check in enumerate(checks, 1):
            times = {event['phase']: event['time'] for event in trace if event['check'] == index}
            if 669 not in times or 672 not in times:
                continue
            toggles.append(dict(suite=directory.name, check=index, name=check['name'],
                enabled=check.get('italics', True),
                total_ms=1000*(times[672]-times[669]),
                rewrite_ms=1000*(times.get(671, times[501])-times.get(670, times[501]))))
    for mode in MODES:
        for enabled in (False, True):
            rows = [row for row in toggles if row['suite'] == mode and row['enabled'] == enabled
                    and row['name'].endswith((' off', ' on'))]
            if rows:
                summaries.append(dict(mode=mode, enabled=enabled, samples=len(rows),
                    total_mean_ms=statistics.mean(row['total_ms'] for row in rows),
                    total_min_ms=min(row['total_ms'] for row in rows),
                    total_max_ms=max(row['total_ms'] for row in rows),
                    rewrite_mean_ms=statistics.mean(row['rewrite_ms'] for row in rows)))
    result = dict(scope='Research variants; alias remains the default. Release sizes include SDK and linker overhead; application ROM excludes six unchanged Bible resources.',
                  evidence=str(args.evidence.resolve()), release_sizes=sizes,
                  nkjv_schoolbook_toggle_summary=summaries, individual_toggles=toggles, suites=suites,
                  corpus={version:json.loads((APP/'build/data'/version.lower()/'ItalicResearch.json').read_text())
                          for version in ('KJV', 'NKJV')})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
