from pathlib import Path
import json,sys,html
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'fonts'));import fontgen
out=root/'research/font-policy/build';out.mkdir(parents=True,exist_ok=True);
sys.path.insert(0,str(root/'research/fonts'));from research_paths import ensure_bdfs
ensure_bdfs()
import subprocess
subprocess.run([sys.executable,str(root/'research/fonts/native.py')],check=True)
r=json.loads((root/'research/fonts/build/native-preview/native-selection.json').read_text());F=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18);T=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',24)
styles=['Regular','Bold','Italic','BoldItalic'];sizes={3:'Large',4:'Medium',5:'Small',6:'Tiny'}
text='The quick brown fox jumps over the lazy dog. COGQ cç ijmw 0123456789. ÀÁÂÃÄÅ ÉÊË ÑÖÜ ŠŽŸ ß. '
def page(gs,lines):
 im=Image.new('1',(264,65));x=y=0
 for c in (text*8).encode('cp1252'):
  g=gs[c]
  if x+g.width>264:x=0;y+=g.height
  if y//g.height>=lines:break
  if y+g.height>65:
   assert not g.crop((0,65-y,g.width,g.height)).getbbox(), 'nonblank overflow in specimen'
  im.paste(g,(x,y));x+=g.width
 return im
links=[]
for family in ['Serif','Sans','Book','Mono']:
 image=Image.new('RGB',(1220,90+4*640),'white');d=ImageDraw.Draw(image)
 d.text((12,8),family+' — edited / standard-policy preview',font=T,fill='black')
 d.text((12,44),'2× exact source pixels. Standard side includes only permitted clipping; no hand repairs.',font=F,fill='#555555')
 for row,lines in enumerate([3,4,5,6]):
  meta=next(f for f in r['fonts']if f['family']==family and f['lines']==lines);y=90+row*640
  label=f'{lines} lines: '+(f"native {meta['pixels']}px, {meta['dpi']}dpi"if meta['available']else'no native fit under the four-slot rule')
  d.text((12,y),label,font=T,fill='black')
  for index,style in enumerate(styles):
   yy=y+38+index*146;d.text((12,yy),style,font=F,fill='#444444')
   rel=Path('BetaWise'+family)/f'BetaWise{family}-{sizes[lines]}-{style}.bdf'
   for col,base in enumerate([root/'fonts/build/bdf',root/'research/fonts/build/native-preview']):
    if col and not meta['available']:continue
    gs=fontgen.load(base/rel,'iso8859-1',63);mask=page(gs,lines).resize((528,130),Image.Resampling.NEAREST)
    image.paste('black',(140+col*540,yy,668+col*540,yy+130),mask)
   if not meta['available']:d.text((710,yy+35),'Unavailable',font=F,fill='#9c2f20')
  d.line((0,y+630,1220,y+630),fill='#bbbbbb')
 name=family.lower()+'.png';image.save(out/name);links.append(f'<h2>{family}</h2><img src="{name}" alt="{family} edited versus native">')
(out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Native bitmap policy preview</title><style>body{font:17px sans-serif;margin:24px}img{max-width:100%;image-rendering:pixelated}</style><h1>Native bitmap policy preview</h1><p>Left: current edited fonts. Right: stock native sources under the four-slot rule, giving keyboard-entered characters priority. No shipping fonts changed. Missing six-line cells require a policy decision.</p>'+''.join(links))
print(out/'index.html')
