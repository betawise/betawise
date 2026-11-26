#!/usr/bin/env python3
"""Native Lucida/Bright exact-x-height small caps beside current bodies and Adobe."""
import itertools
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont
from research_paths import BUILD, generation_report
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent))
import build_fonts as recipe
OUT=BUILD/'smallcaps/lucida-comparison'
STYLES=recipe.STYLES[:3]


def main():
    import subprocess
    if not (OUT.parent/'alternative-sources.json').exists():
        subprocess.run([sys.executable,str(Path(__file__).with_name('audit_smallcap_alternatives.py'))],check=True)
    if not (OUT.parent/'sources.json').exists():
        subprocess.run([sys.executable,str(Path(__file__).with_name('smallcaps_sources.py'))],check=True)
    alternatives=json.loads((OUT.parent/'alternative-sources.json').read_text())['fonts']
    selection=json.loads((OUT.parent/'sources.json').read_text())
    bodies=generation_report()['fonts']
    mapping=recipe.load(ROOT/'os3k/charsets/neo-us.txt')
    codes=tuple(sorted(set(mapping.values())-{None}))
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',20)
    title=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',28)
    OUT.mkdir(parents=True,exist_ok=True)
    report=[];links=[]
    for family in recipe.FAMILIES:
        groups=[]
        for lines in (3,4,5):
            record=next(r for r in selection if r['family']==family and r['lines']==lines)
            lucidas=[]
            for source_family in ('b&h lucida','b&h lucidabright'):
                weights=['medium r','bold r' if source_family=='b&h lucida' else 'demibold r','medium i']
                options=[[a for a in alternatives if a['family']==source_family and a['style']==weights[i]
                          and a['H_height']==record['x_heights'][i]] for i in range(3)]
                if not all(options):continue
                # A mixed-size body such as Mono 3-line has 8/9/8 x-height.
                # Keep common strikes when possible; otherwise label each source.
                common=set(Path(a['path']).parent.name+'|'+str(a['pixels']) for a in options[0])
                for rows in options[1:]:common &= {Path(a['path']).parent.name+'|'+str(a['pixels']) for a in rows}
                if common:
                    combinations=[tuple(next(a for a in rows if Path(a['path']).parent.name+'|'+str(a['pixels'])==key) for rows in options) for key in sorted(common)]
                else:combinations=list(itertools.product(*options))
                for combo in combinations:
                    lucidas.append(dict(name='Lucida' if source_family=='b&h lucida' else 'Lucida Bright (Demibold in Bold column)',
                                        sources=[a['path'] for a in combo],cap_heights=[a['H_height'] for a in combo],
                                        pixels=[a['pixels'] for a in combo],dpi=[Path(a['path']).parent.name for a in combo]))
            if not lucidas:continue
            adobe={}
            for a in record['preferred']:adobe.setdefault(tuple(a['cap_heights']),a)
            choices=[dict(name='Adobe option',sources=a['sources'],cap_heights=a['cap_heights'],
                          pixels=[a['pixels']]*3,dpi=[str(a['dpi'])+'dpi']*3) for a in adobe.values()]+lucidas
            groups.append((record,choices))
        # One body-reference row plus two specimen rows for each source option.
        height=120+sum(120+len(choices)*185 for record,choices in groups)
        card=Image.new('RGB',(2220,height),'white');draw=ImageDraw.Draw(card)
        draw.text((16,10),f'BetaWise {family} bodies · exact-height Lucida / Lucida Bright small capitals',font=title,fill='black')
        draw.text((16,49),'Original pixels at 3×. Lucida matches x-height in every column; Adobe options are x-height or +1px.',font=font,fill='#555555')
        for i,style in enumerate(STYLES):draw.text((16+i*735,80),style,font=title,fill='black')
        y=120
        for record,choices in groups:
            body=next(r for r in bodies if r['family']==family and r['lines']==record['lines'])
            glyphs=[recipe.fontgen.load(ROOT/'fonts/build/bdf'/p,'iso8859-1',63) for p in body['files'][:3]]
            def paste_run(images,index,yy):
                image=Image.new('1',(sum(g.width for g in images),body['pitch']));x=0
                for g in images:image.paste(g,(x,0));x+=g.width
                mask=image.resize((image.width*3,image.height*3),Image.Resampling.NEAREST)
                assert mask.width<715,(family,record['lines'],mask.width)
                x=16+735*index
                card.paste('black',(x,yy,x+mask.width,yy+mask.height),mask)
            draw.text((16,y),f'{record["lines"]} lines · body x-height '+ '/'.join(map(str,record['x_heights']))+'px · body reference',font=font,fill='black')
            for i,g in enumerate(glyphs):paste_run([g[c] for c in b'The lord in heaven.'],i,y+31)
            y+=110
            for choice in choices:
                draw.text((16,y),choice['name']+' · cap H '+ '/'.join(map(str,choice['cap_heights']))+'px',font=font,fill='#245c89')
                for i,path in enumerate(choice['sources']):
                    _,face=recipe.source(Path(path),codes)
                    target=glyphs[i][ord('x')].getbbox()
                    h=face[72]['points'];offset=target[3]-max(py for px,py in h)-1
                    native_h=max(py for px,py in h)-min(py for px,py in h)+1
                    if choice['name'].startswith('Lucida'):assert native_h==target[3]-target[1]
                    # Verify every allocated form fits, not just the displayed word.
                    encoding=json.loads((OUT.parent/'encoding.json').read_text())
                    for letter in encoding['letters']:
                        for c in letter['text']:
                            assert ord(c) in face,(path,c)
                            assert all(0<=py+offset<body['usable_ink_rows'] for px,py in face[ord(c)]['points']),(path,c)
                    def small(c):
                        width,points,_=recipe.horizontal(face[ord(c)],None,False)
                        image=Image.new('1',(width,body['pitch']))
                        for px,py in points:image.putpixel((px,py+offset),1)
                        return image
                    def mixed(parts,yy):
                        images=[]
                        for sc,text in parts:
                            images += [small(c) if sc and c!=' ' else glyphs[i][ord(c)] for c in text]
                        paste_run(images,i,yy)
                    x=16+i*735
                    draw.text((x,y+27),f'{choice["pixels"][i]}px / {choice["dpi"][i]}',font=font,fill='#666666')
                    mixed([(False,'The '),(True,'LORD'),(False,' in '),(True,'HEAVEN'),(False,'.')],y+54)
                    mixed([(False,'x '),(True,'ÀÉÑÖ Œ SS IJ'),(False,' x')],y+121)
                report.append(dict(body_family=family,lines=record['lines'],x_heights=record['x_heights'],**choice))
                y+=185
            draw.line((16,y,2200,y),fill='#aaaaaa');y+=10
        assert y<=height
        filename=family.lower()+'.png';card.save(OUT/filename)
        links.append(f'<h2>BetaWise {family}</h2><a href="{filename}"><img src="{filename}" alt="{family} with Lucida and Adobe small capitals"></a>')
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Lucida small-cap comparisons</title><style>body{font:18px sans-serif;margin:24px}img{max-width:100%;image-rendering:pixelated}</style><h1>Exact-height Lucida small capitals</h1><p>Columns: Regular, Bold, Italic. Sources are translated to the body baseline without resizing or clipping. Mono 3-line uses separately labelled strikes to match its different per-style x-heights.</p>'+''.join(links))
    print(f'{len(report)} three-style source comparisons; {OUT}/index.html')


if __name__=='__main__':main()
