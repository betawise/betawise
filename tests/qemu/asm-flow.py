import os,sys,subprocess,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'tests/qemu/build'/'asm-flow-proof';OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'tools'))
os.environ['OS3K_CLEANUP']='1'
os.environ.update(OS3K_ASM_LIVENESS='1',OS3K_TST_CLEANUP='0',OS3K_A5_CLEANUP='0')
import relative_calls as a,asm_liveness as live
from elf_reader import Image

def run(args):return subprocess.run([str(x) for x in args],check=True,capture_output=True)
# Runtime input alternates the conditional paths. The opaque callee deliberately
# observes A0, so passing this test cannot depend on assuming C call clobbers.
cases=[('long-kill','move.l #0x112233,%a0',True,True,'%d0'),('word-kill','move.w #-1,%a0',True,True,'%d0'),('restore-long','move.l #0x112233,-(%sp)\n movem.l (%sp)+,#256',True,True,'%d0'),('restore-word','move.w #-1,-(%sp)\n movem.w (%sp)+,#256',True,True,'%d0'),('save-mask','movem.l #128,-(%sp)\n move.l (%sp)+,%d1\n move.l #0x112233,%a0',False,False,'%d0'),('ea-read','move.l (%a0),%d1\n move.l #0x112233,%a0',False,False,'%d0'),('both-paths','tst.l %d1\n jeq .Lzero\n move.l #0x112233,%a0\n jra .Ljoin\n.Lzero:\n move.w #-1,%a0\n.Ljoin:',False,True,'%d0'),('one-path-read','tst.l %d1\n jeq .Lzero\n move.l #0x112233,%a0\n jra .Ljoin\n.Lzero:\n move.l %a0,%d1\n.Ljoin:',False,False,'%d0'),('destination-read','move.l (%a0),%d0\n move.l #0x112233,%a0',False,False,'(%a0)'),('other-destination','move.l (%a1),%d0\n move.l #0x112233,%a0',True,True,'(%a1)'),('direct-opaque-call','\tmove.l called@GOT(%a5),%a0\n\tjsr (%a0)',False,False,'%d0'),('fallback-opaque-call','\tmove.l called@GOT(%a5),%a0\n\tjsr (%a0)',True,True,'%d0')]
results=[]
for name,body,linear,cfg,destination in cases:
 for ram in [False,True]:
  d=OUT/(name+('-ram' if ram else '-rom'));d.mkdir(exist_ok=True)
  src='.text\n.globl _start\n.type _start,@function\n_start:\n lea 0x80000000,%a5\n lea report,%a4\n move.l %sp,%a6\n'
  for ccr in range(32):
   for bit in [0,1]:
    src+=f' lea old1,%a0\n lea old2,%a1\n move.l #{bit},%d1\n move.w #{ccr},%ccr\n bsr.w f\n move.w %sr,%d7\n and.l #31,%d7\n move.l %d7,(%a4)+\n move.l %d0,(%a4)+\n move.l %d1,(%a4)+\n move.l %a0,(%a4)+\n move.l %a1,(%a4)+\n move.l %sp,%d0\n sub.l %a6,%d0\n move.l %d0,(%a4)+\n'
  size=64*24
  src+=f' moveq #4,%d0\n moveq #1,%d1\n move.l #report,%d2\n move.l #{size},%d3\n trap #0\n moveq #1,%d0\n moveq #0,%d1\n trap #0\n.size _start,.-_start\n.type f,@function\nf:\n\tmove.l target@GOT(%a5),{destination}\n '+body+'\n rts\n.size f,.-f\n.section .text.called,"ax"\ncalled:\n move.l %a0,%d1\n rts\n'+('.section .data.target,"aw"' if ram else '.section .rodata,"a"')+'\ntarget: .long 1234\n.section .data.old,"aw"\nold1: .long 55\nold2: .long 66\n.data\nreport: .space '+str(size)+'\n'
  r=a.make_record(src,d/'input.o');r['asm_allowed']=['%a0'];labels={s['label'] for s in r['sites']};calls={s['label'] for s in r['sites'] if s.get('kind')=='call'}
  disabled=calls if name.startswith('fallback') else set()
  script=d/'test.lds';script.write_text('ENTRY(_start)\nSECTIONS { .rom 0x10000 : { *(.text) } .rodata 0x17000 : { *(.rodata) } .called '+('0x30000' if name.startswith('fallback') else '0x16000')+' : { *(.text.called) } .got 0x80000000 : { *(.got*) } .target 0x80001000 : { *(.data.target) } .old 0x80001100 : { *(.data.old) } .data 0x80002000 : { *(.data) } }\n')
  outputs=[]
  for mode,wanted in [('baseline',False),('linear',linear),('cfg',cfg)]:
   os.environ['OS3K_ASM_LIVENESS']='0' if mode=='baseline' else '1';os.environ['OS3K_ASM_CFG']='1' if mode=='cfg' else '0'
   o=d/(mode+'.o');result=a.compile_record(r,o,disabled,set() if ram else labels);assert result.returncode==0,result.stderr
   e=o.with_suffix('.elf');run([os.environ.get('CROSS_COMPILE','m68k-linux-gnu-')+'ld','--emit-relocs','-T',script,o,'-o',e]);data=run(['qemu-m68k','-cpu','m68000',e]).stdout;assert len(data)==size;outputs.append(data);(d/(mode+'.bin')).write_bytes(data)
   if mode!='baseline':
    rows=live.REPORTS[r['object']];count=sum(x['scratch'] is not None for x in rows);assert bool(count)==wanted,(name,ram,mode,rows)
  assert outputs[0]==outputs[1]==outputs[2],(name,ram,'CPU register/SP/CCR mismatch')
  results.append({'case':name,'RAM':ram,'linear':linear,'CFG':cfg,'CPU_inputs':64,'equal':True})
assert not any(m in sys.modules for m in ['pic_rtl','rtl_hints'])
(OUT/'results.json').write_text(json.dumps(results,indent=2)+'\n');print('PASS',sum(r['CPU_inputs'] for r in results),'input states in both proof modes: branches, MOVEM, destination reads, actual BSR/GOT calls; no RTL imports')
