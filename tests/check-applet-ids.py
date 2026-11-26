#!/usr/bin/env python3
"""Check current applet headers against the local private-ID index.

Recorded evidence and source snapshots retain historical IDs. Generated outputs
are excluded using Git's tracked/nonignored source list.
"""
from pathlib import Path
import re
import subprocess

from archived_sources import recorded_snapshot

ROOT = Path(__file__).resolve().parents[1]
index = ROOT / 'applets/PRIVATE_IDS.md'
private = {}
for value, source in re.findall(r'^\| `0x(FF[0-9A-F]{2})` \|[^\n]*?\[source\]\(([^)]+)\)', index.read_text(), re.M):
    number = int(value, 16)
    assert number != 0xFFFF and number not in private, f'Duplicate/invalid local ID {value}'
    path = (index.parent / source).resolve()
    assert path.is_relative_to(ROOT) and path.is_file(), source
    private[number] = path

names = set(subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '--cached', '--others', '--exclude-standard', '--', '*.c'], text=True).splitlines())
observed = {}
impersonated = 0
for name in sorted(names):
    path = ROOT / name
    if any(part in {'upstream', 'snapshot', 'evidence', 'build'} or part.endswith('-evidence') for part in path.relative_to(ROOT).parts):
        continue
    if recorded_snapshot(path, ROOT):
        continue
    text = path.read_text()
    allowed = {int(value, 16) for value in re.findall(r'APPLET_ID_IMPERSONATION:\s*(0x[0-9a-fA-F]{4})\b', text)}
    for value in re.findall(r'\bAPPLET_ID\(\s*(0x[0-9a-fA-F]+|[0-9]+)\s*\)', text):
        number = int(value, 0)
        if number in allowed:
            assert name.startswith(('research/', 'tests/')), f'Impersonation marker outside a fixture: {name}'
            impersonated += 1
            continue
        assert number not in observed, f'Duplicate applet ID {number:#06x}: {name} and {observed.get(number)}'
        observed[number] = name
        research = name.startswith(('research/', 'tests/'))
        if research:
            assert 0xFF00 <= number < 0xFFFF, f'Non-private test/example ID in {name}: {number:#x}'
        if 0xFF00 <= number <= 0xFFFF:
            assert private.get(number) == path.resolve(), f'Unindexed private applet ID {number:#x} in {name}'
for number, path in private.items():
    if path.suffix == '.c':
        assert observed.get(number) == str(path.relative_to(ROOT)), f'Missing indexed header {number:#x}'
    else:
        assert re.search(r'\b0x' + f'{number:04x}' + r'\b', path.read_text(), re.I), f'Missing generated fixture ID {number:#x}'
print(f'PASS {len(observed)} unique source header IDs; {len(private)} indexed private IDs; {impersonated} documented header impersonations; no unmarked research/test fixture consumes public IDs')
