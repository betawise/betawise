#!/usr/bin/env python3
"""Rebuild the archived sidecar app against frozen sources and pinned Bible data."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REFERENCE = HERE / 'sidecar-reference'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((REFERENCE / 'archive.json').read_text())
    for name, digest in manifest['sources'].items():
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == digest, name
    for version in ('kjv', 'nkjv'):
        data = REFERENCE / 'build/data' / version
        if not (data / 'container.bin').exists():
            subprocess.run(['python3', str(REFERENCE / 'build_data.py'), '--version', version,
                '--output', str(data)], check=True)
    app = HERE / 'build/sidecar/app'
    app.mkdir(parents=True, exist_ok=True)
    for name in manifest['sources']:
        shutil.copy2(REFERENCE / name, app / name)
    for name, target in [('upstream', REFERENCE / 'upstream'), ('build/data', REFERENCE / 'build/data')]:
        path = app / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.symlink_to(target, target_is_directory=True)
    make = (app / 'Makefile').read_text().replace('include ../../Makefile.common',
        'include ' + str(ROOT / 'Makefile.common'))
    make = make.replace('../../research/fonts/superscript-3x5.json',
        str(ROOT / 'research/fonts/superscript-3x5.json'))
    make = re.sub(r'\$\(DATA_FILES\) &:.*?\n\tpython3 build_data.py[^\n]*\n',
        '# Immutable sidecar baseline data.\n', make, flags=re.S)
    (app / 'Makefile').write_text(make)
    source = (app / 'BibleWise.c').read_text().replace('"../../tests/mame/asneo/BibleWiseProbe.h"',
        '"' + str(ROOT / 'tests/mame/asneo/BibleWiseProbe.h') + '"')
    (app / 'BibleWise.c').write_text(source)
    if args.build:
        for version in ('KJV', 'NKJV'):
            subprocess.run(['make', '-s', '-C', str(app), 'VERSION=' + version], check=True)
    print(app)


if __name__ == '__main__':
    main()
