"""Deterministic same-family digit choice accepted from the specimen middle column."""
import json
from pathlib import Path
from PIL import Image
CODES=tuple(range(48,58))

def select(recipe,family,body,body_pixels,x11_root):
    cap_box=body[72].getbbox()
    top,cap=cap_box[1],cap_box[3]-cap_box[1]
    height=body[72].height
    original=json.loads(Path(__file__).with_name('superscript-3x5.json').read_text())
    candidates=[]
    for option in recipe.strikes(x11_root,family,CODES):
        _,face=recipe.source(option['paths'][0],CODES)
        if not all(c in face and face[c]['points'] for c in CODES):continue
        ys=[y for c in CODES for x,y in face[c]['points']]
        candidates.append(dict(option=option,face=face,ink_height=max(ys)-min(ys)+1,source_top=min(ys)))
    smaller=[c for c in candidates if c['option']['pixels']<body_pixels and c['ink_height']<cap]
    if smaller:
        chosen=min(smaller,key=lambda c:(abs(5*c['ink_height']-3*cap),c['option']['dpi'],c['option']['pixels']))
    else:
        chosen=min(candidates,key=lambda c:(c['ink_height'],c['option']['pixels'],c['option']['dpi']))
    ink=chosen['ink_height']
    native_width=max(max(x for x,y in chosen['face'][c]['points'])-min(x for x,y in chosen['face'][c]['points'])+1 for c in CODES)
    same_3x5=ink==original['height'] and native_width<=original['advance']
    use_original=not same_3x5 and (ink>cap or (ink==cap and 1<=cap-original['height']<=2))
    if use_original:
        glyphs={}
        for digit,columns in enumerate(original['columns']):
            im=Image.new('1',(original['advance'],height))
            for x,column in enumerate(columns):
                for y in range(original['height']):
                    if column>>y&1:im.putpixel((x,top+y),1)
            glyphs[48+digit]=im
        return glyphs,dict(kind='3x5',ink_height=5,top=top,body_cap_height=cap,
                          reason='Native digits exceed capitals' if ink>cap else '3x5 is 1–2px smaller than capitals')
    glyphs={}
    for code in CODES:
        width,points,_=recipe.horizontal(chosen['face'][code],None,False)
        im=Image.new('1',(width,height))
        for x,y in points:
            yy=y-chosen['source_top']+top
            assert 0<=x<width and 0<=yy<height,(family,body_pixels,code,x,yy)
            im.putpixel((x,yy),1)
        glyphs[code]=im
    option=chosen['option']
    return glyphs,dict(kind='native',ink_height=ink,top=top,body_cap_height=cap,
                      pixels=option['pixels'],dpi=option['dpi'],source=recipe.source_name(option['paths'][0]))
