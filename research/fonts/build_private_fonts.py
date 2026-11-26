#!/usr/bin/env python3
"""Private faces: native Adobe small capitals in three styles and superscripts."""
import argparse
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont
from research_paths import BUILD, ensure_bdfs
from build_superscripts import select as select_digits
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'fonts'))
sys.path.insert(0,str(ROOT/'os3k'))
import fontgen
from charsets import load as load_neous
from charsets.smallcaps import load as load_smallcaps


def generate(body_root,output_root,x11_root=ROOT/'fonts/upstream'):
    import build_fonts as recipe
    charset=load_smallcaps()
    neo=load_neous(ROOT/'os3k/charsets/neo-us.txt')
    inverse={code:slot for slot,code in neo.items() if code is not None}
    codes=tuple(sorted(set(neo.values())-{None}))
    records=[]
    for family in ('Serif','Sans','Book','Mono'):
        folder=Path('BetaWise'+family)
        for lines,size in recipe.SIZES.items():
            faces=[fontgen.load(body_root/folder/f'BetaWise{family}-{size}-{style}.bdf','iso8859-1',63)
                   for style in ('Regular','Bold','Italic')]
            raw,ascent,descent=fontgen.load_bdf(body_root/folder/f'BetaWise{family}-{size}-Regular.bdf')
            height=ascent+descent
            targets=[face[ord('x')].getbbox() for face in faces]
            source_meta=None
            if lines<6:
                native_pixel=int(next(row.split()[1] for row in (body_root/folder/f'BetaWise{family}-{size}-Regular.bdf').read_text().splitlines() if row.startswith('PIXEL_SIZE ')))
                choices=[]
                for option in recipe.strikes(x11_root,family,codes):
                    if option['pixels']>=native_pixel:continue
                    original=[recipe.source(path,codes)[1] for path in option['paths'][:3]]
                    caps=[max(y for x,y in face[72]['points'])-min(y for x,y in face[72]['points'])+1 for face in original]
                    xheights=[box[3]-box[1] for box in targets]
                    if not all(xh<=cap<=xh+1 for xh,cap in zip(xheights,caps)):continue
                    converted=[];valid=True
                    for index,face in enumerate(original):
                        offset=targets[index][3]-max(y for x,y in face[72]['points'])-1
                        images={}
                        for letter in charset['letters']:
                            for c in letter['text']:
                                code=ord(c)
                                if code not in face:valid=False;break
                                width,points,_=recipe.horizontal(face[code],None,False)
                                limit=min(height,65-(lines-1)*height)
                                if any(y+offset<0 or y+offset>=limit for x,y in points):valid=False;break
                                image=Image.new('1',(width,height))
                                for x,y in points:image.putpixel((x,y+offset),1)
                                images[code]=image
                        converted.append(images)
                    if valid:
                        score=(sum(cap-xh for cap,xh in zip(caps,xheights)),option['pixels'],option['dpi'])
                        choices.append((score,converted,option,caps))
                if not choices:raise ValueError(f'No unscaled small-cap source for {family} {lines}')
                _,converted,option,caps=min(choices,key=lambda c:c[0])
                source_meta=dict(pixels=option['pixels'],points=option['points'],dpi=option['dpi'],
                                 paths=[recipe.source_name(p) for p in option['paths'][:3]],cap_heights=caps)
            cells={};names={};origins={}
            for letter in charset['letters']:
                for index,style in enumerate(charset['styles']):
                    slot=int(letter[style],16)
                    components=[faces[index][inverse[ord(c)]] if lines==6 else converted[index][ord(c)] for c in letter['text']]
                    image=Image.new('1',(sum(g.width for g in components),height));x=0
                    for component in components:image.paste(component,(x,0));x+=component.width
                    cells[slot]=image
                    names[slot]='sc_'+style+'_'+'_'.join(f'{ord(c):04X}' for c in letter['text'])
                    origins[slot]=dict(text=letter['text'],style=style,source_slots=[f'{inverse[ord(c)]:02X}' for c in letter['text']])
            body_pixels=int(next(row.split()[1] for row in (body_root/folder/f'BetaWise{family}-{size}-Regular.bdf').read_text().splitlines() if row.startswith('PIXEL_SIZE ')))
            digit_images,digit_policy=select_digits(recipe,family,faces[0],body_pixels,x11_root)
            for digit in range(10):
                slot=int(charset['superscript_digits'][digit],16)
                cells[slot]=digit_images[48+digit];names[slot]=f'superior_{digit}'
            assert len(cells)==196
            assert not set(cells)&{int(c,16) for c in charset['reserved']}
            relative=folder/'private'/f'BetaWise{family}-{size}-SmallCaps.bdf'
            path=output_root/relative;path.parent.mkdir(parents=True,exist_ok=True)
            write_bdf(path,family,cells,names,ascent,descent,source_meta)
            parsed,aa,dd=fontgen.load_bdf(path)
            assert (aa,dd)==(ascent,descent)
            for slot,image in cells.items():
                advance,box,rect,bitmap=parsed[slot]
                assert advance==(image.width,0)
                assert bitmap.crop(rect).tobytes()==image.tobytes()
            records.append(dict(family=family,lines=lines,file=str(relative),height=height,ascent=ascent,
                                letters=186,digits=10,source=source_meta,
                                capital_policy='Exact accepted native uppercase cells' if lines==6 else 'Unscaled same-family Adobe capitals at x-height or +1px',
                                digit_policy=digit_policy,
                                origins={f'{slot:02X}':origin for slot,origin in origins.items()}))
    return records


