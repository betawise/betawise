#!/usr/bin/env python3
"""Build an offline picker comparing editable Neo BDFs with hinted outlines.

Candidate generation never edits a BDF. Exported choices retain exact original
cells and source provenance for later, explicit application/review.
"""
import argparse
import base64
from functools import lru_cache
import json
from pathlib import Path
import shlex
import subprocess

from PIL import Image
import review
from research_paths import BUILD

HERE = Path(__file__).resolve().parent
STYLES = ['Regular', 'Bold', 'Italic', 'BoldItalic']
GROUPS = ['CGOQ', 'cg oq', 'aceos', 'mnuw', 'Il1', 'O0', 'bdpq', 'ÀÁÂÃÄÅ', 'CÇcç']


def unpack(packet, height):
    image = Image.new('1', (packet['width'], height))
    data = base64.b64decode(packet['bits'], validate=True)
    stride = (image.width + 7) // 8
    if len(data) != stride * height:
        raise ValueError('invalid packed cell')
    for y in range(height):
        for x in range(image.width):
            image.putpixel((x, y), bool(data[y*stride+x//8] & (0x80 >> (x%8))))
    return image


def topology(image):
    """Eight-connected ink, four-connected background; padding exposes outside."""
    ink = {(x, y) for y in range(image.height) for x in range(image.width) if image.getpixel((x,y))}
    def components(points, directions):
        points = set(points)
        count = 0
        while points:
            stack = [points.pop()]
            count += 1
            while stack:
                x, y = stack.pop()
                for dx, dy in directions:
                    neighbor = x+dx, y+dy
                    if neighbor in points:
                        points.remove(neighbor)
                        stack.append(neighbor)
        return count
    around = [(x,y) for x in [-1,0,1] for y in [-1,0,1] if x or y]
    background = {(x,y) for y in range(-1,image.height+1) for x in range(-1,image.width+1)} - ink
    return dict(ink=len(ink), parts=components(ink, around),
                holes=components(background, [(0,1),(1,0),(0,-1),(-1,0)])-1)


def fit_glyph(glyph, width, height, baseline, shift=0):
    """Keep every raster pixel or reject; never crop, resize or move baseline."""
    points = {(glyph['left']+shift+x, baseline-glyph['top']+y)
              for y,row in enumerate(glyph['rows']) for x,value in enumerate(row) if value == '1'}
    if any(x < 0 or x >= width or y < 0 or y >= height for x,y in points):
        return None
    image = Image.new('1', (width,height))
    for point in points:
        image.putpixel(point, 1)
    return image


def compile_rasterizer(build):
    destination = build / 'vector_raster'
    build.mkdir(parents=True, exist_ok=True)
    source = HERE / 'vector_raster.c'
    if not destination.exists() or source.stat().st_mtime > destination.stat().st_mtime:
        flags = subprocess.check_output(['pkg-config', '--cflags', '--libs', 'freetype2'], text=True)
        subprocess.run(['cc', '-std=c99', '-O2', '-Wall', '-Wextra', str(source),
                        '-o', str(destination), *shlex.split(flags)], check=True)
    return destination


class Rasterizer:
    def __init__(self, executable):
        self.executable = executable
        self.version = None

    @lru_cache(maxsize=None)
    def render(self, path, ppem, hint, phase, codes):
        result = subprocess.run([str(self.executable), str(path), str(ppem), hint, str(phase)],
            input=' '.join(map(str,codes)), text=True, capture_output=True, check=True)
        data = json.loads(result.stdout)
        self.version = data['version']
        return {int(code):glyph for code,glyph in data['glyphs'].items()}


def ink_height(glyph):
    if glyph is None:
        return 0
    ys = [y for y,row in enumerate(glyph['rows']) if '1' in row]
    return max(ys)-min(ys)+1 if ys else 0


def cell_height(image):
    bounds = image.getbbox()
    return bounds[3]-bounds[1] if bounds else 0


def build_data(config, rasterizer, flags=None, families=None):
    data = review.build_data(include_reference=False)
    if families:
        data['faces'] = [face for face in data['faces'] if face['family'].removeprefix('BetaWise ') in families]
    codes = tuple(sorted({ord(c['char']) for c in data['characters'] if c}))
    slots = {slot:ord(info['char']) for slot,info in enumerate(data['characters']) if info}
    for face in data['faces']:
        family = face['family'].removeprefix('BetaWise ')
        height, baseline = face['height'], face['baseline']
        cells = [unpack(g,height) if g else None for g in face['glyphs']]
        target_cap = cell_height(cells[65])
        target_x = cell_height(cells[120])
        face['targetCap'] = target_cap
        face['targetX'] = target_x
        face['sources'] = []
        face['skippedSources'] = []
        pools = [[] for _ in range(256)]
        stats = [dict(missingSources=0, overflow=0, unchanged=0) for _ in range(256)]
        for entry in config[family]:
            filename = entry['files'][STYLES.index(face['style'])]
            if filename is None:
                face['skippedSources'].append(dict(name=entry['name'],reason=entry.get('availability','This style is not installed.')))
                continue
            path = Path(entry['directory']).expanduser() / filename
            if not path.is_file():
                if entry.get('optional'):
                    face['skippedSources'].append(dict(name=entry['name'],reason='Not installed at '+str(path)))
                    continue
                raise FileNotFoundError(f'Outline source missing: {path}; adjust --sources configuration')
            source_index = len(face['sources'])
            source = {key:value for key,value in entry.items() if key not in ('files','directory','optional')}
            source['path'] = str(path)
            face['sources'].append(source)
            for hint in ['native', 'auto']:
                trials = []
                for ppem in range(max(4,target_cap), min(64, target_cap*2+6)):
                    calibration = rasterizer.render(path,ppem,hint,0,(65,72,120))
                    cap, x = ink_height(calibration[65]), ink_height(calibration[120])
                    if not cap or not x:
                        raise ValueError(f'{path} lacks A/x calibration glyphs')
                    error = 2*abs(cap-target_cap) + abs(x-target_x)
                    trials.append((error, ppem, cap, x))
                for error,ppem,cap,xheight in sorted(trials)[:3]:
                    for phase in [0,32]:
                        rendered = rasterizer.render(path,ppem,hint,phase,codes)
                        cap, xheight = ink_height(rendered[65]), ink_height(rendered[120])
                        error = 2*abs(cap-target_cap) + abs(xheight-target_x)
                        for slot,code in slots.items():
                            glyph = rendered[code]
                            if glyph is None:
                                if phase == 0 and ppem == sorted(trials)[0][1]:
                                    stats[slot]['missingSources'] += 1
                                continue
                            width = (face['glyphs'][slot] or face['glyphs'][63])['width']
                            current = cells[slot]
                            old_bounds = current.getbbox() if current else None
                            for shift in [0,-1,1]:
                                image = fit_glyph(glyph,width,height,baseline,shift)
                                if image is None:
                                    stats[slot]['overflow'] += 1
                                    continue
                                if current is not None and image.tobytes() == current.tobytes():
                                    stats[slot]['unchanged'] += 1
                                    continue
                                bounds = image.getbbox()
                                ink_width = bounds[2]-bounds[0] if bounds else 0
                                old_width = old_bounds[2]-old_bounds[0] if old_bounds else 0
                                packet = review.pack(image)
                                score = error*10 + abs(ink_width-old_width) + abs(shift)*0.2 + phase/640
                                candidate = dict(id=f'{source_index}:{ppem}:{hint}:{phase}:{shift}',
                                    source=source_index,ppem=ppem,hint=hint,phase=phase,shift=shift,
                                    cap=cap,xheight=xheight,sourceAdvance=glyph['advance64']/64,
                                    inkWidth=ink_width,widthDelta=ink_width-old_width,score=score,**packet)
                                pools[slot].append(candidate)
        face['alternatives'] = []
        face['candidateStats'] = stats
        for slot,pool in enumerate(pools):
            seen = set()
            alternatives = []
            source_counts = {}
            for candidate in sorted(pool,key=lambda c:(c['score'],c['ppem'],c['id'])):
                image = unpack(candidate,height)
                bounds = image.getbbox()
                shape = (image.crop(bounds).size,image.crop(bounds).tobytes()) if bounds else ((),b'')
                shape = (candidate['source'],shape)
                if shape in seen or source_counts.get(candidate['source'],0) >= 6:
                    continue
                seen.add(shape)
                source_counts[candidate['source']] = source_counts.get(candidate['source'],0) + 1
                candidate = dict(candidate)
                del candidate['score']
                candidate['checks'] = topology(unpack(candidate,height))
                alternatives.append(candidate)
                if len(source_counts) == len(face['sources']) and all(n >= 6 for n in source_counts.values()):
                    break
            face['alternatives'].append(alternatives)
        face['originalChecks'] = [topology(cell) if cell else None for cell in cells]
        print(f"{face['family']} {face['sizeLabel']} {face['style']}: "
              f"{sum(bool(c) for c in face['alternatives'])} slots with fitting alternatives", flush=True)
    data['format'] = 'betawise-vector-review-data-v1'
    data['groups'] = GROUPS
    data['freetype'] = rasterizer.version
    data['flags'] = []
    if flags:
        imported = json.loads(flags.read_text())
        if imported.get('format') != 'betawise-font-fixes-v1':
            raise ValueError('expected glyph-review JSON')
        known = {face['id'] for face in data['faces']}
        data['flags'] = [dict(font=g['font'],slot=g['slot']) for g in imported['glyphs']
                         if g['font'] in known and isinstance(g['slot'],int) and 0 <= g['slot'] < 256]
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources',type=Path,default=HERE/'vector-sources.json')
    parser.add_argument('--flags',type=Path,help='seed flagged glyphs from the existing review export')
    parser.add_argument('--family',action='append',choices=review.FAMILIES,help='optional generation subset')
    parser.add_argument('--output',type=Path,default=BUILD/'vector-review.html')
    args = parser.parse_args()
    executable = compile_rasterizer(HERE/'build/vector-review')
    data = build_data(json.loads(args.sources.read_text()), Rasterizer(executable), args.flags, args.family)
    serialized = json.dumps(data,separators=(',',':'),ensure_ascii=True).replace('<',r'\u003c')
    template = (HERE/'vector-review-template.html').read_text()
    page = template.replace('/*VECTOR_DATA*/null',serialized).replace('/*VECTOR_JS*/',(HERE/'vector-review.js').read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page)
    print(f'{args.output}: {len(data["faces"])} faces, '
          f'{sum(len(c) for f in data["faces"] for c in f["alternatives"]):,} distinct fitting candidates')


if __name__ == '__main__':
    main()
