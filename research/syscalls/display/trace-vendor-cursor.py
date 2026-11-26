#!/usr/bin/env python3
"""Hash-checked static cursor/editor call references in original vendor applets."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
AUDIT = HERE.parents[1] / 'abi-audit'
SERVICES = {0: 'ClearScreen', 1: 'SetCursor', 2: 'GetCursorPos',
            6: 'SetCursorMode', 7: 'GetCursorMode', 33: 'TextBox',
            174: 'CallSysInt', 175: 'TextEditorInit',
            176: 'TextEditorHandleMessage', 177: 'TextEditorRefresh',
            183: 'TextEditorSetFonts', 247: 'FontDialogUpdate',
            263: 'FontDialogCreate'}


def references(raw, targets):
    result = []
    for offset in range(0, len(raw) - 7, 2):
        opcode = int.from_bytes(raw[offset:offset + 2], 'big')
        target = None
        if opcode in (0x4eba, 0x6100) or opcode & 0xf1ff == 0x41fa:
            target = offset + 2 + int.from_bytes(raw[offset + 2:offset + 4], 'big', signed=True)
        elif opcode == 0x4eb9:
            target = int.from_bytes(raw[offset + 2:offset + 6], 'big')
        if target in targets:
            result.append(dict(offset=offset, target=target, service=targets[target], form='direct'))
        form = opcode & 0xf1ff
        if form not in (0x207c, 0x203c, 0x307c, 0x303c):
            continue
        size = 4 if form in (0x207c, 0x203c) else 2
        value = int.from_bytes(raw[offset + 2:offset + 2 + size], 'big', signed=True)
        register = ((opcode >> 9) & 7) + (8 if form in (0x207c, 0x307c) else 0)
        following = offset + 2 + size
        op = int.from_bytes(raw[following:following + 2], 'big')
        ext = int.from_bytes(raw[following + 2:following + 4], 'big')
        if (op == 0x4ebb or op & 0xf1ff == 0x41fb) and ext >> 12 == register:
            delta = value if ext & 0x800 else ((value + 32768) % 65536) - 32768
            target = following + 2 + delta + int.from_bytes(raw[following + 3:following + 4], 'big', signed=True)
            if target in targets:
                result.append(dict(offset=following, target=target, service=targets[target], form='immediate-delta indexed-PC'))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = []
    for index, entry in enumerate(json.loads((AUDIT / 'vendor-image-inventory.json').read_text())):
        path = ROOT / entry['path']
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry['sha256']
        stubs = {}
        for offset in range(0, len(raw) - 7, 2):
            if raw[offset:offset + 8] != bytes.fromhex('a000a004a008a00c'):
                continue
            pos = offset
            previous = -1
            while pos < len(raw) - 1:
                word = int.from_bytes(raw[pos:pos + 2], 'big')
                if word & 0xf003 != 0xa000:
                    break
                slot = (word - 0xa000) // 4
                if slot <= previous or slot > 284:
                    break
                previous = slot
                if slot in SERVICES:
                    stubs[pos] = SERVICES[slot]
                pos += 2
        calls = references(raw, stubs)
        # An absolute call to these pinned Neo 3.21 internals would be a
        # compatibility concern, not a new API. No heuristic pointer inference.
        internals = references(raw, {0x421cf4: 'Neo321 font/cursor raster helper',
                                   0x4221f4: 'Neo321 pixel cursor helper'})
        record = dict(entry, cursor_editor_references=calls, fixed_internal_references=internals)
        report.append(record)
        if entry['name'] in ('AlphaWord Plus', 'Calculator', 'Inspiration(R) Outliner'):
            samples = []
            for service in SERVICES.values():
                hits = [call for call in calls if call['service'] == service]
                if not hits:
                    continue
                call = hits[0]
                samples.append(json.dumps(call))
                samples.append(subprocess.check_output([
                    'm68k-linux-gnu-objdump', '-D', '-b', 'binary', '-m', 'm68k',
                    f'--start-address={max(0, call["offset"] - 60)}',
                    f'--stop-address={call["offset"] + 10}', str(path)], text=True))
            (args.output / f'vendor-{index}-calls.txt').write_text('\n'.join(samples))
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps([dict(name=r['name'], path=r['path'],
                          counts={name: sum(c['service'] == name for c in r['cursor_editor_references'])
                                  for name in SERVICES.values()},
                          fixed_internals=len(r['fixed_internal_references']))
                      for r in report if r['name'] in ('AlphaWord Plus', 'Calculator', 'Inspiration(R) Outliner')], indent=2))


if __name__ == '__main__':
    main()
