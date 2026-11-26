#!/usr/bin/env python3
"""Validate actual direct-reader code against every gap split of verse markers."""
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
BUILD = HERE / 'build'


def main():
    source = (HERE / 'direct_boundaries.h').read_text()
    start = source.index('typedef struct {\n    const uint8_t* base;')
    stop = source.index('static unsigned ParseBoundary', start)
    preamble = """#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#include <assert.h>
#define VERSE_FONT_BEGIN 0xB1
#define VERSE_FONT_END 0xB2
#define VERSE_FONT_FACE_FLAGS 12
static unsigned g_chapter_file_bytes;
static struct { unsigned gap_start, gap_end; } g_editor;
"""
    generated = BUILD / 'direct_gap_test.c'
    generated.write_text(preamble + source[start:stop] + (HERE / 'direct_gap_cases.c').read_text())
    executable = BUILD / 'direct_gap_test'
    subprocess.run(['cc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Wno-unused-function',
        str(generated), '-o', str(executable)], check=True)
    result = subprocess.run([str(executable)], check=True, text=True, capture_output=True)
    (BUILD / 'direct-gap-results.json').write_text(json.dumps(dict(status='passed',
        output=result.stdout.strip()), indent=2)+'\n')
    print(result.stdout, end='')


if __name__ == '__main__':
    main()
