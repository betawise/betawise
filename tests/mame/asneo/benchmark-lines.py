#!/usr/bin/env python3
"""Compare DrawLine with a pinned pixel-at-a-time baseline in original Neo ROM.

Times are emulated machine time around real 68000 code and RasterOp calls,
not host wall time. No screen inference or saved user session is involved.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
WORKSPACE = REPO.parent
CASES = [
    ('horizontal', 1, 20, 260, 20), ('vertical', 20, 1, 20, 63),
    ('shallow', 1, 1, 260, 2), ('steep', 1, 1, 2, 63),
    ('moderate', 1, 1, 260, 63), ('diagonal', 1, 1, 63, 63),
    ('short diagonal', 1, 1, 2, 2), ('short shallow', 1, 1, 4, 2),
]
DRIVER = r'''#include "os3k.h"
typedef void (*line_t)(uint16_t,uint16_t,uint16_t,uint16_t,bool);
void line_baseline(uint16_t,uint16_t,uint16_t,uint16_t,bool);
void line_current(uint16_t,uint16_t,uint16_t,uint16_t,bool);
void entry(void) {
 volatile uint32_t *control=(volatile uint32_t*)0x76000;
 line_t line=control[0]?line_current:line_baseline;
 uint16_t x0=control[1],y0=control[2],x1=control[3],y1=control[4];
 unsigned repeats=control[5];
 RasterOp(0,0,264,65,0,ROP_WHITENESS);
 *(volatile uint16_t*)0x76020=1;
 for(unsigned i=0;i<repeats;++i)line(x0,y0,x1,y1,true);
 *(volatile uint16_t*)0x76020=2;
 control[6]=0x70617373;
}
'''
LUA = r'''local machine=manager.machine
local cpu=machine.devices[':maincpu'];local state=cpu.state;local m=cpu.spaces.program
local frame,started,index,variant=0,false,1,0
local phase='boot';local first,last,deadline;local results={}
local cases=@CASES@
local function load(path,address)
 local f=assert(io.open(path,'rb'));local s=f:read('*a');f:close()
 for i=1,#s do m:write_u8(address+i-1,s:byte(i))end
end
local tap=m:install_write_tap(0x76020,0x76021,'line_benchmark_marker',function(address,data,mask)
 if phase=='armed'and data==1 then first=machine.time:as_double();phase='measuring'
 elseif phase=='measuring'and data==2 then last=machine.time:as_double();phase='completed'end
end)
local function launch()
 local c=cases[index];m:write_u32(0x76000,variant)
 for i=2,5 do m:write_u32(0x76000+4*(i-1),c[i])end
 m:write_u32(0x76014,@REPEATS@);m:write_u32(0x76018,0);m:write_u16(0x76020,0)
 m:write_u16(0x77f00,0x60fe);m:write_u32(0x77ef0,0x77f00)
 phase='armed';deadline=frame+1200
 state.SP.value=0x77ef0;state.SR.value=0x2700;state.A5.value=0;state.PC.value=@ENTRY@
end
emu.register_frame_done(function()
 assert(tap) -- Keep the observer alive after the autoboot chunk returns.
 frame=frame+1
 local ok,error=pcall(function()
  if not started then
   if frame<180 then return end
   load(@BINARY@,0x60000);started=true;launch();return
  end
  assert(frame<deadline,'benchmark deadline: '..phase)
  if phase~='completed'or m:read_u32(0x76018)~=0x70617373 then return end
  if state.PC.value~=0x77f00 and state.PC.value~=0x77f02 then return end
  results[#results+1]=string.format('{"case":"%s","variant":%d,"seconds_per_line":%.12f}',
   cases[index][1],variant,(last-first)/@REPEATS@)
  variant=variant+1
  if variant==2 then variant=0;index=index+1 end
  if index>#cases then
   local f=assert(io.open(@RESULTS@,'w'));f:write('['..table.concat(results,',')..']\n');f:close()
   print('PASS native line benchmark');machine:exit();return
  end
  launch()
 end)
 if not ok then print('FAIL '..tostring(error));machine:exit()end
end)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    baseline_args = parser.add_mutually_exclusive_group()
    baseline_args.add_argument('--baseline-source', type=Path,
                                help='Compare against a saved C source instead of a Git revision')
    baseline_args.add_argument('--baseline-ref', default='b8c5e945749b27f9eb40d4f1987f325089bce339')
    parser.add_argument('--repeats', type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 100:
        parser.error('--repeats must be between 1 and 100')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    baseline = (args.baseline_source.read_bytes() if args.baseline_source else
        subprocess.check_output(['git', '-C', str(REPO), 'show',
            args.baseline_ref + ':os3k/os3k_graphics.c']))
    current = (REPO / 'os3k/os3k_display_gfx.c').read_bytes()
    firmware = WORKSPACE / 'Ghidra/Alphasmart Neo/SmartApplets'
    originals = {'os3kneorom.os3kos': '32fe55bb50c1b58326bd303f14973b8402ddf8bf6662b210e4d5e9f931c7e6c0',
                 'smallos3kneorom.os3kos': '6402c40878ba28747642ce474361b1596555b2a1f137db79c7ea8bb5b35a9523'}
    roms = out / 'roms/asneo'
    roms.mkdir(parents=True)
    for name, expected in originals.items():
        source = firmware / name
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected, name
        (roms / name).symlink_to(source)
    flags = ['-m68000', '-msoft-float', '-fno-pic', '-fno-pie', '-fno-builtin',
             '-fomit-frame-pointer', '-fshort-enums', '-fno-store-merging',
             '-ffunction-sections', '-fdata-sections', '-Os', '-I' + str(REPO / 'os3k')]

    def run(command):
        subprocess.run(list(map(str, command)), check=True)

    objects = []
    for name, source in [('baseline', baseline), ('current', current)]:
        path = out / (name + '.c')
        path.write_bytes(source)
        target = out / (name + '.o')
        run(['m68k-linux-gnu-gcc', *flags, '-DDrawLine=line_' + name,
             '-DDrawPixel=pixel_' + name, '-c', path, '-o', target])
        objects.append(target)
    (out / 'driver.c').write_text(DRIVER)
    run(['m68k-linux-gnu-gcc', *flags, '-c', out / 'driver.c', '-o', out / 'driver.o'])
    (out / 'raster.S').write_text('.text\n.globl RasterOp\nRasterOp: .word 0xa04c\n.section .note.GNU-stack,"",@progbits\n')
    run(['m68k-linux-gnu-as', '-m68000', out / 'raster.S', '-o', out / 'raster.o'])
    (out / 'link.ld').write_text('ENTRY(entry)\nSECTIONS { . = 0x60000; .text : { *(.text*) *(.rodata*) } .data : { *(.data*) } .bss : { *(.bss*) *(COMMON) } }\n')
    run(['m68k-linux-gnu-ld', '--gc-sections', '-T', out / 'link.ld', out / 'driver.o',
         *objects, out / 'raster.o', '-o', out / 'bench.elf'])
    run(['m68k-linux-gnu-objcopy', '-O', 'binary', out / 'bench.elf', out / 'bench.bin'])
    symbols = {parts[2]: int(parts[0], 16) for line in subprocess.check_output(
        ['m68k-linux-gnu-nm', str(out / 'bench.elf')], text=True).splitlines()
        if len(parts := line.split()) == 3}
    cases = '{' + ','.join('{' + ','.join(json.dumps(x) for x in row) + '}' for row in CASES) + '}'
    script = LUA.replace('@CASES@', cases).replace('@ENTRY@', str(symbols['entry']))
    script = script.replace('@REPEATS@', str(args.repeats)).replace('@BINARY@', json.dumps(str(out / 'bench.bin')))
    script = script.replace('@RESULTS@', json.dumps(str(out / 'timings.json')))
    (out / 'run.lua').write_text(script)
    mame = WORKSPACE / 'mame/neodiag'
    with (out / 'mame.log').open('w') as log:
        subprocess.run(list(map(str, [mame, 'asneo', '-rompath', out / 'roms',
            '-nvram_directory', out / 'nvram', '-cfg_directory', out / 'cfg',
            '-video', 'none', '-sound', 'none', '-nothrottle', '-seconds_to_run', '300',
            '-autoboot_delay', '0', '-autoboot_script', out / 'run.lua'])),
            stdout=log, stderr=subprocess.STDOUT, cwd=out,
            env={**os.environ, 'SDL_VIDEODRIVER': 'dummy'}, timeout=180, check=True)
    log = (out / 'mame.log').read_text()
    assert 'PASS native line benchmark' in log and 'FAIL' not in log, log[-2000:]
    rows = json.loads((out / 'timings.json').read_text())
    summary = []
    for name, *coordinates in CASES:
        times = {row['variant']: row['seconds_per_line'] for row in rows if row['case'] == name}
        assert set(times) == {0, 1} and all(value > 0 for value in times.values())
        row = dict(case=name, coordinates=coordinates, baseline_us=times[0] * 1e6,
                   current_us=times[1] * 1e6, speedup=times[0] / times[1])
        summary.append(row)
        print(f'{name:15} {row["baseline_us"]:9.2f} -> {row["current_us"]:9.2f} us  {row["speedup"]:.2f}x')
    report = dict(scope='Emulated machine time; real Neo 3.21 RasterOp; interrupts masked; clear excluded; no physical-device timing claim',
                  baseline_ref=(None if args.baseline_source else args.baseline_ref),
                  baseline_source=(str(args.baseline_source.resolve()) if args.baseline_source else None),
                  baseline_sha256=hashlib.sha256(baseline).hexdigest(),
                  current_sha256=hashlib.sha256(current).hexdigest(), repeats=args.repeats,
                  firmware_sha256=originals, mame_sha256=hashlib.sha256(mame.read_bytes()).hexdigest(),
                  flags=flags, compiler=subprocess.check_output(['m68k-linux-gnu-gcc', '--version'], text=True).splitlines()[0],
                  results=summary)
    (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
