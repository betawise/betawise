#!/usr/bin/env python3
"""Read the shared private charset and inventory unscaled native small-cap sources."""
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

from research_paths import BUILD, generation_report
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent))
import build_fonts as recipe
from charsets.smallcaps import load as load_smallcaps, tables as smallcaps_tables

OUT = BUILD / 'smallcaps'
STYLES = recipe.STYLES[:3]


def height(points):
    return max(y for x,y in points)-min(y for x,y in points)+1


def render_cards(report, generated, codes):
    label=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',20)
    title=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',28)
    links=[]
    for family in recipe.FAMILIES:
        rows=[]
        for lines in (3,4,5):
            record=next(r for r in report if r['family']==family and r['lines']==lines)
            # Keep one original strike per distinct three-style cap-height vector.
            unique={}
            for candidate in record['closest']:
                unique.setdefault(tuple(candidate['cap_heights']),candidate)
            for candidate in sorted(unique.values(),key=lambda c:c['cap_heights']):
                rows.append((record,candidate))
        card=Image.new('RGB',(2220,120+len(rows)*245),'white');draw=ImageDraw.Draw(card)
        draw.text((16,10),f'BetaWise {family} — body text with native small capitals',font=title,fill='black')
        draw.text((16,48),'3× exact bitmap pixels. Blue labels identify alternatives; no glyph rescaling or clipping.',font=label,fill='#555555')
        for index,style in enumerate(STYLES):draw.text((16+index*735,82),style,font=title,fill='black')
        for row,(record,candidate) in enumerate(rows):
            body=next(r for r in generated['fonts'] if r['family']==family and r['lines']==record['lines'])
            top=125+row*245
            draw.text((16,top),f'{record["lines"]} lines · body x-height '+ '/'.join(map(str,record['x_heights']))+
                      'px · small-cap H '+ '/'.join(map(str,candidate['cap_heights']))+
                      f'px · native {candidate["pixels"]}px / {candidate["dpi"]}dpi',font=label,fill='#245c89')
            assert not candidate['missing'] and not candidate['overflows'],candidate
            for index,style in enumerate(STYLES):
                glyphs=recipe.fontgen.load(ROOT/'fonts/build/bdf'/body['files'][index],'iso8859-1',63)
                _,face=recipe.source(Path(candidate['sources'][index]),codes)
                target=glyphs[ord('x')].getbbox()
                offset=target[3]-(max(y for x,y in face[ord('H')]['points'])+1)
                def small(c):
                    glyph=face[ord(c)]
                    width,points,_=recipe.horizontal(glyph,None,False)
                    image=Image.new('1',(width,body['pitch']))
                    for px,py in points:
                        assert 0<=py+offset<body['usable_ink_rows']
                        image.putpixel((px,py+offset),1)
                    return image
                def run(parts,y):
                    images=[]
                    for sc,text in parts:
                        images.extend(small(c) if sc and c!=' ' else glyphs[ord(c)] for c in text)
                    image=Image.new('1',(sum(g.width for g in images),body['pitch']));x=0
                    for g in images:image.paste(g,(x,0));x+=g.width
                    mask=image.resize((image.width*3,image.height*3),Image.Resampling.NEAREST)
                    assert mask.width<715,(family,record['lines'],style,mask.width)
                    x=16+index*735
                    card.paste('black',(x,y,x+mask.width,y+mask.height),mask)
                run([(False,'The lord is good.')],top+32)
                run([(False,'The '),(True,'LORD'),(False,' is good.')],top+98)
                run([(False,'x '),(True,'ÀÉÑÖ Œ SS IJ'),(False,' x')],top+164)
            draw.line((16,top+232,2200,top+232),fill='#cccccc')
        name=family.lower()+'-in-context.png';card.save(OUT/name)
        links.append(f'<h2>{family}</h2><a href="{name}"><img src="{name}" alt="{family} body and small capitals"></a>')
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Small-cap native comparisons</title><style>body{font:18px sans-serif;margin:24px}img{max-width:100%;image-rendering:pixelated}</style><h1>Small capitals in body text</h1><p>Within each option: body-only reference, mixed body/small capitals, extended small capitals and composites. All three share the body baseline. Click cards for full size.</p>'+''.join(links))


