#!/usr/bin/env python3
"""Run the maintained partial-selection regression through the canonical harness."""
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
output = sys.argv[1] if len(sys.argv) > 1 else str(HERE / 'build/partial-copy')
subprocess.run([sys.executable, str(ROOT / 'tests/mame/asneo/check-biblewise.py'),
                '--version', 'KJV', '--case', 'partial-copy', '--output', output], check=True)
