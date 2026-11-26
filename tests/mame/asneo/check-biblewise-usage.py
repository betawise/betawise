#!/usr/bin/env python3
"""Run or collect the source-backed BibleWise everyday-use regression matrix."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


MATRIX = [
    ('boundaries-nkjv', 'NKJV', 'boundaries', 'times'),
    ('usage-kjv', 'KJV', 'usage', 'times'),
    ('usage-nkjv', 'NKJV', 'usage', 'times'),
    ('feedback-nkjv', 'NKJV', 'usage-feedback', 'times'),
    ('font-menu', 'NKJV', 'font-menu', None),
    ('local-font', 'NKJV', 'local-ui', None),
    ('formatting-times', 'NKJV', 'formatting', 'times'),
    ('wrap-regressions', 'NKJV', 'wrap-regression', 'times'),
    ('formatting-helvetica', 'NKJV', 'formatting', 'helvetica'),
    ('formatting-schoolbook', 'NKJV', 'formatting', 'schoolbook'),
    ('mixed-usage', 'NKJV', 'mixed-usage', 'times'),
    ('toggle-page', 'NKJV', 'toggle-page', 'times'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--collect-only', action='store_true')
    parser.add_argument('--report-paths', type=Path,
                        help='JSON mapping of matrix names to existing capture directories')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    paths = json.loads(args.report_paths.read_text()) if args.report_paths else {}
    results = []
    for name, version, case, font in MATRIX:
        capture = Path(paths.get(name, str(output / name))).resolve()
        if not args.collect_only:
            command = [sys.executable, str(Path(__file__).with_name('check-biblewise.py')),
                       '--version', version, '--case', case, '--output', str(capture)]
            if font:
                command += ['--vendor-font', font]
            with (output / (name + '.log')).open('w') as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        report = json.loads((capture / 'results.json').read_text())
        if report.get('status') != 'passed' or report.get('checkpoints', 0) <= 0:
            raise AssertionError(f'{name}: incomplete or failing report')
        results.append(dict(name=name, version=version, case=case, font=font,
                            checkpoints=report['checkpoints'], report=str(capture / 'results.json'),
                            manifest=str(capture / 'manifest.json')))
    summary = dict(status='passed', checkpoints=sum(row['checkpoints'] for row in results),
                   groups=results, oracle='Local source/font/controller/cursor assertions; no model vision')
    (output / 'results.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(f"PASS {len(results)} groups, {summary['checkpoints']} BibleWise checkpoints")


if __name__ == '__main__':
    main()
