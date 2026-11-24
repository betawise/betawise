#!/usr/bin/env python3
"""Convert hand-drawn X11 10-pixel bitmap faces; no TTF downsampling."""
from pathlib import Path
import gzip,json,hashlib
from PIL import Image,PcfFontFile
here=Path(__file__).resolve().parent
profiles=[];arrays=[]
for face,suffix in enumerate(['R','B','O','BO']):
 path=Path('/usr/share/fonts/X11/75dpi')/f'helv{suffix}10.pcf.gz'
 with gzip.open(path,'rb')as stream:font=PcfFontFile.PcfFontFile(stream)
 widths=[];offsets=[];data=[];glyphs=[]
 for c in range(256):
  code=c if 32<=c<127 else 32 if c<32 or c==127 else ord('?')
  (advance,_),box,src,bitmap=font.glyph[code]
  left,top,right,bottom=box;shift=max(0,-left)
  w=max(advance+shift,right+shift,1)
  im=Image.new('1',(w,12))
  assert top+9>=0 and bottom+9<=12,(path,code,box)
  im.paste(bitmap.crop(src),(left+shift,top+9))
  if c==0x95:
   w=6;im=Image.new('1',(w,12))
   for yy,row in enumerate(['0110','1111','1111','0110'],4):
    for xx,bit in enumerate(row,1):
     if bit=='1':im.putpixel((xx,yy),1)
  widths.append(w);offsets.append(len(data));glyphs.append([''.join('1'if im.getpixel((x,y))else'0' for x in range(w))for y in range(12)])
  for band in (0,8):
   for x in range(w):data.append(sum(1<<(y-band) for y in range(band,min(band+8,12))if im.getpixel((x,y))))
 def array(typ,key,values):return f'static const {typ} md_{key}_{face}[]={{'+','.join(map(str,values))+'};\n'
 arrays.extend([array('uint8_t','widths',widths),array('uint16_t','offsets',offsets),array('uint8_t','data',data)])
 profiles.append(dict(name=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),height=12,widths=widths,glyphs=glyphs))
(here/'MarkdownGlyphs.h').write_text('/* Converted X11 bitmap faces; see FONT-LICENSE.txt. */\n'+''.join(arrays))
(here/'markdown-font.json').write_text(json.dumps(profiles)+'\n')
