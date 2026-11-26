#!/usr/bin/env python3
"""Select and export native bitmap strikes under the four-slot clipping policy.

CP1252 selects the strike. Neo-only glyphs are added when available and fitting.
No rescaling, accent rearrangement, slant reduction or hand-drawn repairs.
"""
import argparse
import gzip
from functools import lru_cache
import json
from pathlib import Path
import re
import struct
import sys

from PIL import Image, PcfFontFile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'fonts'))
sys.path.insert(0, str(ROOT/'os3k'))
from charsets import load, glyph_name

STYLES = ['Regular','Bold','Italic','BoldItalic']
FAMILIES = {'Serif':('tim',['R','B','I','BI']), 'Sans':('helv',['R','B','O','BO']),
            'Book':('ncen',['R','B','I','BI']), 'Mono':('cour',['R','B','O','BO'])}
SIZES = {3:'Large',4:'Medium',5:'Small',6:'Tiny'}
PITCH = {3:21,4:16,5:13,6:11,9:7,10:6}
CP = list(range(32,127))+[c for c in range(128,256) if c not in (129,141,143,144,157)]


from fontgen import UnicodePCF


@lru_cache(maxsize=None)
def read_source(path, codes):
    UnicodePCF.codes = codes
    with gzip.open(path,'rb') as stream:font=UnicodePCF(stream)
    if font.info.get(b'CHARSET_REGISTRY')!=b'ISO10646':raise ValueError(path)
    out = {}
    for code,glyph in zip(codes,font.glyph):
        if glyph is None:continue
        advance,(left,top,right,bottom),rect,bitmap = glyph
        ink = bitmap.crop(rect)
        points = {(left+x,top+y) for y in range(ink.height) for x in range(ink.width) if ink.getpixel((x,y))}
        out[code] = dict(advance=advance[0],points=points)
    return out


def keyboard_priority():
    path=ROOT.parent/'Ghidra/Alphasmart Neo/SmartApplets/os3kneorom.os3kos'
    data=path.read_bytes();outputs=set();bindings={}
    names={int(v,16):k for k,v in re.findall(r'(KEY_\w+)\s*=\s*(0x[0-9A-Fa-f]+)',(ROOT/'os3k/os3k_keyboard.h').read_text())}
    for key in range(80):
        at=struct.unpack_from('>I',data,0x44b526-0x410000+4*key)[0]-0x410000
        if not 0<=at<len(data) or not data[at]:continue
        pairs=[('plain',data[at]),('shift',data[at+1])];offset=2
        while data[at+offset]:
            mask,value=data[at+offset:at+offset+2];pairs.append((f'modifier {mask:02X}',value));offset+=2
        for modifier,value in pairs:
            if value not in (0,9,13):
                outputs.add(value);bindings.setdefault(value,[]).append(names.get(key,hex(key))+' '+modifier)
    # Each accent descriptor: key, modifier, spacing byte, count, then key/lower/upper triples.
    for index in range(5):
        at=struct.unpack_from('>I',data,0x44b66a-0x410000+4*index)[0]-0x410000
        for n in range(data[at+3]):
            for value in data[at+5+3*n:at+7+3*n]:outputs.add(value)
    return outputs, {f'{c:02X}':v for c,v in bindings.items() if c<32 or c in (127,129,141,143,144,157)}


@lru_cache(maxsize=None)
def strike_options(family):
    stem,styles=FAMILIES[family];results=[]
    for dpi in (75,100):
        for path in sorted((Path('/usr/share/fonts/X11')/f'{dpi}dpi').glob(stem+'R[0-9][0-9].pcf.gz')):
            points=int(re.search(r'R(\d+)',path.name)[1]);UnicodePCF.codes=[]
            with gzip.open(path,'rb')as stream:font=UnicodePCF(stream)
            if font.info.get(b'CHARSET_REGISTRY')!=b'ISO10646':continue
            results.append(dict(points=points,dpi=dpi,pixels=int(font.info[b'PIXEL_SIZE']),
                paths=[path.with_name(f'{stem}{style}{points:02}.pcf.gz')for style in styles]))
    return results


def normalized(glyph, mono_width=None, italic=False):
    points=glyph['points']
    if mono_width is not None:
        if not italic:
            shift=max(0,-min((x for x,y in points),default=0))
            points={(x+shift,y)for x,y in points}
        return mono_width,points
    left=min((x for x,y in points),default=0);shift=max(0,-left)
    points={(x+shift,y)for x,y in points}
    width=max(glyph['advance']+shift,max((x+1 for x,y in points),default=1),1)
    return width,points


