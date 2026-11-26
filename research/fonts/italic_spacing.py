#!/usr/bin/env python3
"""Audit native left overhangs and preview clipping Serif italic j in context."""
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont
from research_paths import BUILD, generation_report
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'fonts'))
sys.path.insert(0, str(ROOT/'os3k'))
import fontgen
from charsets import load
OUT = BUILD / 'italic-spacing'
OUT.mkdir(parents=True,exist_ok=True)
mapping = load(ROOT/'os3k/charsets/neo-us.txt')
codes = tuple(sorted(set(mapping.values())-{None}))
report = generation_report()
records = []
for record in report['fonts']:
    if record['family'] == 'Terminal': continue
    for index in (2, 3):
        _, face = fontgen.read_unicode_source(ROOT/record['sources'][index], codes)
        affected = []
        for slot in list(range(32,127)) + [s for s in range(128,256) if s not in (129,141,143,144,157)]:
            glyph = face[mapping[slot]]
            left = min((x for x,y in glyph['points']), default=0)
            if left < 0:
                affected.append(dict(char=chr(slot), left_overhang=-left,
                                     clipped_pixels=sum(x<0 for x,y in glyph['points'])))
        records.append(dict(family=record['family'], lines=record['lines'],
                            style=('Italic' if index==2 else 'BoldItalic'), glyphs=affected,
                            shifted_in_current_font=record['family']!='Mono'))
(OUT/'audit.json').write_text(json.dumps(records, indent=2)+'\n')
r = next(r for r in report['fonts'] if r['family']=='Serif' and r['lines']==3)
_, face = fontgen.read_unicode_source(ROOT/r['sources'][2], codes)
glyphs = fontgen.load(ROOT/'fonts/build/bdf'/r['files'][2], 'iso8859-1', 63)
native = face[ord('j')]
replacement = Image.new('1',(native['advance'],r['pitch']))
for x,y in native['points']:
    if 0<=x<replacement.width and 0<=y+r['baseline']<replacement.height:
        replacement.putpixel((x,y+r['baseline']),1)
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',22)
card = Image.new('RGB',(1100,610),'white'); draw=ImageDraw.Draw(card)
draw.text((20,12),'BetaWise Serif · 3-line Italic · native j versus clipped hook',font=font,fill='black')
for row, clip in enumerate((False,True)):
    yy=58+row*265
    draw.text((20,yy),('Current: j shifted right, 8px cell' if not clip else 'Preview: left hook clipped, native 5px advance'),font=font,fill='black')
    text='enjoys'; w=sum((replacement if clip and c=='j' else glyphs[ord(c)]).width for c in text)
    im=Image.new('1',(w,21));x=0
    for c in text:
        g=replacement if clip and c=='j' else glyphs[ord(c)]
        im.paste(g,(x,0));x+=g.width
    mask=im.resize((w*8,168),Image.Resampling.NEAREST)
    card.paste('black',(20,yy+36,20+w*8,yy+204),mask)
    small=im.resize((w*2,42),Image.Resampling.NEAREST)
    card.paste('black',(750,yy+75,750+w*2,yy+117),small)
    draw.text((750,yy+125),'2× view',font=font,fill='#555555')
card.save(OUT/'enjoys.png')
for family in ('Serif','Sans','Book','Mono'):
    print(family)
    for r in records:
        if r['family']==family:
            print(r['lines'],r['style'], ' '.join(f"{g['char']}:{g['left_overhang']}" for g in r['glyphs']))
print('j clipped pixels:',sum(x<0 for x,y in native['points']))
