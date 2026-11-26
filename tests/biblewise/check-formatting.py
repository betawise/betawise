#!/usr/bin/env python3
"""Compare every C formatting event against independent source-row expectations."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
APP = HERE.parents[1] / 'applets/BibleWise'
sys.path.insert(0, str(APP))
from convert_source import convert_text


def expected_chapters(version):
    books = json.loads((APP/'upstream/data/books.json').read_bytes())
    keys = [(b['book'], c) for b in books for c in range(1, b['numChapters']+1)]
    source = json.loads((APP/f'upstream/data/{version}/{version}.json').read_bytes())
    corpus = json.loads((APP/f'build/data/{version}/source.json').read_bytes())
    verses = [c for b in corpus for c in b['chapters']]
    result = {key: [] for key in keys}
    current = {}
    for row in source:
        _, book, chapter, verse = row['r'].split(':')
        key = book, int(chapter)
        if 'h' in row:
            if row['h'] == 1 and row['t'] == f'{book} {chapter}': continue
            title = re.sub(r'[\u0590-\u05ff]+\s*(?=[A-Za-z])', '', row['t'])
            result[key].append((1, 2, int(row['h']*2), convert_text(title)))
            continue
        for token in row['t'].split():
            flags = ''.join(re.findall(r'\*([a-z]+)', token))
            text = convert_text(re.sub(r'\*[a-z]+', '', token))
            for index, atom in enumerate(text.split()):
                if current.get(key) == int(verse): result[key].append((2, 0, 0, ' '))
                elif key in current: result[key].append((2, 0, 0, '\n'))
                current[key] = int(verse)
                style = sum(1 << i for i, flag in enumerate('ibs') if flag in flags)
                layout = sum(1 << i for i, flag in enumerate('plndcge') if flag in flags) if index == 0 else 0
                result[key].append((0, style, layout, atom))
    # Heading events appear after the preceding whitespace in the compressed
    # stream, while source rows list headings before the next verse row.
    expected = []
    for ci, key in enumerate(keys):
        events = result[key]
        for i in range(len(events)-1):
            if events[i][0] == 1:
                j = i
                while j+1 < len(events) and events[j+1][0] == 1: j += 1
                if j+1 < len(events) and events[j+1][0] == 2:
                    space = events.pop(j+1); events.insert(i, space)
        events.append((2, 0, 0, '\n'))
        expected.append(events)
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', choices=['kjv','nkjv'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    executable = args.output/'format-check'
    subprocess.run(['cc','-O2','-Wall','-Wextra','-I'+str(APP),str(HERE/'format_check.c'),
        str(APP/'Formatting.c'),str(APP/'Decoder.c'),'-o',str(executable)],check=True)
    raw = subprocess.check_output([str(executable),str(APP/'build/data'/args.version)])
    (args.output/'events.bin').write_bytes(raw)
    pos = atoms = headings = 0
    for ci, events in enumerate(expected_chapters(args.version)):
        actual = []
        while raw[pos] != 255:
            kind,style,layout = raw[pos:pos+3]; size = int.from_bytes(raw[pos+3:pos+5], 'big'); pos += 5
            text = raw[pos:pos+size].decode('cp1252'); pos += size
            actual.append((kind,style,layout,text))
            atoms += kind == 0; headings += kind == 1
        pos += 1
        assert actual == events, (ci, next(((i,a,b)for i,(a,b)in enumerate(zip(actual,events))if a!=b),None),len(actual),len(events))
    assert pos == len(raw)
    from check import check_search
    corpus=json.loads((APP/'build/data'/args.version/'source.json').read_bytes())
    cases=check_search(APP/'build/data'/args.version,args.output,[c for b in corpus for c in b['chapters']])
    report=dict(status='passed',chapters=1189,atoms=atoms,headings=headings,search_cases=cases,sha256=hashlib.sha256(raw).hexdigest())
    (args.output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report)

if __name__ == '__main__': main()
