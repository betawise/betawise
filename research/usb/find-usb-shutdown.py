#!/usr/bin/env python3
"""Conservative shutdown-wrapper search in hash-verified inventoried ROMs.

A match identifies a reset/quiesce candidate, NOT exclusive USB ownership.
Unknown images are deliberately not accepted by this research utility.
"""
from pathlib import Path
import hashlib
import json
root=Path(__file__).resolve().parents[3]
results=[]
for rom in json.loads((root/'betawise/research/abi-audit/rom-inventory.json').read_text()):
    blob=(root/rom['path']).read_bytes()
    assert hashlib.sha256(blob).hexdigest()==rom['sha256'],rom['name']
    matches=[]
    for i in range(0,len(blob)-45,2):
        b=blob[i:i+46]
        # Absolute operands are relocated between ROMs. Keep opcodes and the
        # complete call/save/clear/restore/return structure fixed.
        if not (b[:4]==bytes.fromhex('2f074eb9') and
                b[8:10]==bytes.fromhex('4eb9') and
                b[14:18]==bytes.fromhex('3e004279') and
                b[22:24]==bytes.fromhex('4279') and
                b[28:36]==bytes.fromhex('700030072f004eb9') and
                b[40:]==bytes.fromhex('588f2e1f4e75')):continue
        u=lambda offset:int.from_bytes(b[offset:offset+4],'big')
        backend,save,state1,state2,restore=map(u,[4,10,18,24,36])
        assert state1==state2+2 and restore==save+8
        assert all(rom['base']<=a<rom['base']+len(blob) for a in [backend,save,restore])
        matches.append(dict(address=f'{rom["base"]+i:08x}',backend=f'{backend:08x}',
                            save_sr=f'{save:08x}',restore_sr=f'{restore:08x}',
                            state_words=[f'{state1:08x}',f'{state2:08x}'],hex=b.hex()))
    # Fail closed on ambiguous matches; zero remains explicitly unsupported.
    assert len(matches)<=1,rom['name']+' ambiguous signature'
    results.append(dict(rom=rom['name'],sha256=rom['sha256'],matches=matches))
print(json.dumps(dict(scope='static shutdown candidates; not ownership or runtime certification',roms=results),indent=2))
