#!/usr/bin/env python3
"""Check prototype literal markers against the actual production C writer."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from compare import APP, verse_markup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = (APP / 'BibleWise.c').read_text()
    start = source.index('static int BufferVerseNumber(')
    end = source.index('static unsigned VerseTextOffset(', start)
    names = ['VERSE_MARKER_BYTES', 'VERSE_DIGIT_CHARACTER', 'VERSE_FONT_BEGIN',
        'VERSE_FONT_END', 'VERSE_FONT_FACE_FLAGS', 'READER_REGION_PROTECTED', 'READER_REGION_HIDDEN']
    constants = '\n'.join(re.search(r'^#define ' + name + r' .*$', source, re.M)[0] for name in names)
    program = '#include <stdint.h>\n#include <stdio.h>\n' + constants + '\n'
    program += 'static struct { unsigned verse_numbers; } g_settings = {1};\n'
    program += source[start:end]
    program += '''int main(void) {
        for(unsigned verse = 1; verse <= 176; ++verse) {
            uint8_t bytes[32]; unsigned count = 0;
            if(!BufferVerseNumber(verse, bytes, &count)) return 1;
            putchar(count); fwrite(bytes, 1, count, stdout);
        }
        return 0;
    }\n'''
    path = args.output / 'native-marker-check.c'
    path.write_text(program)
    executable = path.with_suffix('')
    subprocess.run(['cc', '-O2', '-Wall', '-Wextra', str(path), '-o', str(executable)], check=True)
    raw = subprocess.check_output([str(executable)])
    (args.output / 'native-markers.bin').write_bytes(raw)
    position = 0
    for verse in range(1, 177):
        count = raw[position]
        position += 1
        assert raw[position:position + count] == verse_markup(verse)
        position += count
    assert position == len(raw)
    report = dict(status='passed', production_markers_verified=176,
        source_writer_sha256=hashlib.sha256(source[start:end].encode()).hexdigest(),
        markers_sha256=hashlib.sha256(raw).hexdigest())
    (args.output / 'native-marker-check.json').write_text(json.dumps(report, indent=2) + '\n')
    print(report)


if __name__ == '__main__':
    main()
