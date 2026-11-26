#!/usr/bin/env python3
"""Build an offline glyph-fix picker from the current editable BDFs."""
import argparse
import base64
import json
import unicodedata
import sys
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'fonts'))
import fontgen
from research_paths import BUILD, ensure_bdfs

sys.path.insert(0, str(ROOT / "os3k"))
from charsets import load as load_charset

HERE = Path(__file__).resolve().parent
FAMILIES = ['Serif', 'Sans', 'Book', 'Mono', 'Terminal']
SIZES = {'Large': ('Large', 3), 'Medium': ('Medium', 4),
         'Small': ('Small', 5), 'Tiny': ('Tiny', 6)}


def pack(image):
    stride = (image.width + 7) // 8
    data = bytearray(stride * image.height)
    for y in range(image.height):
        for x in range(image.width):
            if image.getpixel((x, y)):
                data[y * stride + x // 8] |= 0x80 >> (x % 8)
    return dict(width=image.width, height=image.height,
                bits=base64.b64encode(data).decode())


def system_reference(slots):
    from PIL import Image
    path = ROOT.parent / 'Ghidra/Alphasmart Neo/SmartApplets/os3kneorom.os3kos'
    data = path.read_bytes()
    base = 0x410000
    height, width, stride, _, widths, offsets, pixels = struct.unpack_from(
        '>4BIII', data, 0x44af8e - base)
    assert height == 16 and width == 6, 'unexpected Neo system-font descriptor'
    result = {}
    for slot in slots:
        w = data[widths - base + slot] if widths else width
        off = struct.unpack_from('>H', data, offsets - base + 2 * slot)[0] if offsets else slot * stride
        image = Image.new('1', (w, height))
        for y in range(height):
            for x in range(w):
                value = data[pixels - base + off + (y // 8) * w + x]
                image.putpixel((x, y), (value >> (y % 8)) & 1)
        result[str(slot)] = pack(image)
    return result


def build_data(include_reference=True):
    ensure_bdfs()
    faces = []
    mapping = load_charset(ROOT / 'os3k/charsets/neo-us.txt')
    for family in FAMILIES:
        for path in sorted((ROOT / 'fonts/build/bdf' / ('BetaWise' + family)).glob('*.bdf')):
            if family == 'Terminal':
                size, lines = {'glyphs.bdf': ('Medium', 8),
                               'glyphs-5x7.bdf': ('Small', 9),
                               'glyphs-4x6.bdf': ('Tiny', 10)}[path.name]
                style = 'Regular'
            else:
                _, size, style = path.stem.split('-')
                lines = SIZES[size][1]
            label = size
            raw, ascent, descent = fontgen.load_bdf(path)
            cells = fontgen.load(path, 'iso8859-1', 0x3f)
            glyphs = []
            for slot, source in enumerate(raw):
                if source is None:
                    glyphs.append(None)
                    continue
                image = cells[slot]
                stride = (image.width + 7) // 8
                packet = bytearray(stride * image.height)
                for y in range(image.height):
                    for x in range(image.width):
                        if image.getpixel((x, y)):
                            packet[y * stride + x // 8] |= 0x80 >> (x % 8)
                # Check the packed web bitmap independently against every source cell.
                assert all(bool(packet[y * stride + x // 8] & (0x80 >> (x % 8))) ==
                           bool(image.getpixel((x, y)))
                           for y in range(image.height) for x in range(image.width))
                glyphs.append(dict(width=image.width, bits=base64.b64encode(packet).decode()))
            relative = path.relative_to(ROOT / 'fonts/build/bdf').as_posix()
            faces.append(dict(id=relative, path=relative, family='BetaWise ' + family,
                              size=size, sizeLabel=label, lines=lines, style=style,
                              height=cells[0].height, baseline=ascent,
                              maxWidth=max(g.width for g in cells), glyphs=glyphs))
    assert len(faces) == 67
    characters = [dict(char=chr(mapping[c]), name=unicodedata.name(chr(mapping[c]), ''),
                       base=(unicodedata.normalize('NFD', chr(mapping[c]))[0]))
                  if mapping[c] is not None else None for c in range(256)]
    extra = [c for c in range(256) if c < 32 or c == 127 or c in (0x81, 0x8d, 0x8f, 0x90, 0x9d)]
    return dict(format='betawise-glyph-review-data-v1', faces=faces,
                characters=characters, extraSlots=extra, references=system_reference(extra) if include_reference else {})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=BUILD / 'glyph-review.html')
    args = parser.parse_args()
    data = build_data()
    template = (HERE / 'review-template.html').read_text()
    serialized = json.dumps(data, separators=(',', ':'), ensure_ascii=True).replace('<', r'\u003c')
    page = template.replace('/*FONT_DATA*/null', serialized)
    page = page.replace('/*FONT_REVIEW_JS*/', (HERE / 'review.js').read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page)
    total = sum(sum(g is not None for g in f['glyphs']) for f in data['faces'])
    print(f'{args.output}: {len(data["faces"])} faces, {total:,} exact source glyphs')


if __name__ == '__main__':
    main()
