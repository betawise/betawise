#!/usr/bin/env python3
"""Compare immutable 3x5 digits with unscaled same-family Adobe bitmap strikes."""
import json,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import build_fonts as recipe
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent/'build/superscript-strikes'
DIGITS=json.loads(Path(__file__).with_name('superscript-3x5.json').read_text())
CODES=tuple(range(48,58))+(0x2070,0xb9,0xb2,0xb3,0x2074,0x2075,0x2076,0x2077,0x2078,0x2079)
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

def native(face,height,top):
 ys=[y for c in range(48,58)for x,y in face[c]['points']];offset=top-min(ys)
 images={}
 for c in range(48,58):
  w,points,_=recipe.horizontal(face[c],None,False)
  im=Image.new('1',(w,height))
  for x,y in points:
   assert 0<=x<w and 0<=y+offset<height
   im.putpixel((x,y+offset),1)
  images[c]=im
 return images

def current(height,top):
 result={}
 for digit,columns in enumerate(DIGITS['columns']):
  im=Image.new('1',(4,height))
  for x,column in enumerate(columns):
   for y in range(5):
    if column>>y&1:im.putpixel((x,top+y),1)
  result[48+digit]=im
 return result

def run(body,digits,text,superior=False):
 cells=[digits[ord(c)]if superior else body[ord(c)]for c in text]
 im=Image.new('1',(sum(g.width for g in cells),body[72].height));x=0
 for g in cells:im.paste(g,(x,0));x+=g.width
 return im

def example(body,digits):
 a=run(body,digits,'123',True);b=run(body,digits,' Holy.');im=Image.new('1',(a.width+b.width,a.height));im.paste(a,(0,0));im.paste(b,(a.width,0));return im

def paste(card,im,x,y):
 scaled=im.resize((im.width*4,im.height*4),Image.Resampling.NEAREST)
 card.paste('black',(x,y,x+scaled.width,y+scaled.height),scaled)

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 label=ImageFont.truetype(FONT,19);title=ImageFont.truetype(FONT,26)
 coverage=[];records=[]
 for family in recipe.FAMILIES:
  options=recipe.strikes(recipe.X11_ROOT,family,CODES)
  candidates=[]
  for option in options:
   for style,path in zip(recipe.STYLES,option['paths']):
    _,face=recipe.source(path,CODES)
    present=[f'U+{c:04X}'for c in CODES[10:]if c in face]
    coverage.append(dict(family=family,style=style,source=recipe.source_name(path),superscripts=present,complete=len(present)==10))
   _,face=recipe.source(option['paths'][0],CODES)
   ys=[y for c in range(48,58)for x,y in face[c]['points']]
   signature=tuple((face[c]['advance'],tuple(sorted(face[c]['points'])))for c in range(48,58))
   candidates.append(dict(option=option,face=face,height=max(ys)-min(ys)+1,signature=signature))
  card=Image.new('RGB',(1830,1035),'white');draw=ImageDraw.Draw(card)
  draw.text((18,10),f'BetaWise {family}: superscript digit alternatives',font=title,fill='black')
  draw.text((18,46),'4x exact pixels. No rescaling or clipping; all digit sets align with body H top.',font=label,fill='#555555')
  for row,(lines,size)in enumerate(recipe.SIZES.items()):
   path=ROOT/'fonts/build/bdf'/('BetaWise'+family)/f'BetaWise{family}-{size}-Regular.bdf'
   body=recipe.fontgen.load(path,'iso8859-1',63);height=body[72].height;box=body[72].getbbox();top=box[1];cap=box[3]-top
   pixels=int(next(l.split()[1]for l in path.read_text().splitlines()if l.startswith('PIXEL_SIZE ')))
   available=[c for c in candidates if c['option']['pixels']<pixels and c['height']<cap and top+c['height']<=height]
   distinct={}
   for candidate in available:distinct.setdefault(candidate['signature'],candidate)
   available=list(distinct.values())
   # Select native heights around 60% and 80% of the capital height.
   shown=[]
   for target in [cap*.6,cap*.8]:
    ranked=sorted(available,key=lambda c:(abs(c['height']-target),c['option']['dpi'],c['option']['pixels']))
    if ranked and ranked[0]not in shown:shown.append(ranked[0])
   if len(shown)<2:
    for c in sorted(available,key=lambda c:(c['height'],c['option']['pixels'],c['option']['dpi'])):
     if c not in shown:shown.append(c)
     if len(shown)==2:break
   reference=False
   if not shown:
    shown=[min(candidates,key=lambda c:(c['height'],c['option']['pixels'],c['option']['dpi']))];reference=True
   y=85+row*235
   draw.text((18,y),f'{size}: {lines} lines / body capitals {cap}px',font=title,fill='black')
   draw.line((18,y+221,1810,y+221),fill='#cccccc')
   sets=[('TI small 3×5 / 4px advance',current(height,top),None)]
   for c in shown:
    o=c['option'];note=' [not smaller than capitals]'if reference else ''
    sets.append((f"Native {c['height']}px ink / {o['pixels']}px strike / {o['dpi']}dpi"+note,native(c['face'],height,top),c))
   for col,(name,digits,candidate)in enumerate(sets):
    x=18+col*600;draw.text((x,y+40),name,font=label,fill='#ad3024'if reference and col else '#245c89')
    numeral_run=run(body,digits,'0123456789',True);context=example(body,digits)
    assert numeral_run.width*4<580 and context.width*4<580,(family,size,name)
    paste(card,numeral_run,x,y+74)
    paste(card,context,x,y+142)
   records.append(dict(family=family,size=size,lines=lines,body_cap_height=cap,
    available=[dict(ink_height=c['height'],pixels=c['option']['pixels'],dpi=c['option']['dpi'],source=recipe.source_name(c['option']['paths'][0]))for c in available],
    displayed=[recipe.source_name(c['option']['paths'][0])for c in shown],reference_only=reference))
  card.save(OUT/(family.lower()+'.png'))
 assert not any(c['complete']for c in coverage)
 (OUT/'unicode-coverage.json').write_text(json.dumps(coverage,indent=2)+'\n')
 (OUT/'candidates.json').write_text(json.dumps(records,indent=2)+'\n')
 print('Audited',len(coverage),'source faces: no complete Unicode superscript set.')
 for r in records:print(r['family'],r['size'],'cap',r['body_cap_height'],'options',sorted({c['ink_height']for c in r['available']}),'reference only'if r['reference_only']else'')
 print(OUT)
if __name__=='__main__':main()
