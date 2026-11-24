#!/usr/bin/env python3
"""Byte-level anchors for native USB messages, descriptors and vendor handlers.

No USB access or visual inference. Literal candidates alone are not proof of
message emission; the recorded 300xx/400xx sites have reviewed call contexts.
"""
import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parents[3]
p=root/'Ghidra/Alphasmart Neo/SmartApplets/os3kneorom.os3kos'
b=p.read_bytes()
assert hashlib.sha256(b).hexdigest()=='32fe55bb50c1b58326bd303f14973b8402ddf8bf6662b210e4d5e9f931c7e6c0'
def at(a,n):return b[a-0x410000:a-0x410000+n]
# (address of PEA absolute-long or MOVE immediate-long, full message).
sites={0x41cbf4:0x30001,0x41ccce:0x30013,0x41cd2c:0x30012,
       0x41cde2:0x3000c,0x41ce26:0x30001,0x41cee2:0x3021f,
       0x41cef2:0x3021e,0x41cfd4:0x30008,0x41d0c0:0x30007,
       0x41d202:0x3011f,0x41d20a:0x3011e,0x41d21c:0x3001f,
       0x41d224:0x3001e,0x41d3ac:0x3000c,
       0x440e5a:0x40001,0x440ee8:0x40013,0x440f38:0x40012,
       0x44103c:0x4000c,0x441126:0x40001,0x441158:0x40001,
       0x4411d4:0x40002,0x441288:0x40006,0x44140c:0x40001}
for a,msg in sites.items():
    assert at(a,2)in (b'\x48\x79',b'\x2f\x7c'),hex(a)
    assert at(a+2,4)==msg.to_bytes(4,'big'),hex(a)
# Firmware default control-request tables are ROM addresses, not applet callbacks.
standard=[int.from_bytes(at(0x44f628+4*i,4),'big')for i in range(16)]
hid=[int.from_bytes(at(0x44f668+4*i,4),'big')for i in range(16)]
assert standard[6]==0x44083a and hid[14]==0x44060a and hid[15]==0x44060a
assert at(0x44060a,6)==bytes.fromhex('4eb90044042e')
# Private endpoint/controller helpers are absent from all Neo syscall slots.
targets={int.from_bytes(at(0x44f15e+4*i,4),'big')for i in range(285)}
private=[0x41f90a,0x41f95c,0x41f9a0,0x41f9fe,0x41faa4,0x41faf4,
         0x44083a,0x44129e]
assert not targets.intersection(private)
images={}
inventory={row['path']: row['sha256'] for row in json.loads(
    (root/'betawise/research/abi-audit/vendor-image-inventory.json').read_text())}
for name,entry in [('alphawordplus',0x94),('alphaquiz',0xe20),('keywords',0x63e),
                   ('keywordswireless',0x734),('mathfactsinaflash',0xea),('mathfactsoffline',0x94)]:
    p=root/'Ghidra/Alphasmart Neo/SmartApplets'/f'{name}.os3kapp'
    raw=p.read_bytes();assert int.from_bytes(raw[0x84:0x88],'big')==entry
    digest=hashlib.sha256(raw).hexdigest()
    assert inventory[str(p.relative_to(root))]==digest, name+' image hash differs'
    images[name]={'path':str(p.relative_to(root)),'sha256':digest,
                  'entry':f'{entry:08x}','bytes':len(raw)}
result={'scope':'reviewed static anchors, not runtime USB qualification',
        'messages':{f'{a:08x}':f'{v:08x}'for a,v in sites.items()},
        'standard_request_table':[f'{a:08x}'for a in standard],
        'hid_request_table':[f'{a:08x}'for a in hid],
        'private_helpers_not_syscalls':[f'{a:08x}'for a in private],
        'descriptors':{name:at(a,n).hex()for name,a,n in [
            ('keyboard_device',0x44f704,18),('direct_device',0x44f716,18),
            ('keyboard_interface',0x44f73c,9),('direct_interface',0x44f745,9),
            ('keyboard_in',0x44f758,7),('direct_in',0x44f760,7),('direct_out',0x44f768,7)]},
        'vendor_images':images,'result':'PASS static anchors'}
print(json.dumps(result,indent=2))
