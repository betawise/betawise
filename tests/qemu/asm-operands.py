import os,sys,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'tests/qemu/build'/'asm-operand-proof';OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'tools'));import relative_calls as a,asm_liveness as live
os.environ['OS3K_CLEANUP']='1'
os.environ.update(OS3K_ASM_LIVENESS='1',OS3K_ASM_CFG='1',OS3K_TST_CLEANUP='0',OS3K_A5_CLEANUP='0')
def run(args):return subprocess.run([str(x) for x in args],check=True,capture_output=True)
cases=[('%d0','%d0'),('%a0','%a0'),('-(%sp)','(%sp)'),('12(%sp)','12(%sp)'),('(%sp)','(%sp)'),('(%sp)+','-4(%sp)'),('8(%sp,%d1.w)','12(%sp)'),('(%a2)','(%a2)'),('(%a2)+','-4(%a2)'),('-(%a2)','(%a2)'),('8(%a6)','8(%a6)'),('result','result')]
rows=[]
for ram in [False,True]:
 d=OUT/('ram' if ram else 'rom');d.mkdir(exist_ok=True);source='.text\n.globl _start\n.type _start,@function\n_start:\n lea 0x80000000,%a5\n lea report,%a4\n'
 for ccr in range(32):
  for destination,value in cases:
   source+=' lea stack+128,%sp\n lea result+16,%a2\n lea stack+64,%a6\n moveq #4,%d1\n'+f' move.w #{ccr},%ccr\n'
   source+=f'\tmove.l target@GOT(%a5),{destination}\n movea.l #0x12345678,%a1\n move.w %sr,%d7\n move.l {value},%d0\n move.l %d0,(%a4)+\n move.l %sp,(%a4)+\n move.l %a2,(%a4)+\n and.l #31,%d7\n move.l %d7,(%a4)+\n'
 size=16*len(cases)*32
 source+=f' moveq #4,%d0\n moveq #1,%d1\n move.l #report,%d2\n move.l #{size},%d3\n trap #0\n moveq #1,%d0\n moveq #0,%d1\n trap #0\n.size _start,.-_start\n'+('.data' if ram else '.section .rodata')+'\ntarget: .long 123\n.data\nresult: .space 32\nreport: .space '+str(size)+'\n.bss\nstack: .space 256\n'
 record=a.make_record(source,d/'input.o');record['asm_allowed']=['%a1']
 lds=d/'test.lds';lds.write_text('ENTRY(_start)\nSECTIONS { .text 0x10000 : { *(.text) } .rodata 0x17000 : { *(.rodata) } .got 0x80000000 : { *(.got*) } .data 0x80001000 : { *(.data) } .bss : { *(.bss) } }\n')
 outputs=[];sizes=[]
 for name,r,disabled in [('original',record,{s['label'] for s in record['sites']}),('existing',record,set()),('scratch',record,set())]:
  os.environ['OS3K_ASM_LIVENESS']='1' if name=='scratch' else '0'
  o=d/(name+'.o');p=a.compile_record(r,o,disabled,set() if ram else {s['label'] for s in record['sites']});assert p.returncode==0,p.stderr;e=o.with_suffix('.elf');run([os.environ.get('CROSS_COMPILE','m68k-linux-gnu-')+'ld','-T',lds,o,'-o',e]);outputs.append(run(['qemu-m68k','-cpu','m68000',e]).stdout)
  from elftools.elf.elffile import ELFFile
  with e.open('rb') as f:sizes.append(ELFFile(f).get_section_by_name('.text')['sh_size'])
 count=sum(x['scratch'] is not None for x in live.REPORTS[record['object']]);assert count==10*32,(ram,count)
 missing=dict(record,asm_allowed=[]);a.render(missing,set(),set() if ram else {s['label'] for s in record['sites']});assert not any(x['scratch'] for x in live.REPORTS[record['object']])
 assert len(outputs[0])==size and outputs[0]==outputs[1]==outputs[2],(ram,'value/SP/address/CCR mismatch')
 assert sizes[1]==sizes[2],(ram,'unexpected size difference')
 for name,out in zip(['original','existing','scratch'],outputs):(d/(name+'.bin')).write_bytes(out)
 rows.append({'RAM':ram,'CPU_comparisons':len(cases)*32,'stack_pairs_replaced':count,'code_sizes':sizes,'equal':True})
assert not any(m in sys.modules for m in ['pic_rtl','rtl_hints'])
(OUT/'results.json').write_text(json.dumps(rows,indent=2)+'\n');print('PASS',sum(r['CPU_comparisons'] for r in rows),'comparisons: 12 destinations x 32 CCR inputs x ROM/RAM; same optimized code size, missing-hint fallback')
