#!/usr/bin/env python3
"""Target string calls must use firmware helpers even with host fortify enabled."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CROSS = os.environ.get('CROSS_COMPILE', 'm68k-linux-gnu-')
SOURCE = '''#include <string.h>
char destination[64];
void copy_string(const char* source) { strcpy(destination, source); }
void copy_bytes(const void* source, size_t length) { memcpy(destination, source, length); }
'''


def undefined_symbols(path):
    output = subprocess.check_output([CROSS + 'nm', '-u', str(path)], text=True)
    return {line.split()[-1] for line in output.splitlines() if line.split()}


def main():
    with tempfile.TemporaryDirectory(prefix='os3k-fortify-') as temporary:
        root = Path(temporary)
        (root / 'probe.c').write_text(SOURCE)
        # Negative control proves this compiler/sysroot actually emits the
        # missing fortified symbols; otherwise the regression would be vacuous.
        negative = root / 'fortified.o'
        subprocess.run([CROSS + 'gcc', '-m68000', '-Os', '-D_FORTIFY_SOURCE=2',
            '-c', str(root / 'probe.c'), '-o', str(negative)], check=True)
        assert {'__memcpy_chk', '__strcpy_chk'} <= undefined_symbols(negative)
        (root / 'Makefile').write_text('OBJ = build/probe.o\nOS3K_HEADERS =\ninclude '
            + str(ROOT / 'Makefile.common') + '\nTOP := $(TOP)\n')
        for level in (2, 3):
            for fixups in (0, 1):
                subprocess.run(['make', '-s', '-B', '-C', str(root), 'build/probe.o',
                    'CROSS_COMPILE=' + CROSS, 'CPPFLAGS=-D_FORTIFY_SOURCE=' + str(level),
                    'OS3K_FIXUPS=' + str(fixups)], check=True)
                symbols = undefined_symbols(root / 'build/probe.o')
                assert not any(name.endswith('_chk') for name in symbols), (level, fixups, symbols)
                assert {'memcpy', 'strcpy'} <= symbols, (level, fixups, symbols)
    print('PASS firmware string calls under FORTIFY_SOURCE=2/3, with fixups on/off')


if __name__ == '__main__':
    main()
