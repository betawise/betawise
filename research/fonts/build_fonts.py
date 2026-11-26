#!/usr/bin/env python3
"""Rebuild BetaWise BDFs from original Unicode Adobe/Fixed bitmap sources.

Only six-line overflowing accents may move down one row. Letter bodies are never
rescaled. Six-line Mono Regular m is copied from Bold by explicit policy.
Mono uses one advance across every character and style.
"""
import argparse
from functools import lru_cache
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unicodedata

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
X11_ROOT = ROOT / 'fonts/upstream'
sys.path.insert(0, str(ROOT / 'fonts'))
sys.path.insert(0, str(ROOT / 'os3k'))
import fontgen
from charsets import glyph_name, load

STYLES = ['Regular', 'Bold', 'Italic', 'BoldItalic']
FAMILIES = {
    'Serif': ('tim', ['R', 'B', 'I', 'BI']),
    'Sans': ('helv', ['R', 'B', 'O', 'BO']),
    'Book': ('ncen', ['R', 'B', 'I', 'BI']),
    'Mono': ('cour', ['R', 'B', 'O', 'BO']),
}
SIZES = {3: 'Large', 4: 'Medium', 5: 'Small', 6: 'Tiny'}
PITCH = {3: 21, 4: 16, 5: 13, 6: 11, 9: 7, 10: 6}
CP1252 = list(range(32, 127)) + [c for c in range(128, 256) if c not in (129, 141, 143, 144, 157)]
SPACING_MARKS = {0x60, 0xA8, 0xAF, 0xB4, 0x2C6, 0x2D9, 0x2DC}
COPYRIGHT = ('Copyright 1984-1989, 1994 Adobe Systems Incorporated. '
             'Copyright 1988, 1994 Digital Equipment Corporation. See fonts/LICENSE.md.')


@lru_cache(maxsize=None)
def source(path, codes):
    path = Path(path)
    return fontgen.read_unicode_source(path if path.is_absolute() else ROOT / path, codes)


def source_name(path):
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def source_file(directory, stem):
    for suffix in ('.pcf.gz', '.pcf', '.bdf.gz', '.bdf'):
        path = directory / (stem + suffix)
        if path.is_file():
            return path
    raise FileNotFoundError(directory / stem)


def strikes(root, family, codes):
    stem, styles = FAMILIES[family]
    found = []
    for dpi in (75, 100):
        directory = root / f'{dpi}dpi'
        names = sorted({p.name.split('.')[0] for p in directory.glob(stem + 'R*')
                        if re.fullmatch(stem + r'R\d+', p.name.split('.')[0])})
        for name in names:
            points = int(name[len(stem) + 1:])
            paths = [source_file(directory, f'{stem}{style}{points:02}') for style in styles]
            info, _ = source(paths[0], codes)
            found.append(dict(points=points, dpi=dpi, pixels=int(info['PIXEL_SIZE']), paths=paths))
    if not found:
        raise ValueError(f'No Unicode source strikes for {family} under {root}')
    return found


def move_accent(code, glyph, face, top, bottom):
    """Translate only an overflowing upper mark; keep all body pixels intact."""
    points = glyph['points']
    if not points or min(y for x, y in points) >= top:
        return glyph, None
    delta = top - min(y for x, y in points)
    if delta != 1 or max(y for x, y in points) >= bottom:
        return glyph, None
    if code in SPACING_MARKS:
        upper, body, cut = points, set(), None
    else:
        decomposition = unicodedata.normalize('NFD', chr(code))
        if len(decomposition) < 2 or not all(unicodedata.combining(c) for c in decomposition[1:]):
            return glyph, None
        base = face.get(ord(decomposition[0]))
        if base is None or not base['points']:
            return glyph, None
        ys = {y for x, y in points}
        base_top = min(y for x, y in base['points'])
        gaps = [y for y in range(min(ys) + 1, base_top + 1) if y not in ys]
        cut = gaps[0] + 1 if gaps else base_top
        upper = {(x, y) for x, y in points if y < cut}
        body = points - upper
        if not upper or not body:
            return glyph, None
    moved = {(x, y + delta) for x, y in upper}
    # A mark tip may merge with an existing native body pixel, but may not
    # change the body silhouette or introduce new ink below its split.
    if cut is not None and any(y >= cut and (x, y) not in body for x, y in moved):
        return glyph, None
    result = body | moved
    if any(y < top or y >= bottom for x, y in result):
        return glyph, None
    assert body <= result
    return dict(advance=glyph['advance'], points=result), dict(
        operation='accent_down', pixels=delta, cut=cut,
        moved_ink=len(upper), shared_tip_pixels=len(moved & body))


