#!/usr/bin/env python3
"""Launch the selected BibleWise release interactively in disposable MAME storage."""

import argparse
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from check import ROOT, prepare_session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true', help='Print a plain MAME command without starting it')
    parser.add_argument("--version", choices=["KJV", "NKJV", "ESV", "NIV", "NASB", "CSB"], default="KJV")
    parser.add_argument('--scale', type=int, choices=range(1,9), default=4)
    args = parser.parse_args()
    app = ROOT / 'betawise/applets/BibleWise'
    subprocess.run(['make', '-C', str(app), f'VERSION={args.version}'], check=True)
    font_directory = ROOT / 'betawise/fonts'
    subprocess.run(['make','-C',str(font_directory),'readers'],check=True,stdout=subprocess.DEVNULL)
    firmware = ROOT / 'Ghidra/Alphasmart Neo/SmartApplets'
    emulator = ROOT / 'mame/neodiag'
    session = Path(tempfile.mkdtemp(prefix='neo-bible-'+args.version.lower()+'-'))
    prepare_session(session, firmware, 'extra', emulator)
    flash = bytearray((session / 'nvram/asneo/flashnv').read_bytes())
    flash[0x70000:] = b'\xff' * (len(flash) - 0x70000)
    offset = 0x70000
    build_name = args.version
    images = [firmware / 'alphawordplus.os3kapp', app / 'build' / build_name / ('BibleWise'+('' if args.version=='KJV' else '-'+args.version)+'.OS3KApp')]
    images += sorted(firmware.glob('neofont*.os3kapp'))
    images += [path for path in sorted((font_directory/'build').glob('BetaWise*/*.OS3KApp'))
        if 0xAFF0 <= int.from_bytes(path.read_bytes()[20:22],'big') <= 0xAFFF]
    (session / 'artifacts').mkdir()
    for image in images:
        contents = image.read_bytes()
        if offset + len(contents) > len(flash):
            raise ValueError('Applet images exceed the disposable flash capacity')
        flash[offset:offset + len(contents)] = contents
        offset += len(contents)
        shutil.copyfile(image, session / 'artifacts' / image.name)
    (session / 'nvram/asneo/flashnv').write_bytes(flash)
    command = [str(emulator), 'asneo', '-rompath', str(session / 'roms'),
        '-cfg_directory', str(session / 'cfg'), '-nvram_directory', str(session / 'nvram'),
        '-window', '-resolution', f'{264*args.scale}x{65*args.scale}',
        '-intscalex', str(args.scale), '-intscaley', str(args.scale),
        '-nounevenstretch', '-nofilter', '-skip_gameinfo']
    print(f'Disposable session: {session}', flush=True)
    print(shlex.join(command), flush=True)
    if not args.prepare_only:
        subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
