#!/usr/bin/env python3
"""Read the final m68k ELF GOT, retained relocation references, and A5 symbols."""
import argparse
import collections
import json
from pathlib import Path
import struct
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('elf',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    raw=args.elf.read_bytes()
    assert raw[:6]==b'\x7fELF\x01\x02'
    shoff=struct.unpack_from('>I',raw,32)[0]
    entsize,count,strings=struct.unpack_from('>HHH',raw,46)
    sections=[struct.unpack_from('>10I',raw,shoff+i*entsize)for i in range(count)]
    def blob(section):return raw[section[4]:section[4]+section[5]]
    def string(table,offset):return table[offset:table.index(0,offset)].decode()
    names=blob(sections[strings]);section_names=[string(names,s[0])for s in sections]
    syms=[]
    symsec=sections[section_names.index('.symtab')];strs=blob(sections[symsec[6]])
    for start in range(symsec[4],symsec[4]+symsec[5],symsec[9]):
        n,value,size,info,other,idx=struct.unpack_from('>IIIBBH',raw,start)
        syms.append(dict(name=string(strs,n),value=value,size=size,type=info&15,section=idx))
    by_name={s['name']:s for s in syms}
    got_size=by_name['__os3k_got_size']['value']
    ramsec=sections[section_names.index('.rom.ram')]
    words=struct.unpack_from('>'+str(got_size//4)+'I',blob(ramsec))
    entries=[dict(offset=i*4,target=w,references=[])for i,w in enumerate(words)]
    code=[s for s in syms if s['type']==2 and s['size']]
    def owner(address):
        return next((s['name']for s in code if s['value']<=address<s['value']+s['size']),None)
    def contents(address,size):
        for sec in sections:
            if sec[1]!=8 and sec[3]<=address and address+size<=sec[3]+sec[5]:
                offset=sec[4]+address-sec[3];return raw[offset:offset+size]
        raise ValueError(address)
    for sec in sections:
        if sec[1]!=4:continue
        for offset in range(sec[4],sec[4]+sec[5],12):
            address,info,addend=struct.unpack_from('>IIi',raw,offset)
            if info&255 not in (10,11,12):continue
            size=4 if info&255==12 else 2 if info&255==11 else 1
            displacement=int.from_bytes(contents(address,size),'big',signed=True)
            assert displacement>=0 and displacement%4==0 and displacement<got_size,(address,displacement)
            symbol=syms[info>>8]
            entries[displacement//4]['references'].append(dict(address=address,owner=owner(address),symbol=symbol['name'],addend=addend))
    sdk_code={}
    sdk=Path(__file__).resolve().parents[3]/'os3k/build/libos3k.a'
    for line in subprocess.check_output(['m68k-linux-gnu-nm','-A','--defined-only',str(sdk)],text=True).splitlines():
        parts=line.rsplit(':',2);fields=parts[-1].split()
        if len(parts)==3 and len(fields)==3 and fields[1]in ('T','t'):sdk_code[fields[2]]=parts[-2]
    for entry in entries:
        exact=[s for s in syms if s['value']==entry['target'] and s['name'] and s['type']in(0,1,2)]
        entry['symbols']=[s['name']for s in exact]
        refs=entry['references']
        if not refs:category='unreferenced'
        elif entry['target']&0x80000000:category='RAM addresses'
        elif any(s['name']in sdk_code for s in exact):
            owners=[sdk_code[s['name']]for s in exact if s['name']in sdk_code]
            category='firmware syscall wrapper addresses' if any(o in ('syscall.o','os3k_abi_bridge.o')for o in owners) else 'SDK/compiler function addresses'
        elif any(s['type']==2 for s in exact):category='applet function addresses'
        elif any(r['symbol'].startswith('.LC') for r in refs):category='strings/literals'
        else:category='ROM data addresses'
        entry['category']=category
        if category=='strings/literals':
            try:entry['literal']=contents(entry['target'],120).split(b'\0',1)[0].decode('ascii')
            except (ValueError,UnicodeDecodeError):pass
    duplicates=collections.defaultdict(list)
    for entry in entries:duplicates[entry['target']].append(entry['offset'])
    bss=[dict(name=s['name'],offset=s['value']-0x80000000,size=s['size'])for s in syms if s['size'] and 0x80000000<=s['value']<0x80000000+by_name['__os3k_ram_size']['value']]
    summary=collections.Counter(e['category']for e in entries)
    result=dict(elf=str(args.elf),a5_bytes=by_name['__os3k_ram_size']['value'],got_bytes=got_size,
        categories={k:dict(entries=v,bytes=v*4)for k,v in summary.items()},entries=entries,
        duplicates=[dict(target=t,offsets=offs)for t,offs in duplicates.items()if len(offs)>1],ram_symbols=bss)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k]for k in ('a5_bytes','got_bytes','categories','duplicates','ram_symbols')},indent=2))


if __name__=='__main__':main()
