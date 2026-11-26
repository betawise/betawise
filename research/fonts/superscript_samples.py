#!/usr/bin/env python3
"""Render cap-aligned verse numbers from generated BDFs and original ROM glyphs."""
import json,struct,sys
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'fonts'))
import fontgen
OUT=Path(__file__).resolve().parent/'build/superscripts'
DIGITS=json.loads(Path(__file__).with_name('superscript-3x5.json').read_text())

def binary_font(data,address,base):
 h,w,slot,_,wp,op,bp=struct.unpack_from('>4BIII',data,address-base)
 cells=[]
 for c in range(256):
  width=data[wp-base+c]if wp else w
  offset=struct.unpack_from('>H',data,op-base+2*c)[0]if op else c*slot
  cell=Image.new('1',(width,h))
  for y in range(h):
   for x in range(width):
    if data[bp-base+offset+y//8*width+x]>>(y%8)&1:cell.putpixel((x,y),1)
  cells.append(cell)
 return cells

def fallback(cells):
 h=cells[72].height;top=min(cells[72].getbbox()[1],h-5)
 glyphs={}
 for d,columns in enumerate(DIGITS['columns']):
  cell=Image.new('1',(4,h))
  for x,column in enumerate(columns):
   for y in range(5):
    if column>>y&1:cell.putpixel((x,top+y),1)
  glyphs[48+d]=cell
 return glyphs

def strip(cells,digits):
 h=cells[72].height;im=Image.new('1',(264,h));x=0
 for text,superior in [('123',True),(' Holy words: Heaven and earth.',False)]:
  for c in text:
   cell=digits[ord(c)]if superior else cells[ord(c)]
   if x+cell.width>264:break
   im.paste(cell,(x,0));x+=cell.width
 return im

def card(rows,path):
 heights=[38+4*r[1][72].height for r in rows]
 im=Image.new('RGB',(1100,sum(heights)+12),'white');draw=ImageDraw.Draw(im);y=8
 for (label,cells,digits),rh in zip(rows,heights):
  box=cells[72].getbbox();db=digits[49].getbbox();assert db[1]==min(box[1],cells[72].height-5)
  draw.text((14,y),f'{label} | H top = {box[1]}, number top = {db[1]} (4x native pixels)',fill='black')
  native=strip(cells,digits);im.paste(native.resize((1056,native.height*4),Image.Resampling.NEAREST).convert('RGB').point(lambda p:255-p),(14,y+22));y+=rh
 im.save(path)

def comparison_cards():
 from superscript_strikes import current,run,example,paste
 from PIL import ImageFont
 label=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',20)
 title=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',27)
 records=json.loads((ROOT/'fonts/build/bdf/generation-report.json').read_text())['private_faces']
 for family in ['Serif','Sans','Book','Mono']:
  card_image=Image.new('RGB',(1240,1055),'white');draw=ImageDraw.Draw(card_image)
  draw.text((18,10),f'BetaWise {family} — shared fallback versus selected superscripts',font=title,fill='black')
  draw.text((18,48),'4× exact pixels; both choices align to the same body capital top.',font=label,fill='#555555')
  for row,(lines,size)in enumerate([(3,'Large'),(4,'Medium'),(5,'Small'),(6,'Tiny')]):
   folder=ROOT/'fonts/build/bdf'/('BetaWise'+family);stem=f'BetaWise{family}-{size}'
   body=fontgen.load(folder/(stem+'-Regular.bdf'),'iso8859-1',63)
   selected=fontgen.load(folder/'private'/(stem+'-SmallCaps.bdf'),'iso8859-1','blank')
   policy=next(r['digit_policy']for r in records if r['family']==family and r['lines']==lines)
   top=body[72].getbbox()[1];old=current(body[72].height,top)
   y=95+row*235
   draw.text((18,y),f'{size} · {lines} lines per screen',font=title,fill='black')
   note=f"Selected native {policy['ink_height']}px digits"if policy['kind']=='native'else'Selected: TI small 3×5'
   for col,(text,digits)in enumerate([('TI small 3×5 digits',old),(note,selected)]):
    x=18+col*615;draw.text((x,y+39),text,font=label,fill='#245c89')
    numbers=run(body,digits,'0123456789',True);context=example(body,digits)
    assert numbers.width*4<590 and context.width*4<590
    for digit in range(48,58):assert digits[digit].getbbox()[1]==top
    paste(card_image,numbers,x,y+73);paste(card_image,context,x,y+142)
   draw.line((18,y+225,1220,y+225),fill='#cccccc')
  card_image.save(OUT/f'{family.lower()}-original-vs-selected.png')


def main():
 OUT.mkdir(parents=True,exist_ok=True)
 comparison_cards()
 for lines,size in [(3,'Large'),(4,'Medium'),(5,'Small'),(6,'Tiny')]:
  rows=[]
  for family in ['Serif','Sans','Book','Mono']:
   folder=ROOT/'fonts/build/bdf'/('BetaWise'+family);stem=f'BetaWise{family}-{size}'
   cells=fontgen.load(folder/(stem+'-Regular.bdf'),'iso8859-1',63)
   private=fontgen.load(folder/'private'/(stem+'-SmallCaps.bdf'),'iso8859-1','blank')
   rows.append((f'BetaWise {family} {size} ({lines} lines)',cells,private))
  card(rows,OUT/f'betawise-{lines}-lines.png')
 inventory=json.loads((ROOT/'research/abi-audit/rom-inventory.json').read_text())
 record=next(r for r in inventory if r['name']=='neo_3_21');rom=(ROOT.parent/record['path']).read_bytes()
 rows=[]
 for name,ptr in [('System 9px (7 lines)',0x44d592),('System 6x16 (4 lines)',0x44af8e)]:
  cells=binary_font(rom,ptr,record['base']);rows.append((name,cells,fallback(cells)))
 for size,height in [('small',11),('medium',13),('large',16),('vlarge',21),('xlarge',32)]:
  data=(ROOT.parent/'Ghidra/Alphasmart Neo/SmartApplets'/f'neofont{size}.os3kapp').read_bytes();found=[]
  for i in range(len(data)-16):
   h,w,st,p,wp,op,bp=struct.unpack_from('>4BIII',data,i)
   if h==height and 1<w<40 and p==0 and 60<wp<len(data)-256 and 60<op<len(data)-512 and 60<bp<len(data):found.append(i)
  assert len(found)==1,(size,found)
  cells=binary_font(data,found[0],0);rows.append((f'Vendor {size} ({height}px)',cells,fallback(cells)))
 card(rows,OUT/'system-vendor.png');print(OUT)
if __name__=='__main__':main()
