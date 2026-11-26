#!/usr/bin/env python3
"""Research-only pixel edits and lossless X11 strike inventory."""
import json
import unicodedata
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import compare as c

OUT = c.HERE / 'build' / 'tuned'
OUT.mkdir(parents=True, exist_ok=True)
LABEL = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)
ROWS = dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ', [1,4,3,2,3,4,2,4,3,2,3,2,4,3,3,2,2,2,3,3,3,5,5,3,4,4]))
EXTENDED = {'Æ':1, 'Ð':3, 'Ø':4, 'Þ':3}
ACCENTS = {
    '\u0300':['#.','.#'], '\u0301':['.#','#.'],
    '\u0302':['.#.','#.#'], '\u0303':['.##','##.'],
    '\u0308':['#.#'], '\u030a':['.#.','#.#','.#.'],
    '\u0327':['.#','#.'],
}


def moved(glyph, offset, height=11):
    result = Image.new('1', (glyph.width, height))
    result.paste(glyph, (0, offset))
    assert sum(result.getdata()) == sum(glyph.getdata()), 'Clipped source glyph'
    return result


def tuned_cap(smaller, char, style):
    glyph = smaller[ord(char)]
    top, bottom = c.bounds(smaller[ord('H')])
    row = ROWS.get(char, EXTENDED.get(char))
    if style == 'B':
        row = {'M':3, 'W':3, 'Þ':2}.get(char, row)
    if style == 'I':
        row = {'I':2, 'R':3, 'Q':3, 'Ø':3}.get(char, row)
    assert row is not None and bottom - top + 1 == 6
    result = Image.new('1', (glyph.width, 11))
    source_rows = [y for y in range(top, glyph.height) if y != top + row]
    for dest, source in enumerate(source_rows, 3):
        if dest < 11:
            result.paste(glyph.crop((0, source, glyph.width, source+1)), (0, dest))
        else:
            assert not glyph.crop((0, source, glyph.width, source+1)).getbbox()
    patterns = {
        ('R','S'):['.###.','#....','.##..','...#.','###..'],
        ('B','S'):['.####.','##....','.####.','....##','#####.'],
    }
    if (style,char) in patterns:
        result = Image.new('1', (glyph.width,11))
        for y, line in enumerate(patterns[style,char],3):
            for x, pixel in enumerate(line):
                assert x < glyph.width
                if pixel == '#': result.putpixel((x,y),1)
    assert result.getbbox()
    return result


