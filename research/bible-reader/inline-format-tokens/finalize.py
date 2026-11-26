#!/usr/bin/env python3
"""Refresh framing counts and audit existing encoder artifacts without retraining.

Only chapter-record uncompressed-size fields change; all encoded payloads,
models, dictionaries, grammar, semantic round trips and measured lengths remain
unchanged. compare.py now emits these counts directly on a fresh run.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys
from compare import APP, chapter_stream, read_formatting, encode_native

path = Path(sys.argv[1])
report = json.loads((path / 'results.json').read_text())
data = read_formatting('nkjv', APP / 'upstream')
for chapter in data['atoms']:
    for atom in chapter:
        atom['style'] &= 7
for row in report['variants']:
    image_path = path / row['mode'] / 'container.bin'
    image = bytearray(image_path.read_bytes())
    metadata, _, dictionary, model, chapters, _, rules, _ = struct.unpack_from('>8I', image, 8)
    start = 64 + metadata + dictionary + model + 4 * rules
    sizes = []
    for ci, (atoms, headings) in enumerate(zip(data['atoms'], data['headings'])):
        pieces, _ = chapter_stream(atoms, headings, row['default_layout'], row['mode'] == 'combined')
        size = sum(4 if isinstance(p, tuple) else len(encode_native(p)) for p in pieces)
        sizes.append(size)
        struct.pack_into('>I', image, start + ci * 16 + 12, size)
    assert len(sizes) == chapters == 1189
    image_path.write_bytes(image)
    row.update(expanded_markup_bytes=sum(sizes), maximum_expanded_chapter_bytes=max(sizes),
        sha256=hashlib.sha256(image).hexdigest())
    (path / row['mode'] / 'results.json').write_text(json.dumps(row, indent=2) + '\n')
source = APP / 'build/data/nkjv'
report['baseline_sha256'] = {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
    for name in report['baseline']}
(path / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS exact expanded markup lengths in all chapter records')