def choose(family,lines,mapping,priority,fixed_path=None):
    pitch=PITCH[lines];limit=min(pitch,65-(lines-1)*pitch)
    codes=tuple(sorted(set(mapping.values())-{None}));cp_codes={mapping[c]for c in CP}
    if fixed_path:
        UnicodePCF.codes=[]
        with gzip.open(fixed_path,'rb')as stream:f=UnicodePCF(stream)
        options=[dict(points=int(f.info[b'POINT_SIZE'])//10,dpi=int(f.info[b'RESOLUTION_Y']),pixels=int(f.info[b'PIXEL_SIZE']),paths=[fixed_path])]
    else:options=strike_options(family)
    accepted=[]
    closest=[]
    for option in options:
        faces=[read_source(p,codes)for p in option['paths']]
        if any(not cp_codes<=face.keys()for face in faces):continue
        mono_width=faces[0][ord('A')]['advance']+1 if family=='Mono' else None
        metrics=[]
        for style,face in enumerate(faces):
            for slot in CP:
                width,points=normalized(face[mapping[slot]],mono_width,family=='Mono'and style in (2,3))
                if not points:continue
                xs,ys=zip(*points)
                metrics.append((style,slot,min(ys),max(ys)+1,min(xs),max(xs)+1,width))
        for baseline in range(pitch+1):
            top=-baseline;bottom=top+limit;clipped=set();bad=False
            for style,slot,y0,y1,x0,x1,width in metrics:
                vertical=[max(0,top-y0),max(0,y1-bottom)]
                horizontal=[max(0,-x0),max(0,x1-width)]
                ordinary=vertical+(horizontal if not(family=='Mono'and style in (2,3))else[0,0])
                excess=[v for v in ordinary if v]
                if len(excess)>1 or any(v>1 for v in excess):bad=True;break
                if excess:clipped.add(slot)
            if bad:continue
            if len(clipped)>4:
                closest.append(dict(pixels=option['pixels'],dpi=option['dpi'],points=option['points'],baseline=baseline,
                    slots=[f'{c:02X}'for c in sorted(clipped)],keyboard_slots=[f'{c:02X}'for c in sorted(clipped&priority)]))
                continue
            lost=0
            for style,slot,*_ in metrics:
                width,points=normalized(faces[style][mapping[slot]],mono_width,family=='Mono'and style in (2,3))
                lost+=sum(not(0<=x<width and top<=y<bottom)for x,y in points)
            cap=faces[0][ord('A')]['points'];cap_height=max(y for x,y in cap)-min(y for x,y in cap)+1
            # Prefer avoiding keyboard clipping, then fewer exceptions/pixels at a given native size.
            rank=(-len(clipped&priority),option['pixels'],-len(clipped),-lost,cap_height,option['dpi'],-baseline)
            accepted.append((rank,option,faces,mono_width,baseline,limit,clipped))
    if not accepted:
        best=min(closest,key=lambda c:(len(c['slots']),len(c['keyboard_slots']),c['pixels'])) if closest else None
        return None,dict(family=family,lines=lines,pitch=pitch,ink_rows=limit,available=False,closest=best)
    _,option,faces,mono_width,baseline,limit,allowed=max(accepted,key=lambda item:item[0])
    result=[];changes=[];missing=[]
    for style,face in enumerate(faces):
        cells={}
        for slot,code in mapping.items():
            if code is None or code not in face:
                missing.append(dict(style=STYLES[style],slot=f'{slot:02X}',reason='not in native source'));continue
            width,points=normalized(face[code],mono_width,family=='Mono'and style in (2,3))
            vertical_out={(x,y)for x,y in points if not -baseline<=y<-baseline+limit}
            horizontal_out={(x,y)for x,y in points if not 0<=x<width}
            if slot not in CP and (vertical_out or(horizontal_out and not(family=='Mono'and style in (2,3)))):
                missing.append(dict(style=STYLES[style],slot=f'{slot:02X}',reason='Neo-only glyph exceeds cell'));continue
            removed=vertical_out|horizontal_out
            if removed:changes.append(dict(style=STYLES[style],slot=f'{slot:02X}',character=chr(code),
                keyboard=slot in priority,vertical=sorted(vertical_out),horizontal=sorted(horizontal_out)))
            image=Image.new('1',(width,pitch))
            for x,y in points-removed:image.putpixel((x,y+baseline),1)
            assert sum(bool(p)for p in image.getdata())==len(points-removed)
            cells[slot]=image
        result.append(cells)
    meta=dict(available=True,family=family,lines=lines,pitch=pitch,ink_rows=limit,baseline=baseline,
        points=option['points'],dpi=option['dpi'],pixels=option['pixels'],sources=[str(p)for p in option['paths']],
        mono_width=mono_width,allowed_cp1252_slots=[f'{c:02X}'for c in sorted(allowed)],clipping=changes,missing=missing,
        missing_keyboard_slots=sorted({m['slot']for m in missing if int(m['slot'],16)in priority}))
    return result,meta


def bdf(path,source,cells,baseline,mapping,meta,style):
    old=source.read_text();header=old[:old.index('CHARS ')]
    width=max(im.width for im in cells.values());height=meta['pitch'];descent=height-baseline
    header=re.sub(r'^FONTBOUNDINGBOX .*$',f'FONTBOUNDINGBOX {width} {height} 0 {-descent}',header,flags=re.M)
    for key,value in [('FONT_ASCENT',baseline),('FONT_DESCENT',descent),('PIXEL_SIZE',meta['pixels']),('POINT_SIZE',meta['points']*10),('RESOLUTION_X',meta['dpi']),('RESOLUTION_Y',meta['dpi'])]:
        header=re.sub(r'^'+key+r' \d+$',f'{key} {value}',header,flags=re.M)
    header=re.sub(r'^SIZE .*$',f'SIZE {meta["points"]} {meta["dpi"]} {meta["dpi"]}',header,flags=re.M)
    # Keep the public BetaWise family/style identity; update only the source-size XLFD fields.
    parts=next(line for line in header.splitlines()if line.startswith('FONT ')).split('-')
    if len(parts)>=15:
        parts[7:11]=list(map(str,[meta['pixels'],meta['points']*10,meta['dpi'],meta['dpi']]))
        header=re.sub(r'^FONT .*$', '-'.join(parts),header,flags=re.M)
    blocks=[]
    for slot,image in sorted(cells.items()):
        rows=[]
        for y in range(height):
            value=0
            for x in range(image.width):value=(value<<1)|bool(image.getpixel((x,y)))
            rows.append(f'{value<<((-image.width)%8):0{2*((image.width+7)//8)}X}')
        blocks.append(f'STARTCHAR {glyph_name(slot,mapping)}\nENCODING {slot}\nSWIDTH 500 0\nDWIDTH {image.width} 0\nBBX {image.width} {height} 0 {-descent}\nBITMAP\n'+ '\n'.join(rows)+'\nENDCHAR\n')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(header+f'CHARS {len(cells)}\n'+''.join(blocks)+'ENDFONT\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    args=parser.parse_args();mapping=load(ROOT/'os3k/charsets/neo-us.txt')
    priority,bindings=keyboard_priority();out=HERE/'build/native-preview';records=[]
    for family in FAMILIES:
        for lines,size in SIZES.items():
            cells,meta=choose(family,lines,mapping,priority)
            if cells is None:
                records.append(meta);print(f'{family} {lines}: UNAVAILABLE; closest {meta["closest"]}',flush=True);continue
            for index,style in enumerate(STYLES):
                rel=Path('BetaWise'+family)/f'BetaWise{family}-{size}-{style}.bdf'
                bdf(out/rel,ROOT/'fonts/build/bdf'/rel,cells[index],meta['baseline'],mapping,meta,style)
            records.append(meta)
            print(f'{family} {lines}: {meta["pixels"]}px / {meta["dpi"]}dpi; budget slots {meta["allowed_cp1252_slots"]}; clipped cells {len(meta["clipping"])}',flush=True)
    for lines,stem in [(9,'5x7'),(10,'4x6')]:
        # Preserve terminal column capacity: these are the native Fixed strikes
        # between the AS3000 6x8 and the dense 4x6 variant.
        cells,meta=choose('Terminal',lines,mapping,priority,Path('/usr/share/fonts/X11/misc')/(stem+'.pcf.gz'))
        rel=Path('BetaWiseTerminal')/f'glyphs-{stem}.bdf'
        bdf(out/rel,ROOT/'fonts/build/bdf'/rel,cells[0],meta['baseline'],mapping,meta,'Regular');records.append(meta)
        print(f'Terminal {stem}: {len(meta["clipping"])} clipped cells; {len(meta["missing"])} unavailable Neo slots',flush=True)
    report=dict(policy='Largest native XLFD pixel size; at most four distinct CP1252 slots may exceed one edge by one pixel across four styles. Mono italic horizontal overhang is clipped separately. Keyboard outputs are prioritized before native pixel size; at a given size they also break placement ties. Negative left bearings are normalized for upright Mono; italic horizontal clipping uses native placement. Neo-only glyphs must fit vertically.',
        keyboard_extra_bindings=bindings,fonts=records)
    (out/'native-selection.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(out/'native-selection.json')


if __name__=='__main__':main()
