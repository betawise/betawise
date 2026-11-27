#!/usr/bin/env python3
"""Execute shipping flat font images on m68000 at two ROM/RAM placements.

Check every glyph byte against BDF sources, no CRT initialization or screen oracle.
Preserve binaries, descriptor RAM, disassembly, hashes and results under build/.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / 'fonts'
OUT = ROOT / 'tests/fonts/build/minimal'
SPEC = importlib.util.spec_from_file_location('fontgen', FONTS / 'fontgen.py')
fg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fg)
CROSS = os.environ.get('CROSS_COMPILE', 'm68k-linux-gnu-')


def sources(base):
    if base.startswith('BetaWiseTerminal-'):
        name = {'Medium': 'glyphs.bdf', 'Small': 'glyphs-5x7.bdf', 'Tiny': 'glyphs-4x6.bdf'}[base.split('-')[1]]
        return [(FONTS / 'build/bdf/BetaWiseTerminal' / name, 63)]
    directory = FONTS / 'build/bdf' / base.split('-')[0]
    return [(directory / f'{base}-{style}.bdf', 63) for style in ('Regular', 'Bold', 'Italic', 'BoldItalic')] + [(directory / 'private' / f'{base}-SmallCaps.bdf', 'blank')]


def run(command, **kwargs):
    return subprocess.run([str(x) for x in command], check=True, timeout=30, **kwargs)


def check(image):
    base = image.stem
    out = OUT / base
    out.mkdir(parents=True, exist_ok=True)
    data = image.read_bytes()
    rom_size, ram_size = struct.unpack_from('>II', data, 4)
    entry = struct.unpack_from('>I', data, 132)[0]
    assert data[:4] == bytes.fromhex('c0ffeead')
    assert int.from_bytes(data[16:20], 'big') == 0xff000031
    family, size = base.removeprefix('BetaWise').split('-')
    if family == 'Terminal':
        expected_id = 0xa1f0
        columns, lines = {'Medium': (44,8), 'Small': (52,9), 'Tiny': (66,10)}[size]
        menu_name = f'BetaWise - Terminal {size} ({columns}x{lines})'
    else:
        lines = {'Large': 3, 'Medium': 4, 'Small': 5, 'Tiny': 6}[size]
        expected_id = 0xaff0 + 4 * ['Serif','Sans','Book','Mono'].index(family) + lines-3
        menu_name = f'BetaWise - {family} {size} ({lines} lines)'
    assert int.from_bytes(data[20:22], 'big') == expected_id
    assert data[24:60].split(b'\0')[0].decode() == menu_name
    faces = [fg.load(p, 'iso8859-1', fallback) for p, fallback in sources(base)]
    assert rom_size == len(data) and ram_size == 16 * len(faces)
    assert data[-4:] == bytes.fromhex('cafefeed')
    elf = image.with_suffix('.elf')
    relocs = subprocess.check_output([CROSS+'readelf', '-rW', elf], text=True)
    assert 'GOT' not in relocs
    symbols = subprocess.check_output([CROSS+'readelf', '-sW', elf], text=True)
    addresses = {}
    for line in symbols.splitlines():
        fields = line.split()
        if len(fields) >= 8 and fields[0].rstrip(':').isdigit():
            addresses[fields[7]] = int(fields[1], 16)
    assert not any(name.endswith('GLYPH_FONT') for name in addresses)
    assert addresses['Os3kEntry'] == addresses['BwProcessMessage'] == entry
    assert addresses['__header'] == 0
    assert '_ConsoleReset' not in symbols and '__os3k_got_size' not in symbols
    # Only header constants and GCC's range-checked PC16 references.
    pc16_displacements = []
    assert 'R_68K_PC32' not in relocs
    for line in relocs.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[2].startswith('R_68K_'):
            assert fields[2] in ('R_68K_PC32', 'R_68K_PC16', 'R_68K_PC8', 'R_68K_32'), line
            if fields[2] == 'R_68K_PC16':
                address = int(fields[0], 16)
                pc16_displacements.append(struct.unpack_from('>h', data, address)[0])
            if fields[2] == 'R_68K_32':
                address = int(fields[0], 16)
                assert address in {4, 8, 132}, line
    disassembly = subprocess.check_output([CROSS+'objdump', '-dr', elf], text=True)
    assert '<Os3kEntry>' in disassembly or '<BwProcessMessage>' in disassembly
    (out/'disassembly.txt').write_text(disassembly)
    (out/'relocations.txt').write_text(relocs)
    arrays = []
    checks = []
    for index, glyphs in enumerate(faces):
        packets = []
        for glyph in glyphs:
            packets.append(bytes(sum(1 << (y-band) for y in range(band, min(band+8, glyph.height)) if glyph.getpixel((x,y))) for band in range(0,glyph.height,8) for x in range(glyph.width)))
        expected = b''.join(packets)
        arrays.append(f'static const unsigned char expected{index}[]={{'+','.join(map(str,expected))+'};')
        arrays.append(f'static const unsigned char widths{index}[]={{'+','.join(str(g.width) for g in glyphs)+'};')
        message = 'MSG_FONT_GET_PRIVATE' if index == 4 else str(0x1000002+index)
        checks.append(f'''{{ FontHeader_t *f=0; unsigned off=0;
 call({message},(uint32_t)&f,&status);
 if(status || f!=(FontHeader_t *)(font_ram+4)+{index} || f->height!={glyphs[0].height} || f->padding) return 10+{index};
 for(unsigned c=0;c<256;c++) {{
 unsigned w=f->width_table?f->width_table[c]:f->max_width;
 unsigned pos=f->offset_table?f->offset_table[c]:c*f->max_bytes;
 if(w!=widths{index}[c] || w>f->max_width) return 20+{index};
 for(unsigned j=0;j<w*((f->height+7)/8);j++) if(f->bitmap_data[pos+j]!=expected{index}[off++]) return 30+{index};
 }} }}''')
    # String matching avoids depending on compiler literal pooling/layout.
    name = 'BetaWise ' + base.removeprefix('BetaWise').replace('-', ' ')
    source = '''#include "os3k.h"
extern unsigned char font_image[],font_ram[];
void *memcpy(void *d,const void *s,unsigned n) {
 unsigned char *p=d;const unsigned char *q=s;while(n--)*p++=*q++;return d;
}
unsigned __mulsi3(unsigned a,unsigned b) {
 unsigned result=0;while(b){if(b&1)result+=a;a<<=1;b>>=1;}return result;
}
ARRAYS
int test(void) {
 void (*call)(Message_e,uint32_t,uint32_t*)=(void *)(font_image+ENTRY);
 uint32_t status=0xdeadbeef;
 for(unsigned i=0;i<RAM+8;i++)font_ram[i]=0xa5;
 for(unsigned pass=0;pass<2;pass++) {
 CHECKS
 const char *name=0,*want="@NAME@";
 call(MSG_FONT_GET_NAME,(uint32_t)&name,&status);
 if(status || !name)return 40;
 while(*want)if(*name++!=*want++)return 41;
 if(*name)return 42;
 uint32_t output[3]={0x12345678,0,0xabcdef01};
 call(MSG_FONT_GET_HEIGHT,(uint32_t)&output[1],&status);
 if(status || output[0]!=0x12345678 || output[1]!=@HEIGHT@ || output[2]!=0xabcdef01)return 43;
 if(RAM==16)for(unsigned m=0x1000003;m<=0x1000007;m++) {
 if(m==0x1000006)continue;
 uint32_t missing=0xdeadbeef;call(m,(uint32_t)&missing,&status);if(status || missing)return 44;
 }
 call(MSG_INIT,0,&status);if(status)return 45;
 call(MSG_SETFOCUS,0,&status);if(status)return 46;
 call((Message_e)0xdeadbeef,0,&status);if(status)return 47;
 for(unsigned i=0;i<4;i++)if(font_ram[i]!=0xa5 || font_ram[RAM+4+i]!=0xa5)return 48;
 }
 return 0;
}
'''.replace('ARRAYS','\n'.join(arrays)).replace('CHECKS','\n'.join(checks)).replace('ENTRY',str(entry)).replace('RAM',str(ram_size)).replace('@HEIGHT@',str(faces[0][0].height)).replace('@NAME@',name)
    (out/'test.c').write_text(source)
    (out/'start.S').write_text(f'''.text
.globl _start
_start:
 lea font_ram+4,%a5
 jsr test
 move.l %d0,%d6
 moveq #4,%d0
 moveq #1,%d1
 lea font_ram,%a0
 move.l %a0,%d2
 move.l #{ram_size+8},%d3
 trap #0
 move.l %d6,%d1
 moveq #1,%d0
 trap #0
.section .font_image,"ax"
.globl font_image
font_image:
.incbin "{image}"
.section .font_ram,"aw",@nobits
.balign 4
.globl font_ram
font_ram: .skip {ram_size+8}
.section .note.GNU-stack,"",@progbits
''')
    placements=[]
    for rom, ram in ((0x210000,0x30000),(0x710000,0x50000)):
        binary=out/f'test-{rom:x}.elf'
        run([CROSS+'gcc','-m68000','-msoft-float','-fshort-enums','-ffixed-a5','-fno-pic','-fno-pie','-Os','-ffreestanding','-fno-builtin','-nostdlib','-static','-I'+str(ROOT/'os3k'),'-I'+str(ROOT/'os3k/build'),'-Wl,--build-id=none','-Wl,-Ttext=0x10000',f'-Wl,--section-start=.font_image={rom:#x}',f'-Wl,--section-start=.font_ram={ram:#x}',out/'start.S',out/'test.c','-o',binary])
        result=run(['qemu-m68k','-cpu','m68000',binary],capture_output=True)
        (out/f'ram-{rom:x}.bin').write_bytes(result.stdout)
        (out/f'qemu-{rom:x}.log').write_bytes(result.stderr)
        assert len(result.stdout)==ram_size+8
        placements.append(dict(rom=rom,ram=ram,passed=True))
    return dict(applet=base,rom=len(data),ram=ram_size,sha256=hashlib.sha256(data).hexdigest(),faces=len(faces),glyphs=256*len(faces),pc16_max_distance=max(map(abs,pc16_displacements)),placements=placements,passed=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    images=sorted(FONTS.glob('build/*/*.OS3KApp'))
    assert len(images)==19
    results=[check(image) for image in images]
    # Prove that a future layout regression fails at link time, rather than
    # silently wrapping the 68000's signed 16-bit displacement.
    far_script = OUT/'out-of-range.lds'
    script = (FONTS/'font.lds').read_text()
    far_script.write_text(script.replace('        *(.rodata .rodata.*)',
                                         '        . += 0x10000;\n        *(.rodata .rodata.*)'))
    failure = subprocess.run([CROSS+'ld', str(FONTS/'build/BetaWiseMono-Large/FontApplet.o'),
                              '-static', '-T', str(far_script), '--gc-sections',
                              '-o', str(OUT/'out-of-range.elf')], capture_output=True, text=True, timeout=30)
    (OUT/'out-of-range.log').write_text(failure.stdout+failure.stderr)
    assert failure.returncode != 0 and 'R_68K_PC16' in failure.stderr
    assert 'relocation truncated to fit' in failure.stderr
    report = json.dumps(dict(passed=True,applets=results),indent=2)+'\n'
    (OUT/'results.json').write_text(report)
    if args.report:
        args.report.write_text(report)
    print(f'PASS {len(results)} GOT-free shipping images, {sum(r["glyphs"] for r in results):,} exact glyphs at two ROM/RAM placements, dirty RAM, pre-init getters and guards')


if __name__=='__main__':
    main()
