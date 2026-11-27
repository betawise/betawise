#!/usr/bin/env python3
"""Convert 256-slot PNG strips, BDF, or PCF fonts to Neo bitmap tables.

BDF ENCODING values are native byte slots. PCF uses Pillow's codec mapping
(ISO-8859-1 by default). Missing slots fail rather than silently substituting.
"""
import argparse
import gzip
import re
from pathlib import Path
from PIL import Image, PcfFontFile


class UnicodePCF(PcfFontFile.PcfFontFile):
    codes = []

    def _load_encoding(self):
        stream, _, read16, _ = self._getformat(PcfFontFile.PCF_BDF_ENCODINGS)
        c0,c1,r0,r1,_ = [read16(stream.read(2)) for _ in range(5)]
        width = c1-c0+1
        entries = [read16(stream.read(2)) for _ in range(width*(r1-r0+1))]
        out = [None]*256
        for index,code in enumerate(self.codes):
            row,col = code>>8,code&255
            if r0<=row<=r1 and c0<=col<=c1:
                value = entries[(row-r0)*width+col-c0]
                if value!=65535:out[index]=value
        return out


def read_unicode_source(path, codes):
    """Read original ISO10646 BDF/PCF glyphs in baseline-relative coordinates.

    This is separate from load_bdf(), whose ENCODING values are Neo byte slots.
    """
    path = Path(path)
    name = path.name.lower().removesuffix('.gz')
    opener = gzip.open if path.suffix == '.gz' else open
    if name.endswith('.pcf'):
        UnicodePCF.codes = tuple(codes)
        with opener(path, 'rb') as stream:
            font = UnicodePCF(stream)
        info = {key.decode(): value.decode(errors='replace') if isinstance(value, bytes) else value
                for key, value in font.info.items()}
        glyphs = {}
        for code, glyph in zip(codes, font.glyph):
            if glyph is None:
                continue
            advance, (left, top, right, bottom), rect, bitmap = glyph
            image = bitmap.crop(rect)
            points = {(left+x, top+y) for y in range(image.height)
                      for x in range(image.width) if image.getpixel((x, y))}
            glyphs[code] = dict(advance=advance[0], points=points)
    elif name.endswith('.bdf'):
        with opener(path, 'rt', encoding='ascii') as stream:
            lines = iter(stream)
            if next(lines).strip() != 'STARTFONT 2.1':
                raise ValueError('expected BDF 2.1')
            info, glyphs = {}, {}
            requested = set(codes)
            for line in lines:
                fields = line.split()
                if not fields:
                    continue
                if fields[0] != 'STARTCHAR':
                    info[fields[0]] = ' '.join(fields[1:]).strip('"')
                    continue
                props = {}
                for line in lines:
                    fields = line.split()
                    if fields[0] == 'BITMAP':
                        break
                    props[fields[0]] = fields[1:]
                width, height, left, bottom = map(int, props['BBX'])
                rows = [next(lines).strip() for _ in range(height)]
                if next(lines).strip() != 'ENDCHAR':
                    raise ValueError('missing ENDCHAR')
                code = int(props['ENCODING'][0])
                if code not in requested:
                    continue
                points = {(left+x, -bottom-height+y)
                          for y, row in enumerate(rows) for x in range(width)
                          if int(row, 16) & (1 << (8*((width+7)//8)-1-x))}
                glyphs[code] = dict(advance=int(props['DWIDTH'][0]), points=points)
    else:
        raise ValueError('expected Unicode BDF or PCF source')
    if info.get('CHARSET_REGISTRY') != 'ISO10646':
        raise ValueError(f'{path}: source must declare ISO10646')
    return info, glyphs


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
        if missing_glyph == 'blank':
            blank_ascent = max([ascent or 0] + [-g[1][1] for g in glyphs if g])
            blank_descent = max([descent or 0] + [g[1][3] for g in glyphs if g])
            blank_height = blank_ascent + blank_descent
            fallback = ((1, 0), (0, -blank_ascent, 1, blank_descent),
                        (0, 0, 1, blank_height), Image.new('1', (1, blank_height)))
        else:
            if not 0 <= missing_glyph < 256 or glyphs[missing_glyph] is None:
                raise ValueError('fallback slot must contain a glyph')
            fallback = glyphs[missing_glyph]
        for c in missing:
            glyphs[c] = fallback
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


def generate(source, destination, codec='iso8859-1', missing_glyph=None, symbol_prefix=''):
    if symbol_prefix and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', symbol_prefix):
        raise ValueError('symbol prefix must be a C identifier')
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
        out.append('#define GLYPH_PROPORTIONAL 1\n')
        for typ, name, values in [('uint8_t','GLYPH_WIDTHS',widths),
                                  ('uint16_t','GLYPH_OFFSETS',offsets),
                                  ('uint8_t','GLYPH_DATA',data)]:
            out.append(f'const {typ} {name}[{len(values)}] = {{' + ', '.join(map(str, values)) + '};\n')
        out.append('\n')
    tables = ('0', '0', 'GLYPHS[0]') if len(set(widths)) == 1 else (
        'GLYPH_WIDTHS', 'GLYPH_OFFSETS', 'GLYPH_DATA')
    # Runtime providers assign addresses directly; GCC handles PC-relative LEAs.
    out.append('#ifdef FONT_RUNTIME_DESCRIPTORS\n'
               'static __attribute__((always_inline)) inline void GLYPH_INIT(FontHeader_t *font) {\n'
               '    font->height = GLYPH_HEIGHT; font->max_width = GLYPH_WIDTH;\n'
               '    font->max_bytes = GLYPH_BYTES; font->padding = 0;\n'
               f'    font->width_table = {tables[0]};\n'
               f'    font->offset_table = {tables[1]};\n'
               f'    font->bitmap_data = {tables[2]};\n'
               '}\n#else\n')
    # With -msep-data GCC places pointer-bearing const descriptors in
    # .data.rel.ro.* automatically; crt0 rebases them. Glyphs stay in flash.
    out.append('static const FontHeader_t GLYPH_FONT = {\n'
               '    GLYPH_HEIGHT, GLYPH_WIDTH, GLYPH_BYTES, 0,\n'
               f'    {tables[0]}, {tables[1]}, {tables[2]}\n'
               '};\n#endif\n')
    out.append('#endif\n')
    text = ''.join(out)
    if symbol_prefix:
        text = re.sub(r'\b(GLYPH\w*|GLYPHS)\b', lambda m: symbol_prefix + m[0], text)
    Path(destination).write_text(text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source'); parser.add_argument('destination')
    parser.add_argument('--pcf-encoding', default='iso8859-1', help='Python codec for PCF slot mapping')
    parser.add_argument('--missing-glyph', type=lambda s: 'blank' if s == 'blank' else int(s, 0),
                        help='explicit fallback byte slot (e.g. 0x3f) or blank; default: reject missing glyphs')
    parser.add_argument('--symbol-prefix', default='', help='prefix generated C symbols/macros for multi-style fonts')
    args = parser.parse_args()
    generate(args.source, args.destination, args.pcf_encoding, args.missing_glyph, args.symbol_prefix)