def small_cap(smaller, char, style):
    if char == 'ß':
        s = tuned_cap(smaller,'S',style)
        result = Image.new('1',(s.width*2,11))
        result.paste(s,(0,0)); result.paste(s,(s.width,0))
        return result
    capital = char.upper()
    parts = unicodedata.normalize('NFD', capital)
    base = tuned_cap(smaller, parts[0], style)
    if len(parts) == 1: return base
    assert len(parts) == 2 and parts[1] in ACCENTS
    pattern = ACCENTS[parts[1]]
    mark_width = len(pattern[0])
    box = base.getbbox()
    left = max(0, (box[0]+box[2]-mark_width)//2)
    result = Image.new('1',(max(base.width,left+mark_width),11))
    result.paste(base,(0,0))
    y0 = 8 if parts[1] == '\u0327' else 3-len(pattern)
    for dy,line in enumerate(pattern):
        for dx,pixel in enumerate(line):
            if pixel == '#': result.putpixel((left+dx,y0+dy),1)
    return result


def render_sample(face, text):
    result = Image.new('1',(sum(face[ord(ch)].width for ch in text),11))
    x = 0
    for char in text:
        glyph = face[ord(char)]
        result.paste(glyph,(x,0)); x += glyph.width
    return result


def main():
    protected = [c.BETAWISE/'applets/BibleWise/BibleWise.c', c.BETAWISE/'fonts/fontgen.py', c.HERE.parent/'reader-fonts/build.py']
    before = {str(p):c.sha(p) for p in protected}
    report = {'styles':[], 'inventory':[]}
    figure = Image.new('RGB',(1260,660),'white')
    draw = ImageDraw.Draw(figure)
    for column,title in enumerate(['Current resize (5px)','Hinted source (6px)','Hand tuned (5px)']):
        draw.text((column*420+10,8),title,font=LABEL,fill='black')
    for index,style in enumerate(['R','B','I']):
        _,original = c.source_font('ncen',style,10)
        _,smaller = c.source_font('ncen',style,8)
        body = c.reader_font(original,3)
        tuned = c.blank_slots(11)
        hinted = c.blank_slots(11)
        fallbacks = []
        for code in c.PRINTABLE:
            if c.is_latin_lower(code):
                tuned[code] = small_cap(smaller,chr(code),style)
                hinted[code] = moved(c.uppercase(smaller,code),7-c.bounds(smaller[ord('H')])[1])
            else:
                candidate = body[code]
                if sum(candidate.getdata()) != sum(original[code].getdata()):
                    candidate = moved(smaller[code],7-c.bounds(smaller[ord('H')])[1])
                    fallbacks.append(code)
                tuned[code] = candidate
                hinted[code] = candidate.copy()
        assert all(tuned[n].tobytes()==body[n].tobytes() for n in range(48,58))
        export = c.export_bdf(OUT/f'Century-{style}-tuned5-latin1.bdf',tuned,8,'CenturySchoolbook',style)
        report['styles'].append(dict(style=style, smaller_hint_fallback_codes=fallbacks, export=export,
            coverage=191, clipped_source_glyphs=0, accent_patterns=ACCENTS,
            alphabet_advance=sum(tuned[n].width for n in range(97,123))))
        current = c.make_face(body,smaller,'current',range(32,127))
        # Extended current is deliberately cropped diagnostic, not a deliverable face.
        for code in range(160,256):
            current[code] = c.resize_current(body,c.uppercase(original,code)) if c.is_latin_lower(code) else body[code]
        for column,face in enumerate([current,hinted,tuned]):
            y = 45+index*200
            draw.text((column*420+10,y),{'R':'Regular','B':'Bold','I':'Italic'}[style],font=LABEL,fill='black')
            for row,text in enumerate(['Lord God Jesus','abcdefghijklmnopqrstuvwxyz','é à ä ñ ç ø æ ß ÿ','É À Ä Ñ Ç Ø Æ Å']):
                bitmap = render_sample(face,text).convert('RGB').point(lambda x:255-x)
                bitmap = bitmap.resize((bitmap.width*3,33),Image.Resampling.NEAREST)
                figure.paste(bitmap,(column*420+10,y+25+row*39))
    figure.save(OUT/'century-comparison.png')
    # Common baseline envelope includes every face, not just regular H/x.
    size_figure = Image.new('RGB',(1120,1800),'white')
    sd = ImageDraw.Draw(size_figure)
    pitches = {2:32,3:21,4:16,5:13,6:11,7:9,8:8,9:7,10:6,11:5}
    for family_index,(name,family,styles,trim) in enumerate(c.FAMILIES):
        inventory = []
        for points in [8,10,12,14,18,24]:
            faces = [c.source_font(family,s,points)[1] for s in (*styles, 'BO' if family=='helv' else 'BI')]
            item = dict(family=name,points=points)
            for label,codes in [('ascii',range(32,127)),('latin1',c.PRINTABLE)]:
                spans = [(g.getbbox()[1]-c.bounds(face[72])[1],g.getbbox()[3]-1-c.bounds(face[72])[1])
                         for face in faces for code in codes if (g:=face[code]).getbbox()]
                top,bottom = min(x[0] for x in spans),max(x[1] for x in spans)
                item[label] = dict(height=bottom-top+1,top=top,bottom=bottom)
            inventory.append((item,faces[0]))
            report['inventory'].append(item)
        for row,(lines,pitch) in enumerate(pitches.items()):
            x,y=family_index*370,row*178
            fits = [(item,face) for item,face in inventory if item['ascii']['height']<=pitch]
            sd.text((x+5,y+5),f'{name}: {lines} lines / {pitch}px',font=LABEL,fill='black')
            if not fits:
                sd.text((x+5,y+32),'No lossless native X11 strike',font=LABEL,fill='black')
                continue
            item,face = fits[-1]
            sd.text((x+5,y+29),f"{item['points']}pt; Latin-1 needs {item['latin1']['height']}px",font=LABEL,fill='black')
            page=Image.new('1',(264,65))
            text='The quick brown fox jumps over the lazy dog. Reading the book, 123.'
            baseline=-item['ascii']['top']
            px=0; py=0
            for char in text*10:
                glyph=face[ord(char)]
                if px+glyph.width>264: px=0; py+=pitch
                if py+pitch>65: break
                page.paste(glyph,(px,py+baseline-c.bounds(face[72])[1])); px+=glyph.width
            # Page bounds are strict: no 66th-row assumptions.
            page.convert('RGB').point(lambda z:255-z).save(OUT/f'{name}-{lines}-lines-native.png')
            size_figure.paste(page.convert('RGB').point(lambda z:255-z),(x+5,y+55))
    size_figure.save(OUT/'size-inventory.png')
    caps_figure = Image.new('RGB',(1200,1080),'white')
    cd = ImageDraw.Draw(caps_figure)
    for column,(name,family,styles,trim) in enumerate(c.FAMILIES):
        strikes = [8,10,12,14,18,24]
        for row,points in enumerate(strikes):
            _,body = c.source_font(family,styles[0],points)
            _,smaller = c.source_font(family,styles[0],strikes[max(0,row-1)])
            x,y=column*400+8,row*180+8
            cd.text((x,y),f'{name} {points}pt',font=LABEL,fill='black')
            cd.text((x,y+22),'All caps fallback' if row==0 else 'Next smaller hinted capitals',font=LABEL,fill='black')
            for line,small in enumerate([False,True]):
                glyphs=[]
                for char in 'Lord God, Reading':
                    g=body[ord(char)]
                    if small and char.islower():
                        src=(body if row==0 else smaller)
                        g=src[ord(char.upper())]
                        g=moved(g, c.bounds(body[72])[1]-c.bounds(src[72])[1],body[0].height)
                    glyphs.append(g)
                sample=Image.new('1',(sum(g.width for g in glyphs),body[0].height))
                pos=0
                for g in glyphs: sample.paste(g,(pos,0)); pos+=g.width
                sample=sample.convert('RGB').point(lambda z:255-z)
                caps_figure.paste(sample.resize((sample.width*2,sample.height*2),Image.Resampling.NEAREST),(x,y+48+line*62))
    caps_figure.save(OUT/'smallcaps-size-comparison.png')
    assert before=={str(p):c.sha(p) for p in protected}
    report['unchanged_production_sha256']=before
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'output':str(OUT),'faces':3,'coverage_each':191,'production_unchanged':True}))

if __name__=='__main__': main()
