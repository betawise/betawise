"""Shared locations and on-demand inputs for optional font research tools."""
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BUILD = HERE / 'build'
BDFS = ROOT / 'fonts/build/bdf'


def ensure_bdfs():
    subprocess.run(['make', '--no-print-directory', '-s', '-C', str(ROOT / 'fonts'), 'bdfs'], check=True)
    return BDFS


def generation_report():
    ensure_bdfs()
    return json.loads((BDFS / 'generation-report.json').read_text())
