#!/usr/bin/env python3
"""Reprofile generated disposable test inputs, never a user's saved session."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HARNESS = ROOT / 'betawise/tests/mame/asneo'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--checks', type=int, default=4)
    args = parser.parse_args()
    original = args.input.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True)

    sys.path.insert(0, str(HARNESS))
    spec = importlib.util.spec_from_file_location('bible_check', HARNESS / 'check-biblewise.py')
    checks_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checks_module)
    emulator = ROOT / 'mame/neodiag'
    checks_module.prepare_session(output, ROOT / 'Ghidra/Alphasmart Neo/SmartApplets', 'extra', emulator)
    shutil.copyfile(original / 'nvram/asneo/flashnv', output / 'nvram/asneo/flashnv')
    shutil.copytree(original / 'artifacts', output / 'artifacts')
    for name in ['source.json', 'source-version.json', 'symbols.json']:
        shutil.copyfile(original / name, output / name)
    checks = json.loads((original / 'checks.json').read_text())[:args.checks]
    (output / 'checks.json').write_text(json.dumps(checks, indent=2) + '\n')

    # Retain archived symbol offsets and inputs; only add stack observations.
    header = (original / 'run.lua').read_text().split('local machine=manager.machine')[0]
    lines = ['local checks=' + checks_module.repl.lua(checks) if line.startswith('local checks=') else line
             for line in header.splitlines()]
    header = '\n'.join(lines).replace(str(original), str(output)) + '\nlocal profile_stack=true\n'
    (output / 'run.lua').write_text(header + (HARNESS / 'BibleWiseHarness.lua').read_text())
    with (output / 'mame.log').open('w') as log:
        result = subprocess.run([
            str(emulator), 'asneo', '-rompath', str(output / 'roms'),
            '-nvram_directory', str(output / 'nvram'), '-cfg_directory', str(output / 'cfg'),
            '-video', 'none', '-sound', 'none', '-nothrottle', '-autoboot_delay', '0',
            '-autoboot_script', str(output / 'run.lua'), '-seconds_to_run', '300',
        ], stdout=log, stderr=subprocess.STDOUT,
            env=dict(os.environ, SDL_VIDEODRIVER='dummy'), timeout=600)
    log_text = (output / 'mame.log').read_text()
    assert result.returncode == 0 and 'PASS BibleWise suite' in log_text, log_text[-2000:]
    checks_module.verify(output)


if __name__ == '__main__':
    main()
