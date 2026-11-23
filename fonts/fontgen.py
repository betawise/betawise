#!/usr/bin/env python3
"""Convert 256-slot PNG strips, BDF, or PCF fonts to Neo bitmap tables.

BDF ENCODING values are native byte slots. PCF uses Pillow's codec mapping
(ISO-8859-1 by default). Missing slots fail rather than silently substituting.
"""
import argparse
import gzip
from pathlib import Path
from PIL import Image, PcfFontFile


def load_bdf(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='ascii') as stream:
        lines = iter(stream)
        if next(lines).strip() != 'STARTFONT 2.1':
            raise ValueError('expected BDF 2.1')
        glyphs = [None] * 256
        ascent = descent = None
        for line in lines:
            fields = line.split()
            if not fields:
                continue
            if fields[0] == 'FONT_ASCENT':
                ascent = int(fields[1])
            elif fields[0] == 'FONT_DESCENT':
                descent = int(fields[1])
            elif fields[0] == 'STARTCHAR':
                props = {}
                for line in lines:
                    parts = line.split()
                    if parts[0] == 'BITMAP':
                        break
                    props[parts[0]] = parts[1:]
                w, h, left, bottom = map(int, props['BBX'])
                if w < 0 or h < 0:
                    raise ValueError('negative BDF bitmap dimensions')
                rows = [next(lines).strip() for _ in range(h)]
                if next(lines).strip() != 'ENDCHAR':
                    raise ValueError('missing ENDCHAR')
                bitmap = Image.new('1', (w, h))
                for y, row in enumerate(rows):
                    if len(row) != 2 * ((w + 7) // 8):
                        raise ValueError('invalid BDF bitmap row length')
                    value = int(row, 16) if row else 0
                    for x in range(w):
                        bitmap.putpixel((x, y), (value >> (((w + 7)//8)*8-1-x)) & 1)
                code = int(props['ENCODING'][0])
                if not 0 <= code < 256:
                    raise ValueError('BDF must use native slots 0..255; remap Unicode fonts first')
                if glyphs[code] is not None:
                    raise ValueError(f'duplicate BDF slot {code}')
                dx, dy = map(int, props['DWIDTH'])
                if dy:
                    raise ValueError('vertical advances unsupported')
                glyphs[code] = ((dx, 0), (left, -bottom-h, left+w, -bottom),
                                (0, 0, w, h), bitmap)
        return glyphs, ascent, descent


def load(path, codec, missing_glyph=None):
    name = path.name.lower().removesuffix('.gz')
    if name.endswith('.png'):
        im = Image.open(path).convert('L')
        if im.width % 256:
            raise ValueError('glyph strip must contain 256 equal-width cells')
        w = im.width // 256
        return [im.crop((c*w, 0, (c+1)*w, im.height)).point(lambda p: int(p < 128), '1')
                for c in range(256)]
    if name.endswith('.bdf'):
        glyphs, ascent, descent = load_bdf(path)
    elif name.endswith('.pcf'):
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rb') as stream:
            glyphs = PcfFontFile.PcfFontFile(stream, charset_encoding=codec).glyph
        ascent = descent = None
    else:
        raise ValueError('expected PNG, BDF, PCF, BDF.GZ or PCF.GZ')
    glyphs = list(glyphs[:256])
    glyphs.extend([None] * (256-len(glyphs)))
    missing = [c for c, g in enumerate(glyphs) if g is None]
    if missing:
        if missing_glyph is None:
            raise ValueError('missing slots: ' + ', '.join(f'{c:02X}' for c in missing))
        if not 0 <= missing_glyph < 256 or glyphs[missing_glyph] is None:
            raise ValueError('fallback slot must contain a glyph')
        for c in missing:
            glyphs[c] = glyphs[missing_glyph]
    # Preserve declared leading and all source bounds at a common baseline.
    ascent = max([ascent or 0] + [-g[1][1] for g in glyphs])
    descent = max([descent or 0] + [g[1][3] for g in glyphs])
    result = []
    for advance, box, src, bitmap in glyphs:
        left, top, right, bottom = box
        shift = max(0, -left)
        width = max(advance[0]+shift, right+shift, 1)
        cell = Image.new('1', (width, ascent+descent))
        cell.paste(bitmap.crop(src), (left+shift, top+ascent))
        result.append(cell)
    return result


def generate(source, destination, codec='iso8859-1', missing_glyph=None):
    glyphs = load(Path(source), codec, missing_glyph)
    h = glyphs[0].height
    widths = [g.width for g in glyphs]
    if not 1 <= h <= 64 or not 1 <= max(widths) <= 255:
        raise ValueError('font dimensions exceed Neo descriptor limits')
    if max(widths)*((h+7)//8) > 255:
        raise ValueError('glyph slot exceeds one-byte max_bytes field')
    packed = []
    for im in glyphs:
        packed.append([sum(1 << (y-band) for y in range(band, min(band+8, h))
                           if im.getpixel((x, y)))
                       for band in range(0, h, 8) for x in range(im.width)])
    guard = Path(destination).name.upper().replace('.', '_').replace('-', '_') + '_INCLUDED'
    out = [f'#ifndef {guard}\n#define {guard}\n\n',
           f'#define GLYPH_HEIGHT {h}\n#define GLYPH_WIDTH {max(widths)}\n',
           f'#define GLYPH_BYTES {max(widths)*((h+7)//8)}\n\n']
    if len(set(widths)) == 1:
        out.append(f'const uint8_t GLYPHS[256][{len(packed[0])}] = {{\n')
        for c, data in enumerate(packed):
            sep = ',' if c < 255 else ' '
            out.append('    {' + ', '.join(f'0x{x:02X}' for x in data) + f'}}{sep} // {c:02X}\n')
        out.append('};\n\n')
    else:
        offsets = []; data = []
        for glyph in packed:
            offsets.append(len(data)); data.extend(glyph)
        if len(data) > 65536:
            raise ValueError('font exceeds 16-bit bitmap offset range')
        out.append('#define GLYPH_PROPORTIONAL 1\n')
        for typ, name, values in [('uint8_t','GLYPH_WIDTHS',widths),
                                  ('uint16_t','GLYPH_OFFSETS',offsets),
                                  ('uint8_t','GLYPH_DATA',data)]:
            out.append(f'const {typ} {name}[{len(values)}] = {{' + ', '.join(map(str, values)) + '};\n')
        out.append('\n')
    out.append('#endif\n')
    Path(destination).write_text(''.join(out))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source'); parser.add_argument('destination')
    parser.add_argument('--pcf-encoding', default='iso8859-1', help='Python codec for PCF slot mapping')
    parser.add_argument('--missing-glyph', type=lambda s: int(s, 0),
                        help='explicit fallback byte slot, e.g. 0x3f; default: reject missing glyphs')
    args = parser.parse_args()
    generate(args.source, args.destination, args.pcf_encoding, args.missing_glyph)
