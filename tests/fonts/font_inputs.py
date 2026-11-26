"""Build source-backed font fixtures once per test process, without a network."""
from functools import lru_cache
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def ensure_fonts():
    subprocess.run(['make', '--no-print-directory', '-s', '-C', str(ROOT/'fonts'), 'bdfs'], check=True)
