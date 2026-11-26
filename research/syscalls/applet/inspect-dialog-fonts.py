#!/usr/bin/env python3
"""Extract unchanged Neo ROM font cards and inspect getter/create paths."""
import argparse,hashlib,json,struct,subprocess,os
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2];WORKSPACE=REPO.parent
OUT=HERE/'build/dialog-fonts'

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--mame",action="store_true");args=parser.parse_args()
 OUT.mkdir(parents=True,exist_ok=True)
 r=next(x for x in json.loads((REPO/'research/abi-audit/rom-inventory.json').read_text())if x['name']=='neo_3_21')
 path=WORKSPACE/r['path'];rom=path.read_bytes();base=r['base']
 assert hashlib.sha256(rom).hexdigest()==r['sha256']
 mapping={int(l.split()[0],0):int(l.split()[1],0) for l in (REPO/'os3k/charsets/neo-us.txt').read_text().splitlines() if l and not l.startswith('#') and l.split()[1]!='UNMAPPED'}
 fonts=[]
 for name,address in [('small-9px',0x44d592),('dialog-11px',0x44e336)]:
  h,mw,slot,pad,wp,op,bp=struct.unpack_from('>4BIII',rom,address-base)
  widths=list(rom[wp-base:wp-base+256]);offsets=struct.unpack_from('>256H',rom,op-base)
  assert len(widths)==256 and all(0<w<=mw for w in widths)
  glyphs=[]
  for code,w in enumerate(widths):
   data=rom[bp-base+offsets[code]:bp-base+offsets[code]+w*((h+7)//8)]
   assert len(data)==w*((h+7)//8)
   im=Image.new('1',(w,h),1)
   for y in range(h):
    for x in range(w):
     if data[y//8*w+x]>>(y%8)&1:im.putpixel((x,y),0)
   glyphs.append(im)
  blank=[i for i,g in enumerate(glyphs)if not any(v==0 for v in g.getdata())]
  card=Image.new('RGB',(1120,650),'white');d=ImageDraw.Draw(card)
  d.text((16,12),f'{name}: native {h}px, maximum advance {mw}px - all 256 Neo byte slots',fill='black')
  cw,ch=34,67
  for c,g in enumerate(glyphs):
   x=16+(c%32)*cw;y=42+(c//32)*ch
   d.rectangle((x,y,x+cw-1,y+ch-1),outline='#dddddd');d.text((x+3,y+3),f'{c:02X}',fill='#666666')
   card.paste(g.resize((g.width*3,g.height*3),Image.Resampling.NEAREST).convert('RGB'),(x+2,y+22))
  card.save(OUT/f'{name}-glyphs.png')
  fonts.append(dict(name=name,address=hex(address),height=h,max_width=mw,blank_slots=[f'{i:02X}'for i in blank],mapped_blank_slots=[f'{i:02X}'for i in blank if i in mapping],glyphs=glyphs,widths=widths))
 # Identify the repeated replacement box, not merely nonempty slots.
 for font in fonts:
  replacement=font['glyphs'][0x81]
  font['replacement_slots']=[f'{c:02X}'for c,g in enumerate(font['glyphs'])if g.size==replacement.size and g.tobytes()==replacement.tobytes()]
 # Compare the complete advance cell, retaining horizontal bearings and blanks.
 comparison=[]
 small,large=fonts
 for code in range(256):
  a,b=small['glyphs'][code],large['glyphs'][code]
  shifts=[]
  if a.width==b.width:
   for shift in range(b.height-a.height+1):
    padded=Image.new('1',b.size,1);padded.paste(a,(0,shift))
    if padded.tobytes()==b.tobytes():shifts.append(shift)
  ink_a={(x,y)for y in range(a.height)for x in range(a.width)if not a.getpixel((x,y))}
  ink_b={(x,y)for y in range(b.height)for x in range(b.width)if not b.getpixel((x,y))}
  comparison.append(dict(slot=f'{code:02X}',unicode=f'U+{mapping[code]:04X}'if code in mapping else None,
   widths=[a.width,b.width],small_ink=len(ink_a),dialog_ink=len(ink_b),padding_matches=shifts,
   differences_by_shift=[len({(x,y+dy)for x,y in ink_a}^ink_b)for dy in range(3)],
   ink_translations=[[dx,dy]for dx in range(-2,3)for dy in range(3)if {(x+dx,y+dy)for x,y in ink_a}==ink_b]))
 (OUT/'pixel-comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
 shared=[c for c in comparison if c['small_ink'] and c['dialog_ink']]
 genuine=[c for c in shared if c['slot']not in small['replacement_slots'] and c['slot']not in large['replacement_slots']]
 summary_genuine=dict(count=len(genuine),exact_padded=sum(bool(c['padding_matches'])for c in genuine),
  differences=[c for c in genuine if not c['padding_matches']])
 summary=dict(genuine_shared=summary_genuine,shared_ink_slots=len(shared),padding_match_slots=sum(bool(c['padding_matches'])for c in shared),
  width_differences=[c['slot']for c in comparison if c['widths'][0]!=c['widths'][1]],
  shared_nonmatches=[c for c in shared if not c['padding_matches']],
  padding_shift_counts={str(dy):sum(dy in c['padding_matches']for c in shared)for dy in range(3)})
 (OUT/'pixel-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps(summary,indent=2))
 detail=Image.new('RGB',(1120,330),'white');dd=ImageDraw.Draw(detail)
 dd.text((16,12),'Native glyph differences: 9px above / 11px below (6x exact pixels)',fill='black')
 examples=[0x40,0x72,0x7a,0xc7,0xec,0xed,0xee,0xe9,0xf1,0xa0]
 for col,code in enumerate(examples):
  x=16+col*108;dd.text((x,38),f'0x{code:02X}',fill='black')
  for row,f in enumerate(fonts):
   g=f['glyphs'][code];detail.paste(g.resize((g.width*6,g.height*6),Image.Resampling.NEAREST).convert('RGB'),(x,70+row*105))
 detail.save(OUT/'differences.png')
 sample=Image.new('RGB',(1120,760),'#eeeeee');d=ImageDraw.Draw(sample)
 lines=['The quick brown fox enjoys reading.','AaBbCcDdEeFfGg 0123456789','Café déjà vu; naïve façade.','“Read carefully,” she said.']
 for idx,f in enumerate(fonts):
  top=20+idx*370;d.text((22,top),f['name']+' - 264x65 screen, enlarged 4x (native glyphs, no rescaling)',fill='black')
  screen=Image.new('1',(264,65),1)
  reverse={v:k for k,v in mapping.items()};reverse.update({ord(c):ord(c)for c in ''.join(lines) if ord(c)<128})
  for row,line in enumerate(lines):
   x=0
   for c in line:
    code=reverse[ord(c)];g=f['glyphs'][code]
    if x+g.width>264:break
    screen.paste(g,(x,row*f['height']));x+=g.width
  sample.paste(screen.resize((1056,260),Image.Resampling.NEAREST).convert('RGB'),(22,top+32))
 sample.save(OUT/'readability.png')
 report=[{k:v for k,v in f.items()if k not in ('glyphs','widths')}for f in fonts]
 (OUT/'coverage.json').write_text(json.dumps(report,indent=2)+'\n')
 ranges=[(0x425f42,0x42616c),(0x433646,0x433726),(0x433b86,0x433c18),(0x434298,0x4342d4),(0x434852,0x43490c),(0x43490c,0x43496a),(0x432640,0x43272a)]
 (OUT/'paths.asm').write_text('\n'.join(subprocess.check_output(['m68k-linux-gnu-objdump','-D','-b','binary','-m','m68k:68000',f'--adjust-vma={base}',f'--start-address={lo}',f'--stop-address={hi}',str(path)],text=True)for lo,hi in ranges))
 if args.mame:
  romdir=OUT/'roms/asneo';romdir.mkdir(parents=True,exist_ok=True)
  for name in ['os3kneorom.os3kos','smallos3kneorom.os3kos']:
   link=romdir/name
   if not link.exists():link.symlink_to(path.parent/name)
  (OUT/'run.lua').write_text('local RESULT_PATH='+json.dumps(str(OUT/'registers.json'))+'\n'+(HERE/'probe-dialog-fonts.lua').read_text())
  with (OUT/'mame.log').open('w')as log:
   subprocess.run([str(WORKSPACE/'mame/neodiag'),'asneo','-rompath',str(OUT/'roms'),'-nvram_directory',str(OUT/'nvram'),'-cfg_directory',str(OUT/'cfg'),'-video','none','-sound','none','-nothrottle','-seconds_to_run','12','-autoboot_delay','0','-autoboot_script',str(OUT/'run.lua')],stdout=log,stderr=subprocess.STDOUT,timeout=60,check=True,env=dict(os.environ,SDL_VIDEODRIVER='dummy'))
  assert 'PASS dialog font register probe 31 cases' in (OUT/'mame.log').read_text()
 print(json.dumps(report,indent=2));print(OUT/'readability.png')
if __name__=='__main__':main()
