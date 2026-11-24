#!/usr/bin/env python3
"""Build and start the interactive demo in a new, disposable MAME session."""
import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ROOT = REPO.parent
SYSTEM_SHA = '32fe55bb50c1b58326bd303f14973b8402ddf8bf6662b210e4d5e9f931c7e6c0'


def prepare(session, firmware, emulator):
    for directory in ('roms/asneo', 'cfg', 'nvram/asneo', 'snap'):
        (session / directory).mkdir(parents=True, exist_ok=True)
    small = (firmware / 'smallos3kneorom.os3kos').read_bytes()
    system = (firmware / 'os3kneorom.os3kos').read_bytes()
    if hashlib.sha256(system).hexdigest() != SYSTEM_SHA:
        raise ValueError('This demo requires the characterized Neo 3.21 image')
    flash = bytearray(b'\xff' * 0x400000)
    flash[:len(small)] = small
    source = 0
    for offset in range(0x50, 0x70, 8):
        address, size = struct.unpack_from('>II', system, offset)
        if not address and not size:
            break
        size = (size + 1023) & ~1023
        dest = address - 0x400000
        if not (0 <= dest <= len(flash)-size and source+size <= len(system)):
            raise ValueError('Invalid system package segment')
        flash[dest:dest+size] = system[source:source+size]
        source += size
    images = [firmware / 'alphawordplus.os3kapp', HERE / 'FontDialogDemo.OS3KApp']
    offset = 0x70000
    for image in images:
        data = image.read_bytes()
        if (data[:4] != bytes.fromhex('c0ffeead')
                or int.from_bytes(data[4:8], 'big') != len(data)
                or offset+len(data) > len(flash)
                or any(b != 255 for b in flash[offset:offset+len(data)])):
            raise ValueError(f'Invalid applet placement: {image}')
        flash[offset:offset+len(data)] = data
        offset += len(data)
    (session / 'nvram/asneo/flashnv').write_bytes(flash)
    for name in ('smallos3kneorom.os3kos', 'os3kneorom.os3kos'):
        shutil.copyfile(firmware/name, session/'roms/asneo'/name)
    (session/'cfg/asneo.cfg').write_text(
        '<mameconfig version="10"><system name="asneo"><input>'
        '<port tag=":NOR_PROFILE" type="CONFIG" mask="1" defvalue="0" value="1" />'
        '</input></system></mameconfig>\n')
    paths = images + [firmware/'smallos3kneorom.os3kos', firmware/'os3kneorom.os3kos', emulator]
    (session/'manifest.json').write_text(json.dumps([
        {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in paths], indent=2)+'\n')
    return [str(emulator), 'asneo', '-rompath', str(session/'roms'),
            '-cfg_directory', str(session/'cfg'), '-nvram_directory', str(session/'nvram'),
            '-snapshot_directory', str(session/'snap'), '-window', '-skip_gameinfo']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mame', type=Path, default=ROOT/'mame/neodiag')
    parser.add_argument('--firmware', type=Path, default=ROOT/'Ghidra/Alphasmart Neo/SmartApplets')
    parser.add_argument('--prepare-only', action='store_true', help='print the MAME command without opening a window')
    parser.add_argument('--session', type=Path, help='new directory; refuses an existing path')
    args = parser.parse_args()
    subprocess.run(['make', '-C', str(REPO/'os3k')], check=True)
    subprocess.run(['make', '-C', str(HERE)], check=True)
    if args.session:
        session = args.session.resolve()
        session.mkdir(parents=True, exist_ok=False)
    else:
        session = Path(tempfile.mkdtemp(prefix='neo-font-dialogs-'))
    command = prepare(session, args.firmware.resolve(), args.mame.resolve())
    import shlex
    print(f'Disposable session: {session}', flush=True)
    print(shlex.join(command), flush=True)
    print('Boot prompts: Y, then Enter. F9: SmartApplets; choose Font Dialog Demo.', flush=True)
    if not args.prepare_only:
        subprocess.run(command, cwd=session, check=True)


if __name__ == '__main__':
    main()
