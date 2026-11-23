#!/usr/bin/env python3
"""Check message facts against original bytes, independent of Ghidra's types."""
from pathlib import Path
import hashlib
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
VENDORS=json.loads((HERE.parents[1]/'abi-audit/vendor-image-inventory.json').read_text())
checked=0
for e in VENDORS:
    b=(ROOT/e['path']).read_bytes()
    assert hashlib.sha256(b).hexdigest()==e['sha256'],e['path']
    # All stock/alternate Neo providers have the same scalar-height return.
    if 'neofont' in Path(e['path']).name.lower():
        assert bytes.fromhex('223c0000000070001035180020462080') in b,e['path']
        checked+=1
assert checked==21,checked
rp=next(e for e in VENDORS if Path(e['path']).name.lower()=='mathfactsinaflash.os3kapp')
b=(ROOT/rp['path']).read_bytes()
expected={1:'Connected to ADB.',2:'Connected to PS2.',3:'Connected to USB in keyboard mode.',
          4:'Connected to USB.',6:'Connected to a printer.\n',7:'Connected to IR.'}
for family,text in expected.items():
    table=0x15c
    target=table+int.from_bytes(b[table+2*(family-1):table+2*family],'big',signed=True)
    assert b[target:target+2]==bytes.fromhex('287c')
    assert b[target+6:target+10]==bytes.fromhex('49fbc8fe')
    address=target+6+int.from_bytes(b[target+2:target+6],'big',signed=True)
    assert b[address:].split(b'\0',1)[0].decode('ascii')==text,(family,hex(address))
roms=json.loads((HERE.parents[1]/'abi-audit/rom-inventory.json').read_text())
neo=next(e for e in roms if e['name']=='neo_3_21')
b=(ROOT/neo['path']).read_bytes();base=neo['base']
assert hashlib.sha256(b).hexdigest()==neo['sha256']
for code,text in [(0x2e,b'Low Battery.'),(0xbc,b'Making AlphaHub connection...')]:
    table=0x44b03e-base+4*code
    address=int.from_bytes(b[table:table+4],'big')-base
    assert b[address:].split(b'\0',1)[0]==text
assert b[0x417c82-base:0x417c8e-base]==bytes.fromhex('4eb900426df24a0067027e25')
assert b[0x418a84-base:0x418a8c-base]==bytes.fromhex('2f0e42a748780026')
print(f'PASS {checked} vendor scalar-height implementations; six exact transport names; low-battery/AlphaHub strings and event/ID dispatch bytes')
