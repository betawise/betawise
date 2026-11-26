#!/usr/bin/env python3
"""Inventory actual H-top offsets; generated report stays under build/."""
import json,struct
from pathlib import Path
from superscript_samples import ROOT,OUT,binary_font
import fontgen

def main():
 rows=[]
 for folder in ['NeoFonts','SmartApplets']:
  directory=ROOT.parent/'Ghidra/Alphasmart Neo'/folder
  for p in sorted(directory.iterdir()):
   if p.suffix.lower()!='.os3kapp' or (folder=='SmartApplets' and not p.name.startswith('neofont')):continue
   data=p.read_bytes();found=[]
   for i in range(len(data)-16):
    h,w,st,pad,wp,op,bp=struct.unpack_from('>4BIII',data,i)
    if not(5<=h<=66 and 1<w<67 and pad==0 and 60<bp<len(data) and 60<wp<len(data)-256 and 60<op<len(data)-512):continue
    if not all(0<x<=w for x in data[wp:wp+256]):continue
    try:cells=binary_font(data,i,0)
    except (IndexError,ValueError):continue
    if cells[72].getbbox():found.append(cells)
   assert len(found)==1,(p.name,len(found))
   cells=found[0];rows.append(dict(name=p.stem,height=cells[72].height,top=cells[72].getbbox()[1],kind=folder))
 r=next(r for r in json.loads((ROOT/'research/abi-audit/rom-inventory.json').read_text())if r['name']=='neo_3_21');rom=(ROOT.parent/r['path']).read_bytes()
 for label,address in [('System9',0x44d592),('System16',0x44af8e)]:
  h=binary_font(rom,address,r['base'])[72];rows.append(dict(name=label,height=h.height,top=h.getbbox()[1],kind='System'))
 for path in sorted((ROOT/'fonts/build/bdf').glob('BetaWise*/*Regular.bdf')):
  h=fontgen.load(path,'iso8859-1',63)[72];rows.append(dict(name=path.stem,height=h.height,top=h.getbbox()[1],kind='BetaWise private'))
 for path in sorted((ROOT/'fonts/build/bdf/BetaWiseTerminal').glob('*.bdf')):
  h=fontgen.load(path,'iso8859-1',63)[72];rows.append(dict(name=path.stem,height=h.height,top=h.getbbox()[1],kind='Terminal'))
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'offset-inventory.json').write_text(json.dumps(rows,indent=2)+'\n')
 for row in rows:print(f"{row['top']:2} {row['height']:2} {row['name']}")
 print('Fallback fonts within height guard:',sorted({r['top']for r in rows if r['kind']!='BetaWise private'and r['height']<=64}))
 print('All fonts:',sorted({r['top']for r in rows}))
if __name__=='__main__':main()