def horizontal(glyph, width, italic):
    points = glyph['points']
    shift = 0 if italic else max(0, -min((x for x, y in points), default=0))
    points = {(x + shift, y) for x, y in points}
    if width is None:
        width = max(glyph['advance'] + shift, max((x + 1 for x, y in points), default=1), 1)
    return width, points, shift


def fit_option(option, family, lines, mapping, priority):
    pitch = PITCH[lines]
    limit = min(pitch, 65 - (lines - 1) * pitch)
    codes = tuple(sorted(set(mapping.values()) - {None}))
    original = [source(path, codes)[1] for path in option['paths']]
    if any(any(mapping[c] not in face for c in CP1252) for face in original):
        return None
    mono = family in ('Mono', 'Terminal')
    native_advance = original[0][65]['advance'] if mono else None
    choices = []
    for baseline in range(pitch + 1):
        top, bottom = -baseline, -baseline + limit
        adjusted, mark_ops = [], []
        for face in original:
            altered, operations = {}, {}
            for code, glyph in face.items():
                new, operation = move_accent(code, glyph, face, top, bottom) if lines == 6 else (glyph, None)
                altered[code] = new
                if operation:
                    operations[code] = operation
            adjusted.append(altered)
            mark_ops.append(operations)
        for padding in ((0, 1) if family == 'Mono' else (0,)):
            width = native_advance + padding if mono else None
            exceptions, upright_loss, italic_loss = set(), 0, 0
            valid = True
            for index, face in enumerate(adjusted):
                italic = family == 'Mono' and index in (2, 3)
                for slot in CP1252:
                    w, points, _ = horizontal(face[mapping[slot]], width, italic)
                    outside = {(x, y) for x, y in points if x < 0 or x >= w or y < top or y >= bottom}
                    if points and outside == points:
                        valid = False  # Never turn a real glyph into a blank.
                        break
                    xs = [x for x, y in points]
                    ys = [y for x, y in points]
                    if not points:
                        continue
                    over = [max(0, top - min(ys)), max(0, max(ys) + 1 - bottom)]
                    if not italic:
                        over += [max(0, -min(xs)), max(0, max(xs) + 1 - w)]
                    edges = [n for n in over if n]
                    if len(edges) > 1 or any(n > 1 for n in edges):
                        valid = False
                        break
                    if edges:
                        exceptions.add(slot)
                    if italic:
                        italic_loss += len(outside)
                    else:
                        upright_loss += len(outside)
                if not valid:
                    break
            if valid and len(exceptions) <= 4:
                rank = (-len(exceptions & priority), -len(exceptions), -upright_loss,
                        -italic_loss, -padding, -sum(len(o) for o in mark_ops), -baseline)
                choices.append((rank, baseline, width, padding, adjusted, mark_ops, exceptions))
    if not choices:
        return None
    best = max(choices, key=lambda c: c[0])
    return dict(option=option, original=original, pitch=pitch, limit=limit, best=best)


def choose(root, family, lines, mapping, priority, fixed=None):
    codes = tuple(sorted(set(mapping.values()) - {None}))
    if fixed:
        path = source_file(root / 'misc', fixed)
        info, _ = source(path, codes)
        options = [dict(points=int(info['POINT_SIZE']) // 10,
                        dpi=int(info['RESOLUTION_Y']), pixels=int(info['PIXEL_SIZE']), paths=[path])]
    else:
        options = strikes(root, family, codes)
        if lines == 6:
            # Retain the previously selected six-line strike; restore its artwork.
            options = [option for option in options if option['pixels'] == 8]
    accepted = []
    for option in options:
        candidate = fit_option(option, family, lines, mapping, priority)
        if candidate:
            # Size comes first. Keyboard priority chooses placement/width among
            # valid options; it must not force a smaller font for one rare glyph.
            accepted.append(((option['pixels'], candidate['best'][0], option['dpi']), candidate))
    if not accepted:
        raise ValueError(f'No reproducible fit for {family}, {lines} lines')
    return max(accepted, key=lambda c: c[0])[1]


