#!/usr/bin/env python3
"""Rebase built font images and compare every descriptor/glyph with its BDF.

Uses the SDK's flash/RAM image layout and fixup table at displaced bases, without
emulator sessions, screenshots, or inference. Covers single- and four-face apps.
"""
import importlib.util
import os
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / 'fonts'
SPEC = importlib.util.spec_from_file_location('fontgen', FONTS / 'fontgen.py')
fontgen = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fontgen)
ROM_BASE = 0x710000
RAM_BASE = 0x30000
LINK_RAM = 0x80000000
STYLES = [('', 'Regular'), ('BOLD_', 'Bold'), ('ITALIC_', 'Italic'),
          ('BOLD_ITALIC_', 'BoldItalic')]


def symbols(elf):
    tool = os.environ.get('CROSS_COMPILE', 'm68k-linux-gnu-') + 'readelf'
    output = subprocess.check_output([tool, '-sW', elf], text=True)
    result = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 8 and fields[0].rstrip(':').isdigit():
            result[fields[7]] = int(fields[1], 16)
    return result


def check(image):
    base = image.stem
    sym = symbols(FONTS / 'build' / base / (base + '.elf'))
    flash = image.read_bytes()
    size = sym['__os3k_image_size']
    start = sym['__os3k_image_offset']
    ram = bytearray(flash[start:start + size])
    assert len(ram) == size

    def rebase(value):
        return RAM_BASE + value - LINK_RAM if value & LINK_RAM else ROM_BASE + value

    offsets = list(range(0, sym['__os3k_got_size'], 4))
    cursor = sym['__os3k_fixups_offset']
    while True:
        offset, = struct.unpack_from('>I', flash, cursor)
        cursor += 4
        if not offset:
            break
        offsets.append(offset)
    assert len(set(offsets)) == len(offsets)
    for offset in offsets:
        value, = struct.unpack_from('>I', ram, offset)
        struct.pack_into('>I', ram, offset, rebase(value))

    if base.startswith('BetaWiseTerminal-'):
        size_name = base.removeprefix('BetaWiseTerminal-')
        source_name = {'Medium': 'glyphs.bdf', 'Small': 'glyphs-5x7.bdf',
                       'Tiny': 'glyphs-4x6.bdf'}[size_name]
        sources = [('', FONTS / 'build/bdf/BetaWiseTerminal' / source_name, 63)]
    else:
        family = base.split('-')[0]
        sources = [(prefix, FONTS / 'build/bdf' / family / f'{base}-{style}.bdf', 0x3f)
                   for prefix, style in STYLES]
        sources.append(('PRIVATE_', FONTS / 'build/bdf' / family / 'private' / f'{base}-SmallCaps.bdf', 'blank'))
    descriptors = {name for name in sym if name.endswith('GLYPH_FONT')}
    assert descriptors == {prefix + 'GLYPH_FONT' for prefix, _, _ in sources}
    for prefix, source, fallback in sources:
        offset = sym[prefix + 'GLYPH_FONT'] - LINK_RAM
        assert 0 <= offset <= size - 16  # Initialized RAM, never unrebased ROM/BSS.
        height, max_width, max_bytes, padding, widths, offsets_ptr, bitmap = (
            struct.unpack_from('>4BIII', ram, offset))
        assert padding == 0
        expected = fontgen.load(source, 'iso8859-1', fallback)
        for code, glyph in enumerate(expected):
            width = flash[widths - ROM_BASE + code] if widths else max_width
            data_offset = (struct.unpack_from('>H', flash, offsets_ptr - ROM_BASE + code * 2)[0]
                           if offsets_ptr else code * max_bytes)
            assert height == glyph.height and width == glyph.width
            actual = bitmap - ROM_BASE + data_offset
            packet = bytes(sum(1 << (y - band)
                               for y in range(band, min(band + 8, height))
                               if glyph.getpixel((x, y)))
                           for band in range(0, height, 8) for x in range(width))
            assert flash[actual:actual + len(packet)] == packet, (base, prefix, code)
    return len(sources)


def main():
    images = sorted(FONTS.glob('build/**/*.OS3KApp'))
    assert len(images) == 19
    faces = sum(check(image) for image in images)
    assert faces == 83
    print(f'PASS {len(images)} rebased images, {faces} descriptors, '
          f'{faces * 256:,} exact glyphs; Terminal has one descriptor, readers five')


if __name__ == '__main__':
    main()
