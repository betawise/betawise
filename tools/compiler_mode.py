#!/usr/bin/env python3
"""Update a compiler-mode dependency only when its inputs change."""
import hashlib
import json
import os
from pathlib import Path
import sys

path = Path(sys.argv[1])
root = Path(__file__).resolve().parents[1]
signature = json.dumps({
    'enabled': sys.argv[2],
    'cross_compile': sys.argv[3],
    'adapter': hashlib.sha256((root/'tools/relative_calls.py').read_bytes()).hexdigest(),
}, sort_keys=True) + '\n'
path.parent.mkdir(parents=True, exist_ok=True)
if not path.exists() or path.read_text() != signature:
    temporary = path.with_name(path.name + '.' + str(os.getpid()) + '.tmp')
    temporary.write_text(signature)
    temporary.replace(path)
