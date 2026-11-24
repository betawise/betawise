#!/usr/bin/env python3
"""Verify the measured ROM blob; emit its compact navigation declarations."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys

source, target = map(Path, sys.argv[1:3])
expected = sys.argv[3] if len(sys.argv)>3 else '7d58ee4d28a80d530e1a1ca4c510cb55801ac387ba62927278ba4ab515a01c1c'
data = source.read_bytes()
if expected == 'auto': expected=json.loads(source.with_name('results.json').read_text())['sha256']
assert hashlib.sha256(data).hexdigest() == expected
metadata_size = struct.unpack_from('>I', data, 8)[0]
books = json.loads(data[64:64 + metadata_size])
assert len(books) == 66 and all(len(name) < 24 for name, start, count in books)
shutil.copyfile(source, target / 'bible.bin')
(target / 'Navigation.h').write_text('/* Generated from the verified container. */\n'
    'typedef struct { uint16_t first, chapters; char name[24]; } BibleBook;\n'
    'static const BibleBook books[66] = {\n' + ''.join(
    '    {%d,%d,%s},\n' % (start, count, json.dumps(name)) for name, start, count in books) + '};\n')
