from pathlib import Path
import sys,gzip,json
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'fonts'));sys.path.insert(0,str(root/'research/fonts'));import native,fontgen
from PIL import PcfFontFile
from research_paths import ensure_bdfs
ensure_bdfs()
out=root/'research/font-policy/build'
out.mkdir(parents=True,exist_ok=True)
mapping=native.load(root/'os3k/charsets/neo-us.txt');codes=tuple(sorted(set(mapping.values())))
records=[]
def pts(g):
 if g is None:return set()
 _,(left,top,_,_),rect,bitmap=g;bitmap=bitmap.crop(rect);shift=max(0,-left)
 return {(x+left+shift,y+top)for y in range(bitmap.height)for x in range(bitmap.width)if bitmap.getpixel((x,y))}
for family,(stem,source_styles)in native.FAMILIES.items():
 row={'family':family,'styles':[]}
 for style,srcstyle in zip(native.STYLES,source_styles):
  p=root/f'fonts/build/bdf/BetaWise{family}/BetaWise{family}-Tiny-{style}.bdf';old,_,_=fontgen.load_bdf(p)
  source=Path('/usr/share/fonts/X11/75dpi')/f'{stem}{srcstyle}08.pcf.gz'
  direct=native.read_source(source,codes)
  with gzip.open(source,'rb')as f:pcf=PcfFontFile.PcfFontFile(f,charset_encoding='cp1252')
  changes=[]
  for c in native.CP:
   a=pts(pcf.glyph[c]);b=pts(old[c]);_,unicode_points=native.normalized(direct[mapping[c]])
   assert a==unicode_points,(source,c,'Unicode remapping discrepancy')
   if a!=b:changes.append(dict(slot=f'{c:02X}',char=chr(mapping[c]),removed=len(a-b),added=len(b-a)))
  row['styles'].append(dict(style=style,changed_glyphs=len(changes),changes=changes))
 print(family,[(s['style'],s['changed_glyphs'])for s in row['styles']]);records.append(row)
# Larger current Mono exported per-character overhang widths, not one universal cell.
mono=[]
for size in ['Large','Medium','Small','Tiny']:
 for style in native.STYLES:
  p=root/f'fonts/build/bdf/BetaWiseMono/BetaWiseMono-{size}-{style}.bdf';gs,_,_=fontgen.load_bdf(p)
  mono.append(dict(size=size,style=style,widths=sorted({g[0][0]for g in gs if g})))
(out/'current-six-line-edits.json').write_text(json.dumps(dict(fonts=records,current_mono_widths=mono),indent=2,ensure_ascii=False)+'\n')
