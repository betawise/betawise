#!/usr/bin/env python3
"""Regenerate historical listings from hash-checked private inputs; no emulator."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent


def regenerate(workspace, output, only=None):
    workspace = workspace.resolve()
    recipes = json.loads((HERE / 'disassembly-recipes.json').read_text())
    if only:
        recipes = [entry for entry in recipes if entry['output'] == only]
        if not recipes:
            raise ValueError(f'No verified recipe for {only!r}')
    output.mkdir(parents=True, exist_ok=False)
    for entry in recipes:
        source = workspace / entry['source']
        if hashlib.sha256(source.read_bytes()).hexdigest() != entry['source_sha256']:
            raise ValueError(f'Original firmware hash differs: {source}')
        text = subprocess.check_output(entry['argv'], cwd=workspace, text=True)
        target = output / entry['output']
        target.write_text(text)
        print(target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=HERE.parents[3])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--only', help='One output filename from disassembly-recipes.json')
    args = parser.parse_args()
    regenerate(args.workspace, args.output, args.only)