def write_bdf(path,family,cells,names,ascent,descent,source):
    height=ascent+descent;width=max(g.width for g in cells.values())
    pixels,points,dpi=(source['pixels'],source['points'],source['dpi']) if source else (8,8,75)
    props=[f'FONT_ASCENT {ascent}',f'FONT_DESCENT {descent}',
           'COPYRIGHT "Copyright 1984-1989, 1994 Adobe Systems Incorporated. Copyright 1988, 1994 Digital Equipment Corporation. See fonts/LICENSE.md."',
           f'FAMILY_NAME "BetaWise {family} Private"','CHARSET_REGISTRY "NEO-SMALLCAPS"','CHARSET_ENCODING "1"']
    lines=['STARTFONT 2.1','COMMENT Generated by research/fonts/build_private_fonts.py.',
           'COMMENT Charset: os3k/charsets/neo-smallcaps.json. Missing slots are intentionally unassigned.',
           'COMMENT Native capitals and selected smaller-strike digits are translated without rescaling; 3x5 fallback where needed.',
           f'FONT -betawise-{family.lower()}-medium-r-normal--{pixels}-{points*10}-{dpi}-{dpi}-p-0-neo_smallcaps-1',
           f'SIZE {points} {dpi} {dpi}',f'FONTBOUNDINGBOX {width} {height} 0 {-descent}',f'STARTPROPERTIES {len(props)}',
           *props,'ENDPROPERTIES',f'CHARS {len(cells)}']
    for slot,image in sorted(cells.items()):
        lines += [f'STARTCHAR {names[slot]}',f'ENCODING {slot}','SWIDTH 500 0',
                  f'DWIDTH {image.width} 0',f'BBX {image.width} {height} 0 {-descent}','BITMAP']
        for y in range(height):
            row=0
            for x in range(image.width):row=(row<<1)|bool(image.getpixel((x,y)))
            lines.append(f'{row<<((-image.width)%8):0{2*((image.width+7)//8)}X}')
        lines.append('ENDCHAR')
    path.write_text('\n'.join(lines+['ENDFONT','']))


def specimen(records,body_root,private_root):
    charset=load_smallcaps()
    index={l['text']:l for l in charset['letters']}
    card=Image.new('RGB',(2100,1040),'white');draw=ImageDraw.Draw(card)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',22)
    draw.text((15,10),'Six-line private faces — native capitals and selected superscript digits (3×)',font=font,fill='black')
    for i,style in enumerate(('Regular','Bold','Italic')):draw.text((15+i*695,45),style,font=font,fill='black')
    for row,record in enumerate(r for r in records if r['lines']==6):
        top=90+row*235;family=record['family'];draw.text((15,top),'BetaWise '+family,font=font,fill='#245c89')
        private=fontgen.load(private_root/record['file'],'iso8859-1','blank')
        for i,style in enumerate(charset['styles']):
            body=fontgen.load(body_root/f'BetaWise{family}/BetaWise{family}-Tiny-{style.title()}.bdf','iso8859-1',63)
            def run(images,yy):
                image=Image.new('1',(sum(g.width for g in images),11));x=0
                for g in images:image.paste(g,(x,0));x+=g.width
                mask=image.resize((image.width*3,33),Image.Resampling.NEAREST);x=15+i*695
                assert mask.width<680
                card.paste('black',(x,yy,x+mask.width,yy+33),mask)
            run([body[c] for c in b'The lord is good.'],top+38)
            run([body[c] for c in b'The ']+[private[int(index[c][style],16)] for c in 'LORD']+[body[c] for c in b' is good.'],top+88)
            run([private[int(index[c][style],16)] for c in ('À','É','Ñ','SS','IJ')]+[body[32]]+[private[0x30+d] for d in range(10)],top+138)
    target=BUILD/'smallcaps/six-line.png';target.parent.mkdir(parents=True,exist_ok=True);card.save(target)
    return target


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--x11-root',type=Path,default=ROOT/'fonts/upstream')
    parser.add_argument('--body-root',type=Path,default=ROOT/'fonts/build/bdf')
    parser.add_argument('--output',type=Path,default=ROOT/'fonts/build/bdf')
    args=parser.parse_args()
    ensure_bdfs()
    BUILD.mkdir(parents=True,exist_ok=True)
    records=generate(args.body_root,args.output,args.x11_root)
    (BUILD/'private-faces.json').write_text(json.dumps(records,indent=2)+'\n')
    print(specimen(records,args.body_root,args.output))


if __name__=='__main__':main()
