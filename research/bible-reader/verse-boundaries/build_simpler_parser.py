#!/usr/bin/env python3
"""Measure parser control-flow and owned-marker simplifications independently."""
import json
from pathlib import Path
import struct
import subprocess

from prepare import prepare

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
APP = ROOT / 'applets/BibleWise'


def main():
    original = (HERE / 'reference/ChapterPositions.h').read_text()
    first = original.index('static unsigned ParseBoundary(')
    last = original.index('/* Seek existing numbered records;', first)
    common_exit = original[:first] + (HERE / 'simpler_parser.h').read_text() + '\n' + original[last:]
    compact_marker = common_exit
    first = compact_marker.index('    if(index == 6 ||')
    last = compact_marker.index('    *length =', first)
    compact_marker = compact_marker[:first] + '    if(index == 6) return 0;\n' + compact_marker[last:]
    results = []
    for name, header in [('original-parser', original), ('common-exit-parser', common_exit),
                         ('simpler-parser', compact_marker)]:
        app = prepare('baseline', '-' + name)
        source = (APP / 'BibleWise.c').read_text().replace('"../../tests/mame/asneo/BibleWiseProbe.h"',
                            '"' + str(ROOT / 'tests/mame/asneo/BibleWiseProbe.h') + '"')
        (app / 'BibleWise.c').write_text(source)
        (app / 'ChapterPositions.h').write_text(header)
        with (app / 'build.log').open('w') as log:
            subprocess.run(['make', '-s', '-C', str(app), 'VERSION=NKJV'],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        data = (app / 'build/NKJV/BibleWise-NKJV.OS3KApp').read_bytes()
        rom, a5 = struct.unpack_from('>II', data, 4)
        row = dict(variant=name, rom=rom, a5=a5, rom_delta=rom-results[0]['rom'] if results else 0)
        results.append(row)
        print(row, flush=True)
    (HERE / 'build/simpler-parser-sizes.json').write_text(json.dumps(results, indent=2) + '\n')


if __name__ == '__main__':
    main()
