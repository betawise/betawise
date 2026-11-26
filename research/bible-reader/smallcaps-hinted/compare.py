#!/usr/bin/env python3
"""Offline hinted-small-cap study. Does not build/install/modify any applet."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

from PIL import Image, ImageDraw, ImageFont, PcfFontFile


HERE = Path(__file__).resolve().parent
BETAWISE = HERE.parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(BETAWISE / 'fonts'))
from fontgen import generate, load

PRINTABLE = list(range(32, 127)) + list(range(160, 256))
FAMILIES = [
    ('Times', 'tim', ('R', 'B', 'I'), 2),
    ('CenturySchoolbook', 'ncen', ('R', 'B', 'I'), 3),
    ('Helvetica', 'helv', ('R', 'B', 'O'), 3),
]
STYLE_NAMES = ('Regular', 'Bold', 'Italic')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_font(family, style, points):
    path = Path('/usr/share/fonts/X11/75dpi') / f'{family}{style}{points:02}.pcf.gz'
    with gzip.open(path, 'rb') as stream:
        source = PcfFontFile.PcfFontFile(stream, charset_encoding='iso8859-1').glyph
    assert all(source[c] is not None for c in PRINTABLE), f'Incomplete Latin-1: {path}'
    return path, load(path, 'iso8859-1', 63)


def bounds(glyph):
    box = glyph.getbbox()
    assert box is not None, 'Expected nonempty metric glyph'
    return box[1], box[3] - 1


def metric(glyph):
    top, bottom = bounds(glyph)
    return bottom - top + 1


def reader_font(original, trim):
    result = []
    for glyph in original:
        canvas = Image.new('1', (glyph.width, 11))
        canvas.paste(glyph, (0, -trim))
        result.append(canvas)
    return result


def blank_slots(height):
    return [Image.new('1', (1, height)) for _ in range(256)]


def uppercase(glyphs, code):
    """Latin-1 uppercase, with explicit SS and Y-diaeresis compositions."""
    if code == 0xdf:  # Latin-1 has no uppercase sharp S: traditional small-cap SS.
        source = glyphs[ord('S')]
        result = Image.new('1', (source.width * 2, source.height))
        result.paste(source, (0, 0))
        result.paste(source, (source.width, 0))
        return result
    if code == 0xff:  # Uppercase Y-diaeresis is outside Latin-1.
        base = glyphs[ord('Y')]
        cap_top, _ = bounds(glyphs[ord('H')])
        assert bounds(glyphs[ord('A')])[0] >= cap_top
        accent = glyphs[0xc4].crop((0, 0, glyphs[0xc4].width, cap_top))
        box = accent.getbbox()
        assert box is not None
        accent = accent.crop(box)
        width = max(base.width, accent.width)
        result = Image.new('1', (width, base.height))
        result.paste(base, ((width - base.width) // 2, 0))
        result.paste(accent, ((width - accent.width) // 2, box[1]))
        return result
    capital = chr(code).upper()
    assert len(capital) == 1 and ord(capital) <= 255
    return glyphs[ord(capital)]


def is_latin_lower(code):
    return 97 <= code <= 122 or code == 0xdf or 0xe0 <= code <= 0xf6 or 0xf8 <= code <= 0xff


def resize_current(body, capital):
    """Exactly the current C nearest-sample rule, including Q/J ink bounds."""
    cap_top, cap_bottom = bounds(body[ord('H')])
    target_top, target_bottom = bounds(body[ord('x')])
    source_height = cap_bottom - cap_top + 1
    height = target_bottom - target_top + 1
    width = (capital.width * height + source_height - 1) // source_height
    glyph_top, glyph_bottom = bounds(capital)
    glyph_top = min(glyph_top, cap_top)
    glyph_bottom = max(glyph_bottom, cap_bottom)
    result = Image.new('1', (width, body[0].height))
    for y in range(height):
        sy = glyph_top + y * (glyph_bottom - glyph_top) // (height - 1) if height > 1 else glyph_top
        for x in range(width):
            result.putpixel((x, target_top + y), capital.getpixel((x * capital.width // width, sy)))
    return result


def align_hinted(body, smaller, capital):
    result = Image.new('1', (capital.width, body[0].height))
    offset = bounds(body[ord('x')])[1] - bounds(smaller[ord('H')])[1]
    result.paste(capital, (0, offset))
    assert sum(result.getdata()) == sum(capital.getdata()), 'Hinted glyph ink would be clipped'
    return result


def make_face(body, smaller, method, codes):
    result = blank_slots(body[0].height)
    for code in codes:
        if is_latin_lower(code):
            capital = uppercase(body if method == 'current' else smaller, code)
            result[code] = resize_current(body, capital) if method == 'current' else align_hinted(body, smaller, capital)
        else:
            result[code] = body[code].copy()
    # Verse-number overlays are deliberately absent from these resources.
    assert all(result[c].tobytes() == body[c].tobytes() and result[c].size == body[c].size
               for c in range(ord('0'), ord('9') + 1))
    return result


def packed(glyph):
    return bytes(sum(1 << (y % 8) for y in range(band, min(band + 8, glyph.height))
                     if glyph.getpixel((x, y)))
                 for band in range(0, glyph.height, 8) for x in range(glyph.width))


def check_existing_reader(stem, face, glyphs):
    """Pin the comparison's body glyphs to the already-built reader font source."""
    path = HERE.parent / 'reader-fonts/build' / (stem + '.c')
    if not path.exists():
        return None
    source = path.read_text()
    def table(name):
        match = re.search(r'\b' + name + r'\[\]\s*=\s*\{([^}]+)\}', source)
        assert match is not None
        return list(map(int, match.group(1).split(',')))
    widths, offsets, pixels = (table(f'{name}_{face}') for name in ('widths', 'offsets', 'pixels'))
    for code in range(32, 127):
        bitmap = packed(glyphs[code])
        assert widths[code] == glyphs[code].width
        assert bytes(pixels[offsets[code]:offsets[code] + len(bitmap)]) == bitmap
    return dict(path=str(path), sha256=sha(path), matched_ascii_glyphs=95)


