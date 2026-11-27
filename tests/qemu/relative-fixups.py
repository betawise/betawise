#!/usr/bin/env python3
"""Execute GOT fixups on m68000 and exercise checked packaging fallbacks."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'tests/qemu/build/relative-fixups'
sys.path.insert(0, str(ROOT / 'tools'))
import relative_calls as adapter

PREFIX = os.environ.get('CROSS_COMPILE', 'm68k-linux-gnu-')
QEMU = os.environ.get('QEMU_M68K', 'qemu-m68k')
ENV = dict(os.environ, OS3K_INTERNAL_ORDERS='1', OS3K_LAYOUT_SOLVER='1')
for key in ('OBJECT_ORDER', 'OS3K_ORDER_SEED', 'OS3K_SINGLE_STAGE'):
    ENV.pop(key, None)
RESULTS = []


def run(command, log, cwd=ROOT, env=ENV, expected=0):
    result = subprocess.run([str(x) for x in command], cwd=cwd, env=env,
                            capture_output=True, timeout=120)
    log.write_bytes(result.stdout + result.stderr)
    assert result.returncode == expected, (command, result.returncode, str(log))
    return result.stdout


def record_object(directory, source):
    directory.mkdir(parents=True, exist_ok=True)
    # GCC writes tabs; the recognizer intentionally does not parse arbitrary asm.
    source = '\n'.join('\t'+line[1:] if line.startswith(' ') else line
                       for line in source.splitlines())+'\n'
    obj = directory/'test.o'
    record = adapter.make_record(source, obj)
    result = adapter.compile_record(record, obj, {s['label'] for s in record['sites']})
    assert result.returncode == 0, result.stderr
    adapter.REGISTRY.mkdir(exist_ok=True)
    (adapter.REGISTRY/(adapter.digest(obj.read_bytes())+'.json')).write_text(json.dumps(record))
    return obj, record


def operand_modes(ram):
    directory = OUT/('ram-operands' if ram else 'rom-operands')
    directory.mkdir(parents=True, exist_ok=True)
    cases = [('%d0','%d0'),('%a0','%a0'),('-(%sp)','(%sp)'),
             ('12(%sp)','12(%sp)'),('(%sp)','(%sp)'),('(%sp)+','-4(%sp)'),
             ('8(%sp,%d1.w)','12(%sp)'),('(%a2)','(%a2)'),
             ('(%a2)+','-4(%a2)'),('-(%a2)','(%a2)'),('8(%a6)','8(%a6)'),
             ('result','result')]
    source = '.text\n.globl _start\n_start:\n lea 0x80000000,%a5\n lea report,%a4\n'
    for destination, value in cases:
        source += (' lea stack+128,%sp\n lea result+16,%a2\n lea stack+64,%a6\n'
                   ' moveq #4,%d1\n move.w #31,%ccr\n'
                   f' move.l target@GOT(%a5),{destination}\n'
                   ' move.w %sr,%d7\n'+f' move.l {value},%d0\n'
                   ' move.l %d0,(%a4)+\n move.l %sp,(%a4)+\n move.l %a2,(%a4)+\n'
                   ' and.l #31,%d7\n move.l %d7,(%a4)+\n')
    source += (' moveq #4,%d0\n moveq #1,%d1\n move.l #report,%d2\n'
               f' move.l #{16*len(cases)},%d3\n trap #0\n'
               ' moveq #1,%d0\n moveq #0,%d1\n trap #0\n')
    source += ('.data' if ram else '.section .rodata')+'\ntarget: .long 123\n'
    source += '.data\nresult: .space 32\nreport: .space 256\n.bss\nstack: .space 256\n'
    _, record = record_object(directory, source)
    script = directory/'test.lds'
    script.write_text('ENTRY(_start)\nSECTIONS { . = 0x10000; .text : { *(.text) } '
                      '. = 0x14000; .rodata : { *(.rodata) } . = 0x80000000; '
                      '.got : { *(.got*) } . = 0x80001000; .data : { *(.data) } '
                      '.bss : { *(.bss) } }\n')
    labels = {s['label'] for s in record['sites']}
    samples = []
    for name, disabled in [('original',labels),('rewritten',set())]:
        obj = directory/(name+'.o')
        result = adapter.compile_record(record, obj, disabled, set() if ram else labels)
        assert result.returncode == 0, result.stderr
        elf = obj.with_suffix('.elf')
        run([PREFIX+'ld','-T',script,obj,'-o',elf], directory/(name+'-link.log'))
        samples.append(run([QEMU,'-cpu','m68000',elf],directory/(name+'.bin')))
    assert samples[0] == samples[1] and len(samples[0]) == 16*len(cases)
    RESULTS.append({'case':directory.name,'destinations':len(cases),'passed':True})


def near_far():
    directory = OUT/'near-far'
    source = '''.text
.globl _start
_start:
 lea 0x80000000,%a5
 move.l near@GOT(%a5),%a0
 move.l (%a0),%d4
 move.l far@GOT(%a5),%a1
 add.l (%a1),%d4
 move.l near_ram@GOT(%a5),%a2
 add.l (%a2),%d4
 move.l far_ram@GOT(%a5),%a3
 add.l (%a3),%d4
 move.l %d4,%d1
 moveq #1,%d0
 trap #0
.section .rodata
near: .long 1
.space 70000
far: .long 2
.data
near_ram: .long 3
.space 65536
far_ram: .long 36
.section .note.GNU-stack,"",@progbits
'''
    obj, _ = record_object(directory, source)
    script = directory/'test.lds'
    script.write_text('ENTRY(_start)\nSECTIONS { . = 0x10000; .text : { *(.text) *(.rodata) } '
                      '. = 0x80000000; .got : { *(.got*) } '
                      '. = 0x80000100; .data : { *(.data) } }\n')
    original = directory/'original.elf'
    run([PREFIX+'ld',obj,'-static','-T',script,'--emit-relocs','-o',original],directory/'original-link.log')
    run([QEMU,'-cpu','m68000',original],directory/'original-run.log',expected=42)
    elf = directory/'optimized.elf'
    run([sys.executable,ROOT/'tools/relative_calls.py','ld',obj,'-static','-T',script,
         '--emit-relocs','-o',elf],directory/'optimized-link.log')
    run([QEMU,'-cpu','m68000',elf],directory/'optimized-run.log',expected=42)
    relocs = run([PREFIX+'readelf','-rW',elf],directory/'relocations.txt').decode()
    assert 'R_68K_PC16' in relocs and 'R_68K_16 ' in relocs and 'R_68K_GOT16O' in relocs
    assert 'os3k_header' not in run([PREFIX+'readelf','-SW',elf],directory/'sections.txt').decode()
    RESULTS.append({'case':'near-far','rom_gap':70000,'ram_gap':65536,
                    'custom_script_preserved':True,'passed':True})


HEADER = '''.section os3k_header,"a"
.globl __header
__header:
 .long 0xc0ffeead,__os3k_rom_size,__os3k_ram_size
 .space 120
 .long Os3kEntry
 .space 12
'''
FOOTER = '''.section os3k_footer,"a"
 .long 0xcafefeed
.section .note.GNU-stack,"",@progbits
'''


def packaging_fallbacks():
    cases = {
        'table-count': '''.section .text.fixture,"ax"
.balign 2
.globl Os3kEntry
Os3kEntry:
 lea 0x80000000,%a5
.Lmeasure:
 move.l target@GOT(%a5),-(%sp)
.set rewritten_length,.-.Lmeasure
 move.l (%sp)+,%a0
 move.l (%a0),%d1
 moveq #1,%d0
 trap #0
.section .rodata,"a"
target: .long 42
.data
 .long 0
.globl extra_pointer
extra_pointer:
.if rewritten_length > 4
 .long target
.else
 .long 0
.endif
''',
        'alignment': '''.section .text.fixture,"ax"
.org 65520
.globl Os3kEntry
Os3kEntry:
 lea 0x80000000,%a5
 move.l target@GOT(%a5),-(%sp)
 move.l finish@GOT(%a5),%a0
 jmp (%a0)
.balign 65536
target: .long 42
finish:
 move.l (%sp)+,%a0
 move.l (%a0),%d1
 moveq #1,%d0
 trap #0
'''}
    for name, body in cases.items():
        directory = OUT/name
        obj, _ = record_object(directory, HEADER+body+FOOTER)
        elf = directory/'image.elf'
        command = [sys.executable,ROOT/'tools/relative_calls.py','package',obj,'-static',
                   '-T',ROOT/'os3k/os3k.lds','--gc-sections','--emit-relocs',
                   '--defsym','__os3k_reloc_size=0','-o',elf]
        if name == 'table-count': command.append('--undefined=extra_pointer')
        run(command,directory/'build.log')
        package = json.loads(Path(str(elf)+'.package.json').read_text())
        expected = [4] if name == 'table-count' else []
        assert adapter.fixup_module().fixups(elf) == expected
        assert package['total_link_calls'] > 2
        if name == 'table-count': assert package['sizing_retry']
        else: assert not json.loads(Path(str(elf)+'.calls.json').read_text())['fast_layout']['accepted']
        image = elf.with_suffix('.OS3KApp').read_bytes()
        assert int.from_bytes(image[4:8],'big') == len(image)
        RESULTS.append({'case':name,'package':package,'passed':True})


def build_controls():
    directory = OUT/'controls'
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'mode.c').write_text('''#include "os3k.h"
APPLET_HEADER_BEGIN
APPLET_ID(0xFFFE)
APPLET_NAME("Optimizer test")
APPLET_HEADER_END
void *volatile stored;
void BwProcessMessage(Message_e m, uint32_t p, uint32_t *s) {
    stored = "test";
    *s = 0;
}
void Os3kEntry(Message_e, uint32_t, uint32_t *) __attribute__((alias("BwProcessMessage")));
''')
    (directory/'Makefile').write_text('OBJ = mode.o\nTARGET = mode.OS3KApp\ninclude '+str(ROOT/'Makefile.common')+'\n')
    env = dict(os.environ)
    for key in ('OS3K_INTERNAL_ORDERS','OS3K_LAYOUT_SOLVER','OS3K_PACKAGE_SOLVER',
                'OS3K_FIXUPS','RELATIVE_CALLS','OBJECT_ORDER','OS3K_ORDER_SEED',
                'MAKEFLAGS','MFLAGS','MAKEOVERRIDES'):
        env.pop(key,None)
    make = ['make','OS3K_LIB=']
    run(make,directory/'default.log',directory,env)
    original = (directory/'mode.OS3KApp').read_bytes()
    assert json.loads((directory/'mode.elf.package.json').read_text())['total_link_calls'] == 2
    run([*make,'OS3K_INTERNAL_ORDERS=0'],directory/'disabled.log',directory,env)
    assert 'fast_layout' not in json.loads((directory/'mode.elf.calls.json').read_text())
    run([*make,'OS3K_FIXUPS=0'],directory/'raw.log',directory,env)
    import object_order
    assert object_order.read_symbols(directory/'mode.elf')['__os3k_got_size'] > 0
    run(make,directory/'restored.log',directory,env)
    assert (directory/'mode.OS3KApp').read_bytes() == original
    log = run(make,directory/'no-op.log',directory,env)
    assert b'relative_calls.py' not in log
    RESULTS.append({'case':'build-controls','sha256':hashlib.sha256(original).hexdigest(),'passed':True})


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    operand_modes(False)
    operand_modes(True)
    near_far()
    packaging_fallbacks()
    build_controls()
    (OUT/'results.json').write_text(json.dumps(RESULTS,indent=2)+'\n')
    print('PASS GOT fixups: 24 operand modes/CCR, near/far ROM and RAM, custom layout, '
          'alignment/table-count fallbacks, defaults and opt-outs')


if __name__ == '__main__':
    main()