def encoding_view():
    descriptor=load_smallcaps()
    lookup=smallcaps_tables(descriptor)
    letters=[dict(text=letter['text'],source_slot=letter['canonical'],
                  slots={style:letter[style] for style in descriptor['styles']})
             for letter in descriptor['letters']]
    decode=[None]*256
    for letter in letters:
        for style,slot in letter['slots'].items():
            decode[int(slot,16)]=dict(source_slot=letter['source_slot'],text=letter['text'],style=style)
    source_to_regular={f'{source:02X}':f'{lookup["variants"][index][0]:02X}'
                       for source,index in enumerate(lookup['source_to_index']) if index!=255}
    contract=dict(description='Generated research view of os3k/charsets/neo-smallcaps.json; edit the shared descriptor.',
                  optional_forms=[],required_forms=62,letters=letters,
                  superscript_slots={str(i):slot for i,slot in enumerate(descriptor['superscript_digits'])},
                  reserved_slots=descriptor['reserved'],source_to_regular=source_to_regular,decode=decode)
    return contract


def write_encoding():
    OUT.mkdir(parents=True,exist_ok=True)
    contract=encoding_view()
    (OUT/'encoding.json').write_text(json.dumps(contract,indent=2,ensure_ascii=False)+'\n')
    return contract


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    mapping=recipe.load(ROOT/'os3k/charsets/neo-us.txt')
    contract=write_encoding()
    letters=contract['letters']
    descriptor=load_smallcaps()
    occupied={int(slot,16) for letter in letters for slot in letter['slots'].values()}
    occupied.update(int(slot,16) for slot in descriptor['superscript_digits'])
    rom=(ROOT.parent/'Ghidra/Alphasmart Neo/SmartApplets/os3kneorom.os3kos').read_bytes()
    assert all(rom[0x3c7e0+s] == 0 for s in occupied), 'Private slot interpreted as an editor token'
    codes=tuple(sorted((set(mapping.values())-{None})|{ord('S'),ord('H'),ord('I'),ord('J')}))
    generated=generation_report()
    report=[]
    for family in recipe.FAMILIES:
        options=recipe.strikes(recipe.X11_ROOT,family,codes)
        for lines,size in recipe.SIZES.items():
            body=next(r for r in generated['fonts'] if r['family']==family and r['lines']==lines)
            bodies=[recipe.fontgen.load(ROOT/'fonts/build/bdf'/body['files'][index],'iso8859-1',63) for index in range(3)]
            targets=[g[ord('x')].getbbox() for g in bodies]
            xheights=[b[3]-b[1] for b in targets]
            candidates=[]
            for option in options:
                if option['pixels']>=body['pixels']:continue
                faces=[recipe.source(p,codes)[1] for p in option['paths'][:3]]
                cap_heights=[height(f[ord('H')]['points']) for f in faces]
                lost=[];missing=[]
                for index,face in enumerate(faces):
                    offset=targets[index][3]-(max(y for x,y in face[ord('H')]['points'])+1)
                    for letter in letters:
                        components=letter['text']
                        if any(ord(c) not in face for c in components):
                            missing.append(dict(style=STYLES[index],letter=letter['text']));continue
                        ys=[y+offset for c in components for x,y in face[ord(c)]['points']]
                        if min(ys)<0 or max(ys)>=body['usable_ink_rows']:
                            lost.append(dict(style=STYLES[index],letter=letter['text'],top=min(ys),bottom=max(ys)))
                candidates.append(dict(pixels=option['pixels'],points=option['points'],dpi=option['dpi'],
                                       cap_heights=cap_heights,exact=xheights==cap_heights,
                                       overflows=lost,missing=missing,sources=[str(p) for p in option['paths'][:3]]))
            # Prefer height matches, then complete bounds; never resize a source.
            ranked=sorted(candidates,key=lambda c:(max(abs(a-b) for a,b in zip(c['cap_heights'],xheights)),
                                                   len(c['missing']),len(c['overflows']),c['pixels'],c['dpi']))
            closest=[]
            if ranked:
                error=max(abs(a-b) for a,b in zip(ranked[0]['cap_heights'],xheights))
                closest=[c for c in ranked if max(abs(a-b) for a,b in zip(c['cap_heights'],xheights))==error]
            preferred=[c for c in ranked if not c['missing'] and not c['overflows']
                       and all(target<=cap<=target+1 for target,cap in zip(xheights,c['cap_heights']))]
            report.append(dict(preferred=preferred,closest=closest,family=family,lines=lines,body_pixels=body['pixels'],x_heights=xheights,
                               best=ranked[0] if ranked else None,candidates=candidates))
    (OUT/'sources.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    render_cards(report, generated, codes)
    for r in report:
        b=r['best'];print(r['family'],r['lines'],'x',r['x_heights'],'candidate',None if not b else (b['pixels'],b['cap_heights'],b['exact'],len(b['overflows'])))
    print(OUT)


if __name__=='__main__':main()