def check_capture(path, style, face):
    widths = (path / 'privatefont-widths-01.bin').read_bytes()
    offsets = (path / 'privatefont-offsets-01.bin').read_bytes()
    data = (path / 'privatefont-pixels-01.bin').read_bytes()
    for code in range(97, 123):
        slot = code + (0 if style == 0 else 0x80 if style == 1 else 0x60)
        offset = int.from_bytes(offsets[2 * slot:2 * slot + 2], 'big')
        bitmap = packed(face[code])
        assert widths[slot] == face[code].width and data[offset:offset + len(bitmap)] == bitmap


def export_bdf(path, glyphs, ascent, family, style):
    height = glyphs[0].height
    weight = 'bold' if 'B' in style else 'medium'
    slant = 'i' if 'I' in style else 'o' if 'O' in style else 'r'
    rows = ['STARTFONT 2.1', f'FONT -betawise-{family}smallcapsresearch-{weight}-{slant}-normal--{height}-100-75-75-p-0-iso8859-1',
            'SIZE 10 75 75', f'FONTBOUNDINGBOX {max(g.width for g in glyphs)} {height} 0 {ascent-height}',
            'STARTPROPERTIES 3', f'FONT_ASCENT {ascent}', f'FONT_DESCENT {height-ascent}',
            'COPYRIGHT "Adobe/DEC source fonts; see FONT-LICENSE.txt"', 'ENDPROPERTIES', 'CHARS 256']
    for code, glyph in enumerate(glyphs):
        rows += [f'STARTCHAR U{code:04X}', f'ENCODING {code}', f'SWIDTH {glyph.width*96} 0',
                 f'DWIDTH {glyph.width} 0', f'BBX {glyph.width} {height} 0 {ascent-height}', 'BITMAP']
        for y in range(height):
            value = sum(1 << (((glyph.width+7)//8)*8-1-x) for x in range(glyph.width) if glyph.getpixel((x,y)))
            rows.append(f'{value:0{2*((glyph.width+7)//8)}X}')
        rows.append('ENDCHAR')
    rows.append('ENDFONT')
    path.write_text('\n'.join(rows) + '\n')
    restored = load(path, 'iso8859-1')
    assert all(a.size == b.size and a.tobytes() == b.tobytes() for a,b in zip(glyphs,restored)), 'BDF round trip'
    generate(path, path.with_suffix('.h'))
    return dict(bdf=str(path), sha256=sha(path), bitmap_bytes=sum(len(packed(g)) for g in glyphs),
                neo_width_offset_bytes=768, descriptor_bytes=16, bible_superscripts_included=False)


def text_bitmap(text, body, face, small=True):
    images = [face[ord(c)] if small and is_latin_lower(ord(c)) else body[ord(c)] for c in text]
    result = Image.new('1', (sum(g.width for g in images), body[0].height))
    x = 0
    for glyph in images:
        result.paste(glyph, (x,0)); x += glyph.width
    return result


def specimen(path, entries, latin=False):
    """Fixed integer magnification; no antialiasing or screen/model inference."""
    scale = 4
    samples = ['é à ä ñ ç ø æ ß ÿ', 'École déjà Æsir'] if latin else ['Lord God Jesus Yah', 'abcdefghijklm', 'nopqrstuvwxyz']
    ui = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 17)
    title = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 23)
    label_width, column = 190, 480
    row_height = (13 if latin else 11) * scale + 12
    block = 42 + row_height * len(samples)
    image = Image.new('RGB',(label_width + 2*column + 20, 90 + block*len(entries)+48),'white')
    draw = ImageDraw.Draw(image)
    heading = 'Latin-1 extension — 13px cells, hinted accents preserved' if latin else 'Current 11px reader — exact 4× pixel magnification'
    draw.text((18,10),heading,font=title,fill='black')
    draw.text((label_width,49),'Current rule, extended to accents' if latin else 'Current nearest-sample resizing',font=ui,fill='black')
    draw.text((label_width+column,49),'Smaller hinted capitals — no resizing',font=ui,fill='black')
    for index, entry in enumerate(entries):
        y = 84 + index*block
        draw.line((16,y-4,image.width-16,y-4),fill='#c0c0c0')
        draw.text((18,y),entry['label'],font=ui,fill='black')
        draw.text((18,y+23),f"x={entry['target']} / caps={entry['hint_height']}",font=ui,fill='#555555')
        for method, x in [('current',label_width),('hinted',label_width+column)]:
            body, face = entry['body'], entry[method]
            top, bottom = bounds(body[ord('x')])
            for line, sample in enumerate(samples):
                py = y+38+line*row_height
                tile = text_bitmap(sample,body,face)
                assert tile.width*scale < column-12
                draw.line((x,py+top*scale,x+column-16,py+top*scale),fill='#e0bd7e')
                draw.line((x,py+(bottom+1)*scale,x+column-16,py+(bottom+1)*scale),fill='#91c8e5')
                ink = tile.resize((tile.width*scale,tile.height*scale),Image.Resampling.NEAREST)
                image.paste('black',(x,py),ink)
    draw.text((18,image.height-32),'Gold: target x-height top. Blue: baseline. Digits remain normal; BibleWise overlay is separate.',font=ui,fill='#444444')
    image.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=HERE/'build')
    parser.add_argument('--accepted-captures',type=Path,help='Optional family→accepted MAME capture directory JSON')
    args = parser.parse_args()
    output = args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    captures = json.loads(args.accepted_captures.read_text()) if args.accepted_captures else {}
    protected = [BETAWISE/'applets/BibleWise/BibleWise.c', BETAWISE/'fonts/fontgen.py', HERE.parent/'reader-fonts/build.py']
    before = {str(p):sha(p) for p in protected}
    report = dict(scope='Research only; no production build or install', faces=[], inventory=[], current_resize_capture_checks=0)
    overview, accents = [], []
    for stem, family, styles, trim in FAMILIES:
        entries, accent_entries = [], []
        for style_index, style in enumerate(styles):
            large_path, original = source_font(family,style,10)
            small_path, smaller = source_font(family,style,8)
            body = reader_font(original,trim)
            matched = check_existing_reader(stem,style_index,body)
            current = make_face(body,smaller,'current',range(32,127))
            hinted = make_face(body,smaller,'hinted',range(32,127))
            if stem in captures:
                check_capture(Path(captures[stem]),style_index,current)
                report['current_resize_capture_checks'] += 26
            entry = dict(label=stem+' '+STYLE_NAMES[style_index],body=body,current=current,hinted=hinted,
                         target=metric(body[ord('x')]),hint_height=metric(smaller[ord('H')]))
            entries.append(entry)
            full_current = make_face(original,smaller,'current',PRINTABLE)
            full_hinted = make_face(original,smaller,'hinted',PRINTABLE)
            accent_entry = dict(entry,body=original,current=full_current,hinted=full_hinted)
            accent_entries.append(accent_entry)
            exports = []
            for method, glyphs in [('current',current),('hinted',hinted),('current-latin1',full_current),('hinted-latin1',full_hinted)]:
                exported = export_bdf(output/f'{stem}-{style}-{method}.bdf',glyphs,bounds((original if 'latin1' in method else body)[ord('H')])[1]+1,stem.lower(),style)
                exported['coverage'] = 'ASCII + printable Latin-1' if 'latin1' in method else 'ASCII only; remaining slots blank'
                exports.append(exported)
            report['faces'].append(dict(family=stem,style=STYLE_NAMES[style_index],body_source=str(large_path),
                body_source_sha256=sha(large_path),hinted_source=str(small_path),hinted_source_sha256=sha(small_path),
                target_x_height=entry['target'],hinted_cap_height=entry['hint_height'],
                exact_height=entry['target']==entry['hint_height'],baseline_ink_bottom=bounds(body[ord('x')])[1],
                hinted_ink_extents={chr(c):list(bounds(hinted[c])) for c in range(97,123)},
                current_ink_extents={chr(c):list(bounds(current[c])) for c in range(97,123)},
                alphabet_advance={'current':sum(current[c].width for c in range(97,123)),'hinted':sum(hinted[c].width for c in range(97,123))},
                reconstructed_reader=matched,exports=exports))
            for points in (8,10,12,14,18,24):
                path,glyphs=source_font(family,style,points)
                report['inventory'].append(dict(family=stem,style=STYLE_NAMES[style_index],points=points,
                    cell_height=glyphs[0].height,cap_height=metric(glyphs[ord('H')]),x_height=metric(glyphs[ord('x')]),
                    smaller_strike_available=points>8,path=str(path),sha256=sha(path)))
        specimen(output/f'{stem}-styles.png',entries)
        overview.append(entries[0]);accents.append(accent_entries[0])
    specimen(output/'comparison-regular.png',overview)
    specimen(output/'comparison-latin1.png',accents,latin=True)
    shutil.copyfile(HERE.parent/'reader-fonts/FONT-LICENSE.txt',output/'FONT-LICENSE.txt')
    assert before == {str(p):sha(p) for p in protected}, 'Production source changed'
    report.update(status='passed',production_files_unchanged=before,smallest_source_points=8,
                  latin1_coverage='ASCII 32–126 and Latin-1 160–255; controls blank. Not a Neo charset mapping.',
                  composed_glyphs={'U+00DF':'SS ligature','U+00FF':'Y with diaeresis from hinted Ä'},
                  accent_comparison='Current rule extended experimentally to Latin-1; production conversion remains ASCII.',
                  superscript_policy='ASCII digits unchanged in every face. No BibleWise superscript glyphs or private slots included.')
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f"PASS {len(report['faces'])} face comparisons, 36 BDF round trips; {report['current_resize_capture_checks']} current glyphs matched accepted captures")


if __name__ == '__main__':
    main()
