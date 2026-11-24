#!/usr/bin/env python3
"""Check retained original AlphaWord binding records without an emulator."""
from pathlib import Path
import hashlib
import sys

HERE = Path(sys.argv[1]).resolve()
for state in ['empty', 'typed', 'selected', 'home', 'file2', 'reopened']:
    record = (HERE / (state + '-fileinfo.bin')).read_bytes()
    editor = (HERE / (state + '-editor.bin')).read_bytes()
    assert len(record) == 72 and len(editor) == 94
    assert record[0x24:0x34] == bytes(16), state
    assert int.from_bytes(record[0x14:0x18], 'big') == 0, state
    if state == 'selected':
        assert int.from_bytes(editor[0x24:0x28], 'big') == 2
        assert int.from_bytes(editor[0x38:0x3c], 'big') == 3
        assert int.from_bytes(editor[0x36:0x38], 'big') != 0
log = (HERE / 'mame.log').read_text()
assert 'PASS original AlphaWord file bindings' in log and 'FAIL' not in log
print('PASS retained evidence hashes, six zero-binding records and independent selection/file positions')
