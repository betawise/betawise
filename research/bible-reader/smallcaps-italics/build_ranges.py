#!/usr/bin/env python3
"""Generate research-only small-cap ordinal ranges from production formatting events."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / 'applets/BibleWise'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    lower = {int(row['canonical'], 16) for row in json.loads(
        (ROOT / 'os3k/charsets/neo-smallcaps.json').read_text())['letters']}
    with tempfile.TemporaryDirectory() as directory:
        driver = Path(directory) / 'format-check'
        subprocess.run(['cc', '-O2', '-I'+str(APP), str(ROOT/'tests/biblewise/format_check.c'),
                        str(APP/'Formatting.c'), str(APP/'Decoder.c'), '-o', str(driver)], check=True)
        events = subprocess.check_output([str(driver), str(args.data)])
    cursor = chapter = ordinal = 0
    ranges = []
    counts = {}
    while cursor < len(events):
        kind = events[cursor]
        cursor += 1
        if kind == 255:
            chapter += 1
            ordinal = 0
            continue
        style, layout = events[cursor:cursor+2]
        length = int.from_bytes(events[cursor+2:cursor+4], 'big')
        cursor += 4
        text = events[cursor:cursor+length]
        cursor += length
        if kind != 0 or not style & 4:
            continue
        for character in text:
            if character not in lower:
                continue
            if style & 1:
                if ranges and ranges[-1][0] == chapter and sum(ranges[-1][1:]) == ordinal:
                    ranges[-1][2] += 1
                else:
                    ranges.append([chapter, ordinal, 1])
                counts[chapter] = counts.get(chapter, 0) + 1
            ordinal += 1
    assert chapter == 1189
    chapters = sorted(counts)
    lines = ['/* Research only: generated from the production formatting iterator. */',
             '#define ITALIC_RESEARCH_RANGE_COUNT '+str(len(ranges)),
             '#define ITALIC_RESEARCH_CHAPTER_COUNT '+str(len(chapters)),
             '#define ITALIC_RESEARCH_MAX_OFFSETS '+str(max(counts.values(), default=1)),
             '#if BIBLEWISE_ITALICS_PROTOTYPE == 2',
             'typedef struct { uint16_t chapter, first, count; } ItalicRange;',
             'static const ItalicRange g_italic_ranges[] = {']
    lines += ['    {%d, %d, %d},' % tuple(row) for row in ranges or [[0, 0, 0]]]
    lines += ['};', '#elif BIBLEWISE_ITALICS_PROTOTYPE == 1 || BIBLEWISE_ITALICS_PROTOTYPE == 4',
              'static const uint16_t g_italic_chapters[] = {'+', '.join(map(str, chapters or [0]))+'};',
              '#endif', '']
    args.output.write_text('\n'.join(lines))
    args.output.with_suffix('.json').write_text(json.dumps({
        'ranges': ranges, 'chapter_counts': counts, 'max_offsets': max(counts.values(), default=0),
        'ordinal_range_bytes': len(ranges)*6, 'chapter_presence_bytes': len(chapters)*2,
        'separate_b1_flag_bytes': len(ranges)*6, 'opaque_b3_pair_bytes': len(ranges)*6,
        'hidden_literal_pair_bytes': len(ranges)*14,
        'piggyback_region_flag_bytes': 0,
    }, indent=2)+'\n')


if __name__ == '__main__':
    main()
