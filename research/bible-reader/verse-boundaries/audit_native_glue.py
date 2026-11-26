#!/usr/bin/env python3
"""Measure direct chapter reads in isolated native-reader glue prototypes."""
import json
import re
from pathlib import Path
import struct
import subprocess
from prepare import prepare

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
APP = ROOT / 'applets/BibleWise'


def direct_words(source, name, next_name):
    start = source.index('static ' + ('int ' if name == 'FindWordOffset' else 'unsigned ') + name + '(')
    stop = source.index(next_name, start)
    function = source[start:stop]
    first = function.index('    while(position < end) {')
    body = function.index('            int character = NativeTextCharacter(', first)
    last = function.index('        }\n        position += bytes_read;\n    }', body)
    tail = last + len('        }\n        position += bytes_read;\n    }')
    prefix = function[:first].replace('    uint8_t buffer[READER_IO_BYTES];\n', '').replace('    int32_t saved_position = FileTell(READER_FILE);\n', '')
    loop = function[body:last].replace('buffer[index]', 'bytes[position]').replace('position + index', 'position')
    loop = loop.replace('                    FileSeek(READER_FILE, saved_position, FILE_SEEK_START);\n', '')
    loop = '\n'.join(line[4:] if line.startswith('        ') else line for line in loop.split('\n'))
    function = prefix + '    const uint8_t* bytes = FileBindState(READER_FILE, NULL, NULL, NULL, NULL);\n    if(!bytes) return 0;\n    for(; position < end; ++position) {\n' + loop + '    }' + function[tail:]
    function = function.replace('    FileSeek(READER_FILE, saved_position, FILE_SEEK_START);\n', '')
    return source[:start] + function + source[stop:]


def direct_copy(source):
    start = source.index('static void CopySelectedVerses(')
    stop = source.index('static bool AcceptInput(', start)
    function = source[start:stop]
    first = function.index('        unsigned raw = position +')
    last = function.index('        for(index =', first)
    function = function[:first] + '''        if(count > sizeof(input)) count = sizeof(input);
        const uint8_t* bytes = FileBindState(READER_FILE, NULL, NULL, NULL, NULL);
        if(!bytes) goto failed;
        int read = count;
        /* Clipboard growth may relocate the file. Borrow afresh for each block,
         * then consume the local copy before the next clipboard write. */
        memcpy(input, bytes + position, read);
''' + function[last:]
    function = function.replace('    int32_t saved_position = FileTell(READER_FILE);\n', '')
    function = function.replace('    FileSeek(READER_FILE, saved_position, FILE_SEEK_START);\n', '')
    return source[:start] + function + source[stop:]


def direct_regions(source):
    first = source.index('static bool UpdateTextRegions(')
    last = source.index('/* After native wrapping,', first)
    function = source[first:last]
    body_start = function.index('            unsigned character = buffer[index];')
    body_end = function.index('        }\n        /* Each block stops', body_start)
    body = function[body_start:body_end].replace('buffer[index]', 'bytes[position]')
    body = '\n'.join(line[4:] if line.startswith('        ') else line for line in body.split('\n'))
    body = body.replace('                changed = true;\n', '').replace('        changed = true;\n', '')
    replacement = ('static bool UpdateTextRegions(unsigned operation, bool visible) {\n'
                   '    unsigned token = 0, flags = 0, begin = 0;\n'
                   '    uint8_t* bytes = FileBindState(READER_FILE, NULL, NULL, NULL, NULL);\n'
                   '    if(!bytes) return false;\n'
                   '    for(unsigned position = 0; position < g_chapter_file_bytes; ++position) {\n'
                   + body + '    }\n    return true;\n}\n\n')
    return source[:first] + replacement + source[last:]


def main():
    original = (HERE / 'reference/pre-native-glue.c').read_text()
    words = direct_words(original, 'FindWordOffset', 'static int SeekToWord(')
    words = direct_words(words, 'FindWordAtOffset', '#define READER_SEARCH_INVALID')
    variants = [('current', original), ('direct-words', words), ('direct-words-copy', direct_copy(words)), ('direct-toggles', direct_regions(direct_copy(words))), ('narrow-book-names', direct_regions(direct_copy(words)))]
    results = []
    for name, source in variants:
        app = prepare('baseline', '-glue-' + name)
        source = source.replace('"../../tests/mame/asneo/BibleWiseProbe.h"', '"' + str(ROOT / 'tests/mame/asneo/BibleWiseProbe.h') + '"')
        (app / 'BibleWise.c').write_text(source)
        # Never modify the shared production resources through prepare's symlink.
        if (app / 'build/data').is_symlink():
            (app / 'build/data').unlink()
        data_dir = app / 'build/data/nkjv'
        data_dir.mkdir(parents=True, exist_ok=True)
        for item in (APP / 'build/data/nkjv').iterdir():
            target = data_dir / item.name
            if item.name == 'Navigation.h':
                width = 16 if name == 'narrow-book-names' else 24
                target.write_text(re.sub(r'char name\[\d+\];', f'char name[{width}];', item.read_text()))
            elif not target.exists():
                target.symlink_to(item)
        with (app / 'glue-build.log').open('w') as log:
            subprocess.run(['make', '-s', '-C', str(app), 'VERSION=NKJV'], stdout=log, stderr=subprocess.STDOUT, check=True)
        data = (app / 'build/NKJV/BibleWise-NKJV.OS3KApp').read_bytes()
        rom, a5 = struct.unpack_from('>II', data, 4)
        row = dict(variant=name, rom=rom, a5=a5, saved=results[0]['rom']-rom if results else 0)
        results.append(row)
        print(row, flush=True)
    (HERE / 'build/native-glue-sizes.json').write_text(json.dumps(results, indent=2)+'\n')


if __name__ == '__main__':
    main()
