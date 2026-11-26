#!/usr/bin/env python3
"""Read-only original-image audit; static references are candidates, not execution."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
AUDIT=HERE.parents[1]/'abi-audit'


def disassemble(path,base,start,end):
    return subprocess.check_output(['m68k-linux-gnu-objdump','-D','-b','binary','-m','m68k',
        f'--adjust-vma={base}',f'--start-address={start}',f'--stop-address={end}',str(path)],text=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    report={'roms':[],'vendor_images':[],'scope':'Pinned original ROMs/vendor images only. No dynamic calls or claims about unexamined firmware.'}
    for entry in json.loads((AUDIT/'rom-inventory.json').read_text()):
        path=ROOT/entry['path'];raw=path.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==entry['sha256']
        target=entry['targets'][1]
        code=raw[target-entry['base']:target-entry['base']+20]
        cursor_base=int.from_bytes(code[6:10],'big')if code[4:6]==bytes.fromhex('267c')else None
        text=disassemble(path,entry['base'],target,target+140)
        (args.output/(entry['name']+'-set-cursor.txt')).write_text(text)
        report['roms'].append(dict(name=entry['name'],path=entry['path'],sha256=entry['sha256'],set_cursor=hex(target),bitmap_cursor_base=hex(cursor_base)if cursor_base else None))
    addresses=sorted(set(range(0x5c68,0x5c7a))|set(range(0x5712,0x5724))|{0x423b,0x423c,0x4369,0x436a,0x48bf,0x48c0})
    for entry in json.loads((AUDIT/'vendor-image-inventory.json').read_text()):
        path=ROOT/entry['path'];raw=path.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==entry['sha256']
        stubs={}
        sequence=bytes.fromhex('a000a004a008a00c')
        for offset in range(0,len(raw)-7,2):
            if raw[offset:offset+8]==sequence:
                stubs[offset+2]='SetCursor';stubs[offset+4]='GetCursorPos'
        calls=[]
        for offset in range(0,len(raw)-5,2):
            opcode=int.from_bytes(raw[offset:offset+2],'big')
            target=None
            if opcode in (0x4eba,0x6100):target=offset+2+int.from_bytes(raw[offset+2:offset+4],'big',signed=True)
            elif opcode==0x4eb9:target=int.from_bytes(raw[offset+2:offset+6],'big')
            if target in stubs:calls.append(dict(offset=hex(offset),service=stubs[target],form=hex(opcode),target=hex(target)))
        relative_literals=set()
        for offset in range(0,len(raw)-9,2):
            opcode=int.from_bytes(raw[offset:offset+2],'big');form=opcode&0xf1ff
            if form not in (0x207c,0x203c,0x307c,0x303c):continue
            size=4 if form in (0x207c,0x203c) else 2
            value=int.from_bytes(raw[offset+2:offset+2+size],'big',signed=True)
            register=((opcode>>9)&7)+(8 if form in (0x207c,0x307c) else 0)
            following=offset+2+size
            op=int.from_bytes(raw[following:following+2],'big')
            ext=int.from_bytes(raw[following+2:following+4],'big')
            if (op==0x4ebb or op&0xf1ff==0x41fb) and ext>>12==register:
                relative_literals.add(offset+2)
                delta=value if ext&0x800 else ((value+32768)%65536)-32768
                target=following+2+delta+int.from_bytes(raw[following+3:following+4],'big',signed=True)
                if target in stubs:calls.append(dict(offset=hex(following),service=stubs[target],form='immediate-delta indexed-PC',target=hex(target)))
        literals=[]
        for address in addresses:
            encoded=address.to_bytes(4,'big')
            pos=raw.find(encoded)
            while pos>=0:
                if pos%2==0:literals.append(dict(offset=hex(pos),address=hex(address),classification='PC-relative delta' if pos in relative_literals else 'unresolved literal; may be data'))
                pos=raw.find(encoded,pos+1)
        report['vendor_images'].append(dict(name=entry['name'],path=entry['path'],sha256=entry['sha256'],cursor_stubs=stubs,resolved_calls=calls,absolute_long_literals=literals))
    report['summary']=dict(images=len(report['vendor_images']),images_with_resolved_cursor_calls=sum(bool(v['resolved_calls'])for v in report['vendor_images']),images_with_cursor_address_literals=sum(bool(v['absolute_long_literals'])for v in report['vendor_images']))
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'roms':report['roms'],'summary':report['summary']},indent=2))

if __name__=='__main__':main()
