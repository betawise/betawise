import sys,json,re
from pathlib import Path
from PIL import Image,ImageChops
root=Path(__file__).resolve().parents[4]
from neo_reader import bitmap,FONT

def native_code(character):
    return {'‘':0x91,'’':0x92,'“':0x93,'”':0x94}.get(character,ord(character))

font=bitmap(FONT,(1536,8));digits=json.loads((root/'betawise/research/fonts/superscript-3x5.json').read_text())['columns']
def paragraph(verses,numbers=True):
 # Explicit typeset input: each verse marker, one separator, then source words.
 words=[]
 for i,v in enumerate(verses,1):
  if numbers:words.append([(d,True)for d in str(i)])
  words.extend([[(c,False)for c in w]for w in v.split(' ')])
 lines=[];line=[];width=0
 for word in words:
  n=sum(4 if sup else 6 for c,sup in word)
  if line and width+6+n>264:lines.append(line);line=[];width=0
  if line:line.append((' ',False));width+=6
  for c,sup in word:
   if width+(4 if sup else 6)>264:lines.append(line);line=[];width=0
   line.append((c,sup));width+=4 if sup else 6
 if line:lines.append(line)
 return lines

def render(lines, height=8, body_font=None, profile=None):
 im=Image.new('1',(264,65));px=im.load()
 if profile:
  w=profile['widths'][72];g=profile['glyphs'][72]
  ink=lambda y:any(g[y//8*w+x]>>(y%8)&1 for x in range(w))
 elif body_font is not None:
  ink=lambda y:any(body_font[72*12+y//8*6+x]>>(y%8)&1 for x in range(6))
 else:
  ink=lambda y:any(font[y*1536+72*6+x]for x in range(6))
 shift=min(next((y for y in range(height)if ink(y)),0),height-5)
 for r,line in enumerate(lines[:6 if height==11 else 65//height]):
  x=0
  for c,sup in line:
   w=4 if sup else (profile['widths'][native_code(c)] if profile else 6)
   for y in range(height):
    for dx in range(w):
     if sup:bit=dx<4 and y>=shift and ((digits[int(c)][dx]>>(y-shift))&1)
     elif profile:
      glyph=profile['glyphs'][native_code(c)];bit=(glyph[(y//8)*w+dx]>>(y%8))&1
     elif body_font is not None:bit=(body_font[native_code(c)*12+(y//8)*6+dx]>>(y%8))&1
     else:bit=font[y*1536+native_code(c)*6+dx]
     if bit and r*height+y<65:px[x+dx,r*height+y]=1
   x+=w
 return im

def typeset(verses,numbers=True,widths=None,screen_width=264):
    """Independent source/position typesetter, with markers glued to verse text."""
    widths=widths or [6]*256;words=[];raw=0;verse_starts=[]
    for vi,text in enumerate(verses,1):
        if vi>1:raw+=1
        verse_starts.append(raw);start=raw;marker=[]
        if numbers:
            raw+=3
            for d in str(vi):marker.append((d,True,raw));raw+=1
            raw+=3
        for wi,word_text in enumerate(text.split(' ')):
            if wi:raw+=1;start=raw
            word=marker[:]if wi==0 else []
            for c in word_text:word.append((c,False,raw));raw+=1
            words.append((start,raw,word))
    lines=[];line=[];x=0;positions={};line_starts=[]
    for start,end,word in words:
        size=sum(4 if sup else widths[native_code(c)] for c,sup,o in word)
        if line and x+widths[32]+size>screen_width:
            lines.append(line);line=[];x=0
        if not line:line_starts.append(start)
        else:
            positions[start-1]=(len(lines),x);line.append((' ',False));x+=widths[32]
        positions[start]=(len(lines),x)
        for c,sup,o in word:
            w=4 if sup else widths[native_code(c)]
            if x+w>screen_width:lines.append(line);line=[];x=0;line_starts.append(o)
            positions[o]=(len(lines),x);line.append((c,sup));x+=w;positions[o+1]=(len(lines),x)
        positions[end]=(len(lines),x)
    if line:lines.append(line)
    return lines,positions,line_starts,verse_starts

def system_font():
    """Verified fixed 6x16 font from the pinned original Neo 3.21 ROM."""
    import hashlib,struct
    inventory=json.loads((root/'betawise/research/abi-audit/rom-inventory.json').read_text())
    record=next(r for r in inventory if r['name']=='neo_3_21')
    rom=(root/record['path']).read_bytes()
    assert hashlib.sha256(rom).hexdigest()==record['sha256']
    descriptor=rom[0x44af8e-record['base']:0x44af9e-record['base']]
    h,w,stride,pad,widths,offsets,data=struct.unpack('>4BIII',descriptor)
    assert(h,w,stride,widths,offsets)==(16,6,12,0,0)
    pixels=rom[data-record['base']:data-record['base']+256*stride]
    assert len(pixels)==3072
    return pixels


def captured_font(out,index,prefix="font"):
    """Font source bytes, independent of LCD pixels; require original asset backing."""
    import struct,hashlib
    descriptor=(out/f'{prefix}-{index:02}.bin').read_bytes()
    h,w,stride,pad,wp,op,bp=struct.unpack('>4BIII',descriptor)
    raw=(out/f'{prefix}-pixels-{index:02}.bin').read_bytes()
    originals=[p.read_bytes()for p in (out/'artifacts').glob('*.os3kapp')]
    originals+=[p.read_bytes()for p in (out/'artifacts').glob('*.OS3KApp')]
    originals+=[(root/'Ghidra/Alphasmart Neo/SmartApplets/os3kneorom.os3kos').read_bytes()]
    assert any(raw in b for b in originals),'font pixels not backed by a retained original image'
    widths=list((out/f'{prefix}-widths-{index:02}.bin').read_bytes())if wp else [w]*256
    offsets=list(struct.unpack('>256H',(out/f'{prefix}-offsets-{index:02}.bin').read_bytes()))if op else [i*stride for i in range(256)]
    if wp:assert any(bytes(widths)in b for b in originals),'unverified width table'
    if op:assert any((out/f'{prefix}-offsets-{index:02}.bin').read_bytes()in b for b in originals),'unverified offset table'
    glyphs=[raw[offsets[c]:offsets[c]+widths[c]*((h+7)//8)]for c in range(256)]
    return dict(height=h,widths=widths,glyphs=glyphs,proportional=len(set(widths[32:127]))>1,sha256=hashlib.sha256(descriptor+raw+bytes(widths)).hexdigest())
