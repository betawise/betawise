#!/usr/bin/env python3
"""Build four-face, six-row ASCII/curly-quote Neo test fonts from installed X11 PCF assets."""
import hashlib
import json
from pathlib import Path
from PIL import Image
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'betawise/fonts'))
from fontgen import load

FAMILIES = [
    ('CenturySchoolbook', 'Century Schoolbook', 'ncen', ('R', 'B', 'I', 'BI'), 0xFF30),
    ('Helvetica', 'Helvetica', 'helv', ('R', 'B', 'O', 'BO'), 0xFF31),
    ('Times', 'Times', 'tim', ('R', 'B', 'I', 'BI'), 0xFF32),
]


def declaration(kind, name, values):
    return f'static const {kind} {name}[] = {{' + ','.join(map(str, values)) + '};\n'


def build_fonts():
    output = HERE / 'build'
    output.mkdir(exist_ok=True)
    (output / 'Makefile').write_text(
        'FONT ?= Helvetica\nTARGET = $(FONT).OS3KApp\nOBJ = $(FONT).o\n'
        'include ../../../../Makefile.common\n')
    manifest = []
    for stem, title, family, styles, identifier in FAMILIES:
        arrays = []
        descriptors = []
        sources = []
        for face, style in enumerate(styles):
            points = '10'
            path = Path('/usr/share/fonts/X11/75dpi') / f'{family}{style}{points}.pcf.gz'
            original = load(path, 'cp1252', ord('?'))
            # Neo-US quote positions 91..94 match CP1252. Other extended slots
            # remain explicitly unsupported in these temporary demo fonts.
            glyphs = [original[c] if 32 <= c < 127 or 0x91 <= c <= 0x94 else original[ord('?')] for c in range(256)]
            # Eleven-pixel cells need an empty last row for six rows on the LCD.
            trim_top = 3 if family == 'helv' else 2
            padded = []
            for glyph in glyphs:
                assert glyph.height == 13
                if trim_top:
                    assert not any(glyph.getpixel((x, y)) for y in range(trim_top) for x in range(glyph.width))
                    glyph = glyph.crop((0, trim_top, glyph.width, glyph.height))
                canvas = Image.new(glyph.mode, (glyph.width, 11))
                canvas.paste(glyph, (0, -1 if family == 'ncen' else 0))
                padded.append(canvas)
            glyphs = padded
            # The full eleven-row serif ink is retained; the sixth line may
            # lose its bottom pixel on the 65-row LCD.
            height = 11
            widths = []
            offsets = []
            pixels = []
            for glyph in glyphs:
                widths.append(glyph.width)
                offsets.append(len(pixels))
                for band in range(0, height, 8):
                    for x in range(glyph.width):
                        pixels.append(sum(1 << (y - band) for y in range(band, min(band + 8, height))
                            if glyph.getpixel((x, y))))
            arrays.extend([
                declaration('uint8_t', f'widths_{face}', widths),
                declaration('uint16_t', f'offsets_{face}', offsets),
                declaration('uint8_t', f'pixels_{face}', pixels),
            ])
            descriptors.append(f'{{{height},{max(widths)},{max(widths)*((height+7)//8)},0,'
                f'widths_{face},offsets_{face},pixels_{face}}}')
            sources.append(dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                height=height, trim_top=trim_top, shift_up=1 if family == 'ncen' else 0, coverage='ASCII 32..126 and Neo curly quotes 91..94; other slots use question mark'))
        source = f'''#include "os3k.h"
APPLET_HEADER_BEGIN
    APPLET_FLAGS(APPLET_FLAG_FONT | APPLET_FLAG_HIDDEN)
    APPLET_ID({identifier})
    APPLET_FONT_NAME("{title}")
    APPLET_INFO("X11 Adobe bitmap font; see FONT-LICENSE.txt")
    APPLET_VERSION(0, 1, "a")
    APPLET_LANGUAGE_EN_US
APPLET_HEADER_END
'''
        source += ''.join(arrays) + 'static FontHeader_t faces[4] = {' + ','.join(descriptors) + '};\n'
        source += '''void ProcessMessage(Message_e message, uint32_t parameter, uint32_t* reply) {
    *reply = 0;
    switch(message) {
        case MSG_FONT_GET_NAME:
            *(const char**)parameter = APPLET_FONT_NAME_PTR;
            break;
        case MSG_FONT_GET_NORMAL:
            *(FontHeader_t**)parameter = &faces[0];
            break;
        case MSG_FONT_GET_BOLD:
            *(FontHeader_t**)parameter = &faces[1];
            break;
        case MSG_FONT_GET_ITALIC:
            *(FontHeader_t**)parameter = &faces[2];
            break;
        case MSG_FONT_GET_BOLD_ITALIC:
            *(FontHeader_t**)parameter = &faces[3];
            break;
        case MSG_FONT_GET_HEIGHT:
            *(uint32_t*)parameter = faces[0].height;
            break;
    }
}
'''
        (output / f'{stem}.c').write_text(source)
        subprocess.run(['make', '-C', str(output), f'FONT={stem}'], check=True)
        manifest.append(dict(name=title, stem=stem, id=identifier, height=height, sources=sources,
            app_sha256=hashlib.sha256((output / f'{stem}.OS3KApp').read_bytes()).hexdigest()))
    (output / 'fonts.json').write_text(json.dumps(manifest, indent=2))
    shutil.copyfile('/usr/share/doc/xfonts-75dpi/copyright', HERE / 'FONT-LICENSE.txt')
    return manifest


if __name__ == '__main__':
    print(json.dumps(build_fonts(), indent=2))
