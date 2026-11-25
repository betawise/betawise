#!/usr/bin/env python3
"""Original neotools + original Neo Manager, with a disposable packet transport.

This is NOT a USB controller test. Command-lane normalization is optional and
explicit; it is a NOR fixture assumption, not qualified physical board wiring.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output', type=Path)
parser.add_argument('--normalize-command-lanes', action='store_true')
parser.add_argument('--repair-on-init', action='store_true',
                    help='Test first applet repairing the floor after the native RAM clear')
parser.add_argument('--ram-loader-only', action='store_true',
                    help='Exercise the private RAM-image entry instead of flash installation')
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, str(ROOT / 'neotools'))
from usb.core import USBError
from neotools.applet.manager import install_applet, remove_applet, fetch_applet
from neotools.applet.applet import read_applet_list
from neotools.device import restart

sha = lambda data: hashlib.sha256(data).hexdigest()
firmware = ROOT / 'Ghidra/Alphasmart Neo/SmartApplets'
system = (firmware / 'os3kneorom.os3kos').read_bytes()
small = (firmware / 'smallos3kneorom.os3kos').read_bytes()
assert sha(system) == '32fe55bb50c1b58326bd303f14973b8402ddf8bf6662b210e4d5e9f931c7e6c0'
flash = bytearray(b'\xff' * 0x400000)
flash[:len(small)] = small
source = 0
for offset in range(0x50, 0x70, 8):
    address, size = struct.unpack_from('>II', system, offset)
    if not address and not size:
        break
    size = (size+1023) & ~1023
    flash[address-0x400000:address-0x400000+size] = system[source:source+size]
    source += size

def applet(index):
    blob = bytearray(1024)
    struct.pack_into('>IIII', blob, 0, 0xc0ffeead, 1024, 2048 if index < 3 else 3072, 0)
    struct.pack_into('>IHBB', blob, 16, 0xff000000, (0xFF40, 0xFF41, 0xFF42, 0xFF43)[index-1], 1, 0)
    name = f'HeapProbe{index}'.encode()
    blob[24:24+len(name)] = name
    blob[60:64] = bytes([1, 0, 65, 0])
    struct.pack_into('>IIII', blob, 132, 148, 0, 1, 2)
    # status = 0; if (message == 18) *(uint32_t *)A5 = 70000000 + index;
    # No crt0, allocator, RAM clearing, or file-table manipulation in this applet.
    code = bytes.fromhex('206f000c42900caf00000018000466062abc')
    code += (0x70000000+index).to_bytes(4, 'big') + bytes.fromhex('4e75')
    if index == 1:
        # Observe from executed callback instructions, not a speculative ROM read tap.
        assembly = '''.text
        .globl entry
        entry:
        movea.l 12(%sp),%a0
        clr.l (%a0)
        cmpi.l #0x18,4(%sp)
        bne.w done
        move.l #0x70000001,(%a5)
        move.l 0x35de,0x26300
        move.w 0x35f8,0x26308
        move.l 0x356a,0x26310
        movea.l #0x3562,%a1
        moveq #-1,%d0
        moveq #30,%d1
        next:
        movea.l (%a1)+,%a0
        cmpa.l #0,%a0
        beq.s skip
        cmp.l %a0,%d0
        bls.s skip
        move.l %a0,%d0
        skip:
        dbra %d1,next
        move.l %d0,0x26304
        '''
        if args.repair_on_init:
            assembly += '''cmpi.w #0x2675,0x35f8
            beq.s no_repair
            cmp.l 0x35de,%d0
            bls.s no_repair
            move.l %d0,0x35de
            no_repair:
            '''
        assembly += '''move.l 0x35de,0x2630c
        addq.l #1,0x26314
        done:
        rts
        '''
        (out / 'init-observer.S').write_text(assembly)
        subprocess.run(['m68k-linux-gnu-as', '-m68000', str(out / 'init-observer.S'),
                        '-o', str(out / 'init-observer.o')], check=True)
        subprocess.run(['m68k-linux-gnu-objcopy', '-O', 'binary', '-j', '.text',
                        str(out / 'init-observer.o'), str(out / 'init-observer.bin')], check=True)
        code = (out / 'init-observer.bin').read_bytes()
    blob[148:148+len(code)] = code
    struct.pack_into('>I', blob, 1020, 0xcafefeed)
    return bytes(blob)

applets = [applet(i) for i in (1, 2, 3)]
if args.ram_loader_only:
    assembly = '''.text
    .globl entry
    entry:
    movea.l 12(%sp),%a0
    clr.l (%a0)
    cmpi.l #0x26,4(%sp)
    bne.s other
    move.l #0x7010,(%a0)
    rts
    other:
    cmpi.l #0x18,4(%sp)
    bne.s done
    move.l #0x52414d49,(%a5)
    move.l 0x35de,0x26320
    move.w 0x35f8,0x26324
    done:
    rts
    '''
    (out / 'ram-entry.S').write_text(assembly)
    subprocess.run(['m68k-linux-gnu-as', '-m68000', str(out / 'ram-entry.S'),
                    '-o', str(out / 'ram-entry.o')], check=True)
    subprocess.run(['m68k-linux-gnu-objcopy', '-O', 'binary', '-j', '.text',
                    str(out / 'ram-entry.o'), str(out / 'ram-entry.bin')], check=True)
    ram_image = bytearray(applet(4))
    struct.pack_into('>I', ram_image, 8, 2048)
    struct.pack_into('>H', ram_image, 20, 0xFF43)
    ram_image[148:1020] = bytes(1020-148)
    code = (out / 'ram-entry.bin').read_bytes()
    ram_image[148:148+len(code)] = code
    (out / 'ram-probe.bin').write_bytes(ram_image)
for i, blob in enumerate(applets[:2]):
    flash[0x70000+i*1024:0x70400+i*1024] = blob
(out / 'nvram/asneo').mkdir(parents=True)
(out / 'nvram/asneo/flashnv').write_bytes(flash)
(out / 'roms/asneo').mkdir(parents=True)
for name in ('smallos3kneorom.os3kos', 'os3kneorom.os3kos'):
    shutil.copyfile(firmware / name, out / 'roms/asneo' / name)
(out / 'cfg').mkdir()
(out / 'cfg/asneo.cfg').write_text('<mameconfig version="10"><system name="asneo"><input>'
    '<port tag=":NOR_PROFILE" type="CONFIG" mask="1" defvalue="0" value="1" />'
    '</input></system></mameconfig>\n')
(out / 'probe.lua').write_text('local normalize_command_lanes=' +
    str(args.normalize_command_lanes).lower() + '\n' + (HERE / 'probe.lua').read_text())

class PacketTransport:
    """Replace only host transport; all Manager requests run in original ROM."""
    def __init__(self):
        self.sequence = 0
        self.queue = bytearray()
        self.label = 'ordinary-close'
        self.log = (out / 'protocol.jsonl').open('w')

    def rpc(self, op, data=b''):
        self.sequence += 1
        path = out / f'request-{self.sequence}'
        temporary = path.with_suffix('.tmp')
        temporary.write_bytes(op.encode()+data)
        temporary.rename(path)
        response = out / f'response-{self.sequence}'
        deadline = time.monotonic()+70
        while not response.exists():
            if (out / 'failure.txt').exists():
                raise RuntimeError((out / 'failure.txt').read_text())
            if proc.poll() is not None:
                raise RuntimeError((out / 'mame.log').read_text())
            if time.monotonic() >= deadline:
                raise TimeoutError((op, self.sequence))
            time.sleep(.005)
        reply = response.read_bytes()
        # Keep exact protocol headers and hashes without publishing ROM header payloads.
        self.log.write(json.dumps(dict(sequence=self.sequence, op=op,
            outgoing=data.hex(), incoming_header=reply[:8].hex(), incoming_size=len(reply),
            incoming_sha256=sha(reply)))+'\n')
        self.log.flush()
        return reply

    def dialogue_start(self, *unused):
        self.rpc('O')  # Native system applet's direct-transport open callback.

    def dialogue_end(self):
        self.rpc('C', self.label.encode())  # Native poll/close, including restart.

    def write(self, data, timeout=None):
        blob = bytes(data)
        for offset in range(0, len(blob), 8):
            self.queue.extend(self.rpc('W', blob[offset:offset+8]))

    def read(self, length, timeout=None):
        if not self.queue:
            # neotools catches this when it polls again after successful finalization.
            raise USBError('No queued Manager reply', errno=110)
        reply = bytes(self.queue[:length])
        del self.queue[:length]
        return reply

manifest = dict(scope='Neo 3.21 original Manager packet transaction; no USB controller acceptance',
    ram_applet_id=0xFF43, normalize_command_lanes=args.normalize_command_lanes, system_sha256=sha(system),
    repair_on_init=args.repair_on_init,
    ram_loader_only=args.ram_loader_only,
    smallrom_sha256=sha(small), initial_flash_sha256=sha(flash),
    applet_sha256=[sha(blob) for blob in applets], inputs=[])
for path in [HERE / 'run.py', HERE / 'probe.lua', ROOT / 'mame/neodiag',
             ROOT / 'neotools/neotools/applet/manager.py',
             ROOT / 'neotools/neotools/applet/applet.py',
             ROOT / 'neotools/neotools/message.py', ROOT / 'neotools/neotools/device.py']:
    manifest['inputs'].append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path.read_bytes())))
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
log = (out / 'mame.log').open('w')
proc = subprocess.Popen([str(ROOT / 'mame/neodiag'), 'asneo', '-rompath', str(out / 'roms'),
    '-nvram_directory', str(out / 'nvram'), '-cfg_directory', str(out / 'cfg'),
    '-video', 'none', '-sound', 'none', '-nothrottle', '-autoboot_delay', '0',
    '-autoboot_script', str(out / 'probe.lua'), '-seconds_to_run', '240'],
    cwd=out, env={**os.environ, 'SDL_VIDEODRIVER':'dummy'}, stdout=log, stderr=subprocess.STDOUT)
dev = None
checks = []
def check(name, condition):
    assert condition, name
    checks.append(name)
    print('PASS', name, flush=True)

try:
    deadline = time.monotonic()+30
    while not (out / 'ready').exists():
        if proc.poll() is not None:
            raise RuntimeError((out / 'mame.log').read_text())
        if time.monotonic() >= deadline:
            raise TimeoutError('native cold startup')
        time.sleep(.02)
    dev = PacketTransport()
    check('initial two applets enumerated by neotools',
          [r['applet_id'] for r in read_applet_list(dev)] == [0, 0xFF40, 0xFF41])
    if args.ram_loader_only:
        dev.rpc('L')
        loaded = json.loads(dev.rpc('S', b'after-ram-load'))
        raw = (out / 'after-ram-load.ram').read_bytes()
        num = lambda addr: int.from_bytes(raw[addr:addr+4], 'big')
        check('private loader registers RAM header and following A5',
              loaded['applets'][-1]['id'] == 0xFF43
              and loaded['applets'][-1]['header'] == 0x5c000
              and loaded['applets'][-1]['base'] == 0x5c400)
        check('new RAM instance receives INIT while global init is complete',
              num(0x5c400) == 0x52414d49 and num(0x26320) == 0x5c000
              and int.from_bytes(raw[0x26324:0x26326], 'big') == 0x2675)
        check('RAM registration preserves both existing A5 blocks',
              raw[0x7c800:0x7d800] == bytes([0xc3])*4096)
        check('RAM applet appears in native Manager enumeration',
              [r['applet_id'] for r in read_applet_list(dev)] == [0,0xFF40,0xFF41,0xFF43])
        dev.rpc('Q')
        proc.wait(timeout=10)
        check('RAM test exits successfully', proc.returncode == 0)
        (out / 'results.json').write_text(json.dumps(dict(result='PASS', checks=checks,
            scope='private Neo 3.21 RAM-loader entry; no USB upload or flash install',
            normalize_command_lanes=args.normalize_command_lanes), indent=2)+'\n')
        raise SystemExit(0)
    dev.rpc('H', b'before-control')
    dev.label = 'control'
    dev.dialogue_start()
    restart(dev)
    dev.dialogue_end()
    control = json.loads(dev.rpc('S', b'after-control'))
    before = (out / 'before-control.ram').read_bytes()
    after = (out / 'after-control.ram').read_bytes()
    check('actual warm restart preserves heap and both A5 arenas',
          before[0x7b800:0x7d800] == after[0x7b800:0x7d800] and control['floor'] == 0x7b800)
    dev.label = 'install'
    install_applet(dev, applets[2])
    finalized = json.loads(dev.rpc('S', b'install-finalized'))
    check('native finalizer adjusts floor and invalidates initialization',
          finalized['floor'] == 0x7ac00 and finalized['marker'] == 0)
    dev.dialogue_start()
    restart(dev)
    dev.dialogue_end()
    installed = json.loads(dev.rpc('S', b'after-install'))
    expected = 0x7bc00 if args.repair_on_init else 0x7ac00
    check('post-install floor and fully assigned third A5 base',
          installed['floor'] == expected and installed['applets'][-1]['base'] == 0x7bc00)
    raw = (out / 'after-install.ram').read_bytes()
    num = lambda addr: int.from_bytes(raw[addr:addr+4], 'big')
    check('executed INIT observes complete base table before repair',
          num(0x26300) == 0x7ac00 and num(0x26304) == num(0x26310) == 0x7bc00
          and num(0x2630c) == expected)
    downloaded = fetch_applet(dev, 0xFF42)
    check('neotools reads back every programmed applet byte', downloaded == applets[2])
    (out / 'readback.json').write_text(json.dumps(dict(size=len(downloaded), sha256=sha(downloaded))))
    dev.rpc('H' if args.repair_on_init else 'R', b'before-remove')
    dev.label = 'remove'
    remove_applet(dev, 0xFF42)
    removed = json.loads(dev.rpc('S', b'after-remove'))
    expected = 0x7c800 if args.repair_on_init else 0x7b800
    check('post-remove floor agrees with selected repair policy',
          removed['floor'] == expected and removed['applets'][-1]['base'] == 0x7c800)
    raw = (out / 'after-remove.ram').read_bytes()
    num = lambda addr: int.from_bytes(raw[addr:addr+4], 'big')
    check('executed INIT observes survivor base table before repair',
          num(0x26300) == 0x7b800 and num(0x26304) == 0x7c800
          and num(0x26310) == 0 and num(0x2630c) == expected)
    check('removed applet absent from neotools enumeration',
          [r['applet_id'] for r in read_applet_list(dev)] == [0, 0xFF40, 0xFF41])
    for label, floor in [('install', 0x7ac00), ('remove', 0x7b800)]:
        raw = (out / f'{label}-cleared.ram').read_bytes()
        check(f'{label}: entire applet RAM region zero before initialization',
              raw[floor:0x7d800] == bytes(0x7d800-floor))
    dev.rpc('Q')
    proc.wait(timeout=10)
    check('native test exited successfully', proc.returncode == 0)
    (out / 'results.json').write_text(json.dumps(dict(result='PASS', checks=checks,
        scope=manifest['scope'], normalize_command_lanes=args.normalize_command_lanes,
        repair_on_init=args.repair_on_init), indent=2)+'\n')
except Exception as error:
    (out / 'results.json').write_text(json.dumps(dict(result='INCOMPLETE', checks=checks,
        error=str(error), scope=manifest['scope'],
        normalize_command_lanes=args.normalize_command_lanes), indent=2)+'\n')
    raise
finally:
    if dev:
        dev.log.close()
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=5)
    log.close()
    artifacts = []
    for path in sorted(out.glob('*.ram')):
        raw = path.read_bytes()
        compressed = path.with_suffix('.ram.gz')
        compressed.write_bytes(gzip.compress(raw, mtime=0))
        artifacts.append(dict(file=compressed.name, raw_sha256=sha(raw), sha256=sha(compressed.read_bytes())))
    manifest['ram_captures'] = artifacts
    final_flash = out / 'nvram/asneo/flashnv'
    manifest['final_flash_sha256'] = sha(final_flash.read_bytes())
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
