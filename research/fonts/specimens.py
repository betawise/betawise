#!/usr/bin/env python3
"""Render current shipping BDFs into deterministic 264x65 specimen cards."""
import html
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

from research_paths import BUILD, generation_report
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'fonts'))
import fontgen

OUT = BUILD / 'specimens'
STYLES = ['Regular', 'Bold', 'Italic', 'BoldItalic']
SIZES = {3: 'Large', 4: 'Medium', 5: 'Small', 6: 'Tiny'}
TEXT = ('A calm reader enjoys clear type. COGQ acç ijmw 0123456789. '
        'ÀÁÂÃÄÅ ÉÊË ÑÖÜ ŠŽŸ ß € — “Hello!” The quick brown fox jumps over the lazy dog. ')


def screen(glyphs, lines):
    image = Image.new('1', (264, 65))
    x = row = 0
    for slot in (TEXT * 12).encode('cp1252'):
        glyph = glyphs[slot]
        if x + glyph.width > 264:
            x = 0
            row += 1
        if row == lines:
            break
        y = row * glyph.height
        if y + glyph.height > 65:
            assert not glyph.crop((0, 65-y, glyph.width, glyph.height)).getbbox()
        image.paste(glyph, (x, y))
        x += glyph.width
    assert row == lines
    return image


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report = generation_report()
    label = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 20)
    title = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 28)
    links = []
    for family in ('Serif', 'Sans', 'Book', 'Mono'):
        card = Image.new('RGB', (2200, 890), 'white')
        draw = ImageDraw.Draw(card)
        draw.text((16, 10), f'BetaWise {family} — current generated BDFs', font=title, fill='black')
        draw.text((16, 49), '264 × 65 screens at 2× nearest-neighbour enlargement; original bitmap pixels, no smoothing.', font=label, fill='#505050')
        for index, style in enumerate(STYLES):
            draw.text((18 + index*545, 88), style, font=title, fill='black')
        for row, (lines, size) in enumerate(SIZES.items()):
            record = next(f for f in report['fonts'] if f['family'] == family and f['lines'] == lines)
            top = 130 + row*188
            detail = f'{lines} lines · {size} · native {record["pixels"]}px'
            if record['mono_width']:
                detail += f' · {record["mono_width"]}px fixed cell'
            draw.text((18, top), detail, font=label, fill='#454545')
            for index, style in enumerate(STYLES):
                path = ROOT / f'fonts/build/bdf/BetaWise{family}/BetaWise{family}-{size}-{style}.bdf'
                glyphs = fontgen.load(path, 'iso8859-1', 63)
                mask = screen(glyphs, lines).resize((528, 130), Image.Resampling.NEAREST)
                x, y = 18 + index*545, top + 33
                draw.rectangle((x-1, y-1, x+528, y+130), outline='#9fa99f')
                card.paste('black', (x, y, x+528, y+130), mask)
            draw.line((16, top+176, 2180, top+176), fill='#c7cdc7')
        filename = family.lower() + '.png'
        card.save(OUT / filename)
        links.append(f'<h2>BetaWise {family}</h2><a href="{filename}"><img src="{filename}" alt="{html.escape(family)} all sizes and styles"></a>')
    (OUT / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Current font specimens</title><style>body{font:18px sans-serif;margin:24px}img{max-width:100%;image-rendering:pixelated}</style><h1>Current BetaWise font specimens</h1><p>Rows: 3, 4, 5, 6 lines. Columns: Regular, Bold, Italic, BoldItalic. Click to view full size.</p>' + ''.join(links))
    print(OUT / 'index.html')


if __name__ == '__main__':
    main()