def export_choice(choice, family, lines, mapping, destination):
    _, baseline, mono_width, padding, faces, mark_ops, exceptions = choice['best']
    pitch, limit, option = choice['pitch'], choice['limit'], choice['option']
    files, operations, missing = [], [], []
    size = SIZES.get(lines, {9: 'Small', 10: 'Tiny'}.get(lines))
    for index, face in enumerate(faces):
        style = STYLES[index]
        italic = family == 'Mono' and index in (2, 3)
        cells = {}
        for slot, code in mapping.items():
            if code is None or code not in face:
                missing.append(dict(style=style, slot=f'{slot:02X}', reason='not in source'))
                continue
            glyph = face[code]
            if family == 'Mono' and lines == 6 and index == 0 and code == ord('m'):
                glyph = faces[1][code]
                operations.append(dict(style=style, slot=f'{slot:02X}', char=chr(code),
                                       operation='copy_from_bold'))
            width, points, shift = horizontal(glyph, mono_width, italic)
            vertical = {(x, y) for x, y in points if y < -baseline or y >= -baseline + limit}
            horizontal_loss = {(x, y) for x, y in points if x < 0 or x >= width}
            if slot not in CP1252 and (vertical or (horizontal_loss and not italic)):
                missing.append(dict(style=style, slot=f'{slot:02X}', reason='does not fit'))
                continue
            if code in mark_ops[index]:
                operations.append(dict(style=style, slot=f'{slot:02X}', char=chr(code), **mark_ops[index][code]))
            if vertical or horizontal_loss:
                operations.append(dict(style=style, slot=f'{slot:02X}', char=chr(code),
                    operation='clip', vertical=sorted(vertical), horizontal=sorted(horizontal_loss)))
            cell = Image.new('1', (width, pitch))
            kept = points - vertical - horizontal_loss
            for x, y in kept:
                cell.putpixel((x, y + baseline), 1)
            assert sum(bool(p) for p in cell.getdata()) == len(kept)
            cells[slot] = cell
        relative = (Path('BetaWiseTerminal') / ('glyphs-5x7.bdf' if lines == 9 else 'glyphs-4x6.bdf')
                    if family == 'Terminal' else Path('BetaWise' + family) / f'BetaWise{family}-{size}-{style}.bdf')
        write_bdf(destination / relative, family, size, style, cells, baseline, option, mapping)
        files.append(str(relative))
        if mono_width is not None:
            assert {g.width for g in cells.values()} == {mono_width}
    return dict(family=family, lines=lines, pixels=option['pixels'], points=option['points'],
                dpi=option['dpi'], pitch=pitch, usable_ink_rows=limit, baseline=baseline,
                native_advance=choice['original'][0][65]['advance'], mono_width=mono_width,
                added_column=padding, sources=[source_name(p) for p in option['paths']], files=files,
                clipping_slots=[f'{c:02X}' for c in sorted(exceptions)], operations=operations, missing=missing)


