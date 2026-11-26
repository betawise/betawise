#!/usr/bin/env python3
"""Run the same source/font/cursor/LCD assertions and phase timings on either app."""
import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'research/bible-reader/preallocated-output'))
from run import benchmark_cases

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--app', type=Path, default=ROOT / 'applets/BibleWise')
args, remaining = parser.parse_known_args()
script = ROOT / 'tests/mame/asneo/check-biblewise.py'
source = script.read_text().replace("APP = ROOT / 'betawise/applets/BibleWise'", 'APP = Path('+repr(str(args.app.resolve()))+')')
marker = "    if args.case != 'native': clear_previous_find_queries(checks)"
assert marker in source
source = source.replace(marker, '    checks = benchmark_cases(books, args.version)\n' + marker)
sys.path.insert(0, str(script.parent))
sys.argv = [str(script), *remaining]
exec(compile(source, str(script), 'exec'), {'__name__': '__main__', '__file__': str(script), 'benchmark_cases': benchmark_cases})
