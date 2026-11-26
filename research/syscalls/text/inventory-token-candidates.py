#!/usr/bin/env python3
"""Candidate inventory only: raw matches are not evidence of text-token use.

Inspect disassembly and callers before assigning meaning. Font and dictionary
bytes, jump tables, hardware bit masks and transport opcodes all produce matches.
"""
import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WORKSPACE = REPO.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args=parser.parse_args()
    records=[]
    for entry in json.loads((REPO/'research/abi-audit/vendor-image-inventory.json').read_text()):
        data=(WORKSPACE/entry['path']).read_bytes()
        frames=[]
        for offset in range(0x94,len(data)-2):
            if data[offset] in (0xb1,0xb2) and data[offset]==data[offset+2]:
                frames.append(dict(offset=hex(offset),bytes=data[offset:offset+3].hex()))
        candidates=[]
        for offset in range(0x94,len(data)-5,2):
            opcode=int.from_bytes(data[offset:offset+2],'big')
            value=int.from_bytes(data[offset+2:offset+4],'big')
            if not 0xb0<=value<=0xbf:continue
            if opcode&0xffc0==0x0c00 or opcode&0xf03f==0x103c:
                candidates.append(dict(offset=hex(offset),opcode=hex(opcode),value=hex(value)))
        records.append(dict(name=entry['name'],path=entry['path'],
                            community_font='/NeoFonts/' in entry['path'],
                            raw_frames=frames,byte_instruction_candidates=candidates))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(dict(note=__doc__,images=records),indent=2)+'\n')
    print(f'{len(records)} images; {sum(not r["community_font"] for r in records)} vendor images; candidates require instruction/context validation')


if __name__=='__main__':main()