def write_bdf(path, family, size, style, cells, baseline, option, mapping):
    pitch = next(iter(cells.values())).height
    descent = pitch - baseline
    width = max(g.width for g in cells.values())
    bold, italic = style in ('Bold', 'BoldItalic'), style in ('Italic', 'BoldItalic')
    slant = ('O' if family in ('Sans', 'Mono') else 'I') if italic else 'R'
    spacing = 'C' if family == 'Terminal' else 'M' if family == 'Mono' else 'P'
    props = [f'FONT_ASCENT {baseline}', f'FONT_DESCENT {descent}',
             f'COPYRIGHT "{COPYRIGHT if family != "Terminal" else "Public domain X11 Misc Fixed; see fonts/LICENSE.md."}"',
             f'FAMILY_NAME "BetaWise {family}"', f'FULL_NAME "BetaWise {family} {style} {size}"',
             f'WEIGHT_NAME "{"Bold" if bold else "Medium"}"', f'SLANT "{slant}"',
             'SETWIDTH_NAME "Normal"', f'PIXEL_SIZE {option["pixels"]}', f'POINT_SIZE {option["points"]*10}',
             f'RESOLUTION_X {option["dpi"]}', f'RESOLUTION_Y {option["dpi"]}', f'SPACING "{spacing}"',
             'CHARSET_REGISTRY "NEO"', 'CHARSET_ENCODING "US"']
    text = ['STARTFONT 2.1', 'COMMENT Generated by research/fonts/build_fonts.py; charset os3k/charsets/neo-us.txt',
            f'FONT -betawise-{family.lower()}-{"bold" if bold else "medium"}-{slant.lower()}-normal--{option["pixels"]}-{option["points"]*10}-{option["dpi"]}-{option["dpi"]}-{spacing.lower()}-0-neo-us',
            f'SIZE {option["points"]} {option["dpi"]} {option["dpi"]}',
            f'FONTBOUNDINGBOX {width} {pitch} 0 {-descent}', f'STARTPROPERTIES {len(props)}',
            *props, 'ENDPROPERTIES', f'CHARS {len(cells)}']
    for slot, image in sorted(cells.items()):
        text += [f'STARTCHAR {glyph_name(slot, mapping)}', f'ENCODING {slot}', 'SWIDTH 500 0',
                 f'DWIDTH {image.width} 0', f'BBX {image.width} {pitch} 0 {-descent}', 'BITMAP']
        for y in range(pitch):
            row = 0
            for x in range(image.width):
                row = (row << 1) | bool(image.getpixel((x, y)))
            text.append(f'{row << ((-image.width) % 8):0{2*((image.width+7)//8)}X}')
        text.append('ENDCHAR')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(text + ['ENDFONT', '']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--x11-root', type=Path, default=X11_ROOT)
    parser.add_argument('--charset', type=Path, default=ROOT / 'os3k/charsets/neo-us.txt')
    parser.add_argument('--output', type=Path, default=ROOT / 'fonts/build/bdf')
    parser.add_argument('--terminal-medium', type=Path, default=ROOT / 'fonts/BetaWiseTerminal/glyphs.bdf')
    args = parser.parse_args()
    global MAPPING
    MAPPING = load(args.charset)
    priority = set(json.loads((Path(__file__).with_name('keyboard-characters.json')).read_text())['slots'])
    medium = args.terminal_medium.read_bytes()
    records = []
    # Staging prevents a partial source update if any selection or assertion fails.
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='native-fonts-', dir=args.output.parent) as directory:
        staging = Path(directory)
        for family in FAMILIES:
            for lines in SIZES:
                selected = choose(args.x11_root, family, lines, MAPPING, priority)
                record = export_choice(selected, family, lines, MAPPING, staging)
                records.append(record)
                print(f'{family} {lines}: {record["pixels"]}px, width {record["mono_width"] or "variable"}, '
                      f'{sum(o["operation"] == "accent_down" for o in record["operations"])} mark moves', flush=True)
        for lines, fixed in ((9, '5x7'), (10, '4x6')):
            selected = choose(args.x11_root, 'Terminal', lines, MAPPING, priority, fixed)
            records.append(export_choice(selected, 'Terminal', lines, MAPPING, staging))
        target = staging / 'BetaWiseTerminal/glyphs.bdf'
        target.write_bytes(medium)
        from build_private_fonts import generate as generate_private
        private_records = generate_private(staging, staging, args.x11_root)
        # Re-read every BDF through the production converter; check fixed advances.
        for path in staging.rglob('*.bdf'):
            raw, ascent, descent = fontgen.load_bdf(path)
            fontgen.load(path, 'iso8859-1', 'blank' if path.parent.name == 'private' else 63)
            if path.parent.name == 'BetaWiseMono':
                assert len({g[0][0] for g in raw if g}) == 1
        for path in staging.rglob('*.bdf'):
            relative = path.relative_to(staging)
            destination = args.output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
    assert args.terminal_medium.read_bytes() == medium
    report = dict(private_faces=private_records, policy='Native bitmap bodies; six-line upper accents may move down one row; no rescaling. '
                         'Largest fitting strike, up to four CP1252 clipping slots; Mono italic horizontal clipping separate. '
                         'Mono native advance or native advance+1 chosen for fit; no wholly erased glyphs.', fonts=records)
    (args.output / 'generation-report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(args.output / 'generation-report.json')


if __name__ == '__main__':
    main()
