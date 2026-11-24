#!/usr/bin/env python3
"""Exercise a synthetic file arena and private floor reservation; disposable RAM only."""
from pathlib import Path
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WS = ROOT.parent
out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=False)
roms = json.loads((ROOT / 'research/abi-audit/rom-inventory.json').read_text())
manifest = {'purpose': 'bounded native startup clear/repack and mask-register probe', 'runs': []}
for r in roms:
    name = r['name']
    if name not in ('as3000', 'neo_3_01', 'neo_3_21'):
        continue
    work = out / name
    work.mkdir()
    system = (WS / r['path']).read_bytes()
    assert hashlib.sha256(system).hexdigest() == r['sha256']
    neo = name != 'as3000'
    driver = 'asneo' if neo else 'asma3k'
    directory = work / 'roms' / driver
    directory.mkdir(parents=True)
    nvram = work / 'nvram' / driver
    nvram.mkdir(parents=True)
    cfg = work / 'cfg'
    cfg.mkdir()
    if neo:
        old = name == 'neo_3_01'
        firmware = WS / ('Ghidra/Alphasmart 3000/SmartApplets' if old else 'Ghidra/Alphasmart Neo/SmartApplets')
        small = (firmware / ('SMALLOS3KNeoROM.OS3KOS' if old else 'smallos3kneorom.os3kos')).read_bytes()
        flash = bytearray(b'\xff' * 0x400000)
        flash[:len(small)] = small
        if old:
            flash[0x1c0000:0x200000] = system[:0x40000]
            flash[0x6000:0x6014] = system[0x40000:0x40014]
        else:
            source = 0
            for off in range(0x50, 0x70, 8):
                address = int.from_bytes(system[off:off+4], 'big')
                size = int.from_bytes(system[off+4:off+8], 'big')
                if not address and not size:
                    break
                size = (size + 1023) & ~1023
                flash[address-0x400000:address-0x400000+size] = system[source:source+size]
                source += size
        (nvram / 'flashnv').write_bytes(flash)
        loader = WS / 'Ghidra/Alphasmart Neo/SmartApplets'
        for filename in ('smallos3kneorom.os3kos', 'os3kneorom.os3kos'):
            shutil.copyfile(loader / filename, directory / filename)
        (cfg / 'asneo.cfg').write_text('<mameconfig version="10"><system name="asneo"><input><port tag=":NOR_PROFILE" type="CONFIG" mask="1" defvalue="0" value="1" /></input></system></mameconfig>')
        image, a5, stack, stub, data, ram_size = 0x60000, 0x70000, 0x74000, 0x75000, 0x76000, 0x80000
        executable = WS / 'mame/neodiag'
    else:
        small = (WS / 'mame/roms/asma3k/smallos3krom.os3kos').read_bytes()
        flash = bytearray(b'\xff' * 0x100000)
        flash[:len(small)] = small
        flash[0xc0000:] = system[:0x40000]
        flash[0x4000:0x7bf0] = system[0x40000:]
        if sys.byteorder == 'little':
            flash[0::2], flash[1::2] = flash[1::2], flash[0::2]
        (nvram / 'flash').write_bytes(flash)
        (directory / 'smallos3krom.os3kos').write_bytes(small)
        (directory / 'os3krom.os3kos').write_bytes(system)
        image, a5, stack, stub, data, ram_size = 0x20000, 0x30000, 0x34000, 0x35000, 0x36000, 0x40000
        executable = WS / 'mame/mame'
    layout = {
        'as3000': (0x1042,0x4558,0x354e,0x3446,0x3442,0x344a,0xd82,0xe02,0x34ce,0x3568,0x4c74b6,0x4c765e,0x3d800),
        'neo_3_01': (0x109a,0x69c0,0x35a6,0x349e,0x349a,0x34a2,0xdda,0xe5a,0x3526,0x35c0,0x5c6d08,0x5c6eb0,0x7d800),
        'neo_3_21': (0x10d2,0x1509c,0x35de,0x34d6,0x34d2,0x34da,0xe0a,0xe92,0x355e,0x35f8,0x417224,0x4173cc,0x7d800),
    }[name]
    definitions = dict(a5=0x9000, stack=0x10000, stub=0x11000, data=0x12000, ram_size=ram_size,
        mask_query=r['targets'][152], **dict(zip(('first','payload','floor_addr','last_addr','current_addr',
        'clipboard_addr','descriptors','ids','bases','init_marker','phase_start','phase_stop','top'),layout)))
    script = 'local model=' + json.dumps(name) + '\n'
    script += '\n'.join(f'local {key}={value}' for key, value in definitions.items()) + '\n'
    script += (HERE / 'lifecycle-probe.lua').read_text()
    (work / 'probe.lua').write_text(script)
    with (work / 'mame.log').open('w') as log:
        result = subprocess.run([str(executable), driver, '-rompath', str(work / 'roms') + ';' + str(WS / 'mame/roms'),
            '-nvram_directory', str(work / 'nvram'), '-cfg_directory', str(cfg), '-video', 'none', '-sound', 'none',
            '-nothrottle', '-seconds_to_run', '20', '-autoboot_delay', '0', '-autoboot_script', str(work / 'probe.lua')],
            cwd=work, env={**os.environ, 'SDL_VIDEODRIVER': 'dummy'}, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    log = (work / 'mame.log').read_text(errors='replace')
    print(log, flush=True)
    assert result.returncode == 0 and 'PASS lifecycle qualification complete ' + name in log and 'FAIL ' not in log
    row = {'rom': name, 'system_sha256': r['sha256'], 'smallrom_sha256': hashlib.sha256(small).hexdigest(), 'artifacts': []}
    for path in sorted(work.glob('*.ram')):
        raw = path.read_bytes()
        compressed = path.with_suffix('.ram.gz')
        compressed.write_bytes(gzip.compress(raw, mtime=0))
        row['artifacts'].append({'file': str(compressed.relative_to(out)), 'raw_sha256': hashlib.sha256(raw).hexdigest(), 'gzip_sha256': hashlib.sha256(compressed.read_bytes()).hexdigest()})
    row['log_sha256'] = hashlib.sha256((work / 'mame.log').read_bytes()).hexdigest()
    manifest['runs'].append(row)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('PASS all lifecycle cases; evidence:', out)
