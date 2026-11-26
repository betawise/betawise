#!/usr/bin/env python3
"""Account for adoption ROM growth using isolated, identically linked stages."""
import argparse
import json
from pathlib import Path
import struct
import subprocess

from prepare import prepare

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
APP = ROOT / 'applets/BibleWise'
BUILD = HERE / 'build'


def section(source, begin, end):
    return source[source.index(begin):source.index(end, source.index(begin))]


def gap_header(header):
    header = header.replace('unsigned position, available;',
                            'unsigned position, available;\n    uint8_t seam[15];')
    old = (HERE / 'direct_boundaries.h').read_text()
    fill = section(old, 'static void BoundaryFill(', 'static void BoundaryAdvance(')
    fill = fill[fill.index('#else') + 5:fill.rindex('#endif')] + '}\n\n'
    begin = header.index('static void BoundaryFill(')
    end = header.index('static void BoundaryAdvance(', begin)
    header = header[:begin] + 'static void BoundaryFill(BoundaryStream* stream) {' + fill + header[end:]
    begin = header.index('    if(g_editor.gap_start !=')
    end = header.index('    const uint8_t* base =', begin)
    return header[:begin] + header[end:]


def without_eof_move(source):
    begin = source.index('static bool MoveChapterGapToEnd(void)')
    end = source.index('static void OpenChapter(', begin)
    return (source[:begin] + source[end:]).replace(' || !MoveChapterGapToEnd()', '')


def retained_file(source, old):
    source = source.replace('static bool g_resume_view;\n', '')
    source = source.replace(', const ReadingView* reading_view', '')
    source = source.replace(', READER_NO_WORD, NULL)', ', READER_NO_WORD)')
    source = source.replace(', g_match.word, NULL)', ', g_match.word)')
    begin = source.index('static void OpenChapter(unsigned chapter, unsigned verse, unsigned target_word) {')
    end = source.index('/* Bypass the optional Betawise console font:', begin)
    legacy = section(old, 'static void OpenChapter(unsigned chapter, unsigned verse, unsigned target_word) {',
                     '/* Bypass the optional Betawise console font:')
    source = source[:begin] + legacy + source[end:]
    begin = source.index('void ProcessMessage(')
    return source[:begin] + old[old.index('void ProcessMessage('):]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current', action='store_true', help='Measure the current rather than original adopted boundary code')
    args = parser.parse_args()
    old = (HERE / 'reference/pre-binary-lifecycle.c').read_text()
    current = (APP / 'BibleWise.c').read_text()
    # Freeze the original adoption boundary code; later simplifications are separate.
    contiguous = ((APP / 'ChapterPositions.h') if args.current else (HERE / 'reference/ChapterPositions.h')).read_text()
    gap = gap_header(contiguous)
    retained = retained_file(without_eof_move(current), old)
    linear = gap.replace('    NumberedRecord anchor = FindEarlierRecord(target, by_position, base);\n'
                         '    if(by_position) anchor = FindEarlierRecord(anchor.number, false, base);',
                         '    NumberedRecord anchor = {0, 1};')
    stages = [
        ('tables', old, contiguous),
        ('linear', retained, linear),
        ('binary', retained, gap),
        ('delete-recreate', without_eof_move(current), gap),
        ('contiguous-eof', current, contiguous),
    ]
    results = []
    for name, source, header in stages:
        app = prepare('baseline', '-size-audit-' + name)
        source = source.replace('"../../tests/mame/asneo/BibleWiseProbe.h"',
                                '"' + str(ROOT / 'tests/mame/asneo/BibleWiseProbe.h') + '"')
        (app / 'BibleWise.c').write_text(source)
        (app / 'ChapterPositions.h').write_text(header)
        with (app / 'size-audit.log').open('w') as log:
            subprocess.run(['make', '-s', '-C', str(app), 'VERSION=NKJV'],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        image = (app / 'build/NKJV/BibleWise-NKJV.OS3KApp').read_bytes()
        rom, a5 = struct.unpack_from('>II', image, 4)
        row = dict(stage=name, rom=rom, a5=a5,
                   rom_delta=rom-results[-1]['rom'] if results else 0,
                   a5_delta=a5-results[-1]['a5'] if results else 0)
        results.append(row)
        print(row, flush=True)
    if not args.current:
        assert results[-1]['rom'] - results[0]['rom'] == 1268
    assert results[-1]['a5'] - results[0]['a5'] == -1018
    (BUILD / ('adoption-size-current.json' if args.current else 'adoption-size-audit.json')).write_text(json.dumps(results, indent=2) + '\n')


if __name__ == '__main__':
    main()
