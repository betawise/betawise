#!/usr/bin/env python3
"""Render the actual private BDF as a 32-column, eight-row assignment card."""
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

from research_paths import BUILD, ensure_bdfs

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'fonts'))
import fontgen


def render(descriptor, images, destination, description,
           title_text='Neo private charset — 32 × 8 slots'):
    entries = {}
    colors = {'regular': '#222222', 'italic': '#16814d', 'bold': '#8341a0', 'digit': '#185ec6'}
    for letter in descriptor['letters']:
        for style in descriptor['styles']:
            entries[int(letter[style], 16)] = (letter['text'], style)
    for digit, slot in enumerate(descriptor['superscript_digits']):
        entries[int(slot, 16)] = (str(digit), 'digit')
    reserved = {int(slot, 16) for slot in descriptor['reserved']}
    assert len(entries) == 196 and not entries.keys() & reserved
    cell_w, cell_h, left, top = 76, 100, 48, 132
    card = Image.new('RGB', (left + 32 * cell_w + 20, top + 8 * cell_h + 24), 'white')
    draw = ImageDraw.Draw(card)
    face = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    title = ImageFont.truetype(face, 27)
    label = ImageFont.truetype(face, 14)
    draw.text((20, 12), title_text, font=title, fill='#111111')
    draw.text((20, 50), description, font=label, fill='#333333')
    for i, (text, color) in enumerate([('Regular', colors['regular']), ('Italic', colors['italic']), ('Bold', colors['bold']), ('Superscript', colors['digit']), ('Reserved / editor control', '#bc2222'), ('Unused', '#888888')]):
        draw.text((20 + i * 310, 78), text, font=label, fill=color)
    for column in range(32):
        draw.text((left + column * cell_w + 22, top - 24), f'{column:02X}', font=label, fill='#555555')
    for slot in range(256):
        x, y = left + slot % 32 * cell_w, top + slot // 32 * cell_h
        if slot % 32 == 0:
            draw.text((8, y + 37), f'{slot:02X}', font=label, fill='#555555')
        background = '#ffe5e5' if slot in reserved else ('white' if slot in entries else '#eeeeee')
        draw.rectangle((x, y, x + cell_w - 1, y + cell_h - 1), fill=background, outline='#bbbbbb')
        draw.text((x + 5, y + 4), f'{slot:02X}', font=label, fill='#a82020' if slot in reserved else '#777777')
        if slot in entries:
            text, style = entries[slot]
            assert slot in images
            bitmap = images[slot]
            scale = min(3, (cell_w - 8) // bitmap.width)
            bitmap = bitmap.resize((bitmap.width * scale, bitmap.height * scale), Image.Resampling.NEAREST)
            card.paste(colors[style], (x + (cell_w - bitmap.width) // 2, y + 26), bitmap)
            draw.text((x + 5, y + 80), text, font=label, fill=colors[style])
        elif slot in reserved:
            draw.text((x + 5, y + 42), 'reserved', font=label, fill='#bc2222')
    destination.parent.mkdir(parents=True, exist_ok=True)
    card.save(destination)
    print(destination)


def main():
    ensure_bdfs()
    descriptor = json.loads((ROOT / 'os3k/charsets/neo-smallcaps.json').read_text())
    path = ROOT / 'fonts/build/bdf/BetaWiseBook/private/BetaWiseBook-Medium-SmallCaps.bdf'
    raw, _, _ = fontgen.load_bdf(path)
    cells = fontgen.load(path, 'iso8859-1', 'blank')
    images = {slot: image for slot, image in enumerate(cells) if raw[slot] is not None}
    render(descriptor, images, BUILD/'smallcaps/charset-32x8.png',
           'Regular: source-bit transform   •   Italic: XOR 2B   •   Bold: XOR 40   •   Digits: 30–39')


if __name__ == '__main__':
    main()
