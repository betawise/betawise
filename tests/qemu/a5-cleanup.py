"""Conservative A5 frame proofs, independently executed on m68000."""
import sys,json,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import a5_cleanup as a
from elf_reader import Image
PREFIX=os.environ.get("CROSS_COMPILE","m68k-linux-gnu-")
QEMU=os.environ.get("QEMU_M68K","qemu-m68k")
out=ROOT/'tests/qemu/build/a5-cleanup';out.mkdir(parents=True,exist_ok=True)
checks=[]
def check(name,body,ok,contains=()):
 try:
  text,stats=a.function(body)
  assert ok,(name,'unexpected acceptance')
  for s in contains:assert s in text,(name,s,text)
  checks.append({'name':name,'accepted':True,'stats':stats})
 except a.Unsafe as e:
  assert not ok,(name,str(e))
  checks.append({'name':name,'accepted':False,'reason':str(e)})
base='move.l %a5,-(%sp)\n'
end='move.l (%sp)+,%a5\nrts\n'
check('argument',base+'move.l 8(%sp),%d0\n'+end,True,['4(%sp)'])
check('other saved register',base+'move.l %d2,-(%sp)\nmove.l 12(%sp),%d2\nmove.l (%sp)+,%d2\n'+end,True,['8(%sp)'])
check('fixed locals',base+'subq.l #8,%sp\nmove.l 16(%sp),%d0\nmove.l %d0,(%sp)\naddq.l #8,%sp\n'+end,True,['12(%sp)','%d0,(%sp)'])
check('postincrement destination',base+'pea value\nmove.l (%sp)+,12(%sp)\n'+end,True,['move.l (%sp)+,8(%sp)'])
check('two returns',base+'cmp.l #1,%d0\njeq .L1\n'+end+'.L1:\n'+end,True)
check('loop',base+'.L1:\nsubq.l #1,%d0\njne .L1\n'+end,True)
check('tail',base+'move.l 8(%sp),%d0\nmove.l (%sp)+,%a5\njmp target\n',True,['4(%sp)'])
for name,body in [
 ('entry flags read',base+'seq %d0\n'+end),
 ('MOVEM',base+'movem.l %d2-%d4,-(%sp)\n'+end),
 ('frame pointer','link.w %fp,#-8\n'+base+end),
 ('inline assembly',base+'#APP\nnop\n#NO_APP\n'+end),
 ('CFI',base+'.cfi_adjust_cfa_offset 4\n'+end),
 ('dynamic stack',base+'sub.l %d0,%sp\n'+end),
 ('stack join',base+'jeq .L1\npea value\n.L1:\n'+end),
 ('A5 mutation',base+'move.l %d0,%a5\n'+end),
 ('A5 postincrement',base+'move.l (%a5)+,%d0\n'+end),
 ('A5 predecrement',base+'move.l %d0,-(%a5)\n'+end),
 ('save slot read',base+'move.l (%sp),%d0\n'+end),
 ('SP alias',base+'move.l %sp,%a0\n'+end),
 ('indexed stack',base+'move.l (%sp,%d0.l),%d1\n'+end),
 ('unknown instruction',base+'trap #0\n'+end),
 ('unreachable instructions',base+'jra .L1\nnop\n.L1:\n'+end),
 ('wrong restore depth',base+'pea value\n'+end),
]:check(name,body,False)
global_asm='#APP\n.type external_asm,@function\nexternal_asm:\n'+base+'move.l 8(%sp),%d0\n'+end+'.size external_asm,.-external_asm\n#NO_APP\n'
ret=a.transform(global_asm,'global-assembly-regression');assert 'move.l %a5,-(%sp)' in ret
assert not a.REPORTS['global-assembly-regression'][0]['accepted']
checks.append({'name':'global assembly outside function body','accepted':False,'reason':'inline-assembly'})
# Execute original and rewritten assembly over a different A5 base and 32 CCR
# states. The function changes an incoming stack argument through a synthetic
# adapter PEA / postincrement MOVE, has two epilogues, locals and a loop.
body='''move.l %a5,-(%sp)
subq.l #8,%sp
move.l 16(%sp),%d0
move.l %d0,(%sp)
.Lloop:
subq.l #1,%d0
jgt .Lloop
addq.l #8,%sp
cmp.l #0,8(%sp)
jeq .Lzero
pea value(%pc)
move.l (%sp)+,12(%sp)
move.l 8(%sp),%d0
move.l (%sp)+,%a5
rts
.Lzero:
moveq #99,%d0
move.l (%sp)+,%a5
rts
'''
new,stats=a.function(body)
script=out/'test.lds';script.write_text('ENTRY(_start)\nSECTIONS { .text 0x10000 : { *(.text) } .data 0x80000000 : { *(.data) } }\n')
results=[]
for mode,code in [('original',body),('removed',new)]:
 text='.text\n.globl _start\n_start:\n lea report,%a4\n move.l %sp,%a6\n'
 for ccr in range(32):
  for argument in [0,3]:
   text+=f' move.l #0x81234560,%a5\n move.l #0xabcdef,-(%sp)\n move.l #{argument},-(%sp)\n move.w #{ccr},%ccr\n bsr.w function\n move.w %sr,%d7\n and.l #31,%d7\n move.l %d7,(%a4)+\n move.l %d0,(%a4)+\n move.l %a5,(%a4)+\n move.l 4(%sp),(%a4)+\n move.l %sp,%d4\n sub.l %a6,%d4\n move.l %d4,(%a4)+\n addq.l #8,%sp\n'
 size=64*20
 text+=f' moveq #4,%d0\n moveq #1,%d1\n move.l #report,%d2\n move.l #{size},%d3\n trap #0\n moveq #1,%d0\n moveq #0,%d1\n trap #0\nfunction:\n'+code+'\nvalue: .long 0x12345678\n.data\nreport: .space '+str(size)+'\n'
 path=out/(mode+'.s');path.write_text(text)
 subprocess.run([PREFIX+'as','-m68000',path,'-o',path.with_suffix('.o')],check=True,capture_output=True)
 subprocess.run([PREFIX+'ld','-T',script,path.with_suffix('.o'),'-o',path.with_suffix('.elf')],check=True,capture_output=True)
 r=subprocess.run([QEMU,'-cpu','m68000',path.with_suffix('.elf')],check=True,capture_output=True);path.with_suffix('.bin').write_bytes(r.stdout);results.append(r.stdout)
# Code shrinks, so the address of value changes. Compare its pointee identity
# separately, and normalize that one expected address field per nonzero case.
from struct import unpack,pack
norm=[]
for mode,data in zip(['original','removed'],results):
 value=Image(out/(mode+'.elf')).values['value']
 words=list(unpack('>'+str(len(data)//4)+'I',data))
 for i in range(64):
  assert words[5*i+2]==0x81234560
  assert words[5*i+1]==(99 if i%2==0 else 3)
  assert words[5*i+3]==(0xabcdef if i%2==0 else value)
  assert words[5*i+4]==0xfffffff8,'caller SP mismatch'
  if i%2:words[5*i+3]=0x12345678
 norm.append(words)
assert norm[0]==norm[1],'CCR/register/argument mismatch'
(out/'results.json').write_text(json.dumps({'unit_cases':checks,'CPU_cases':64,'equal':True,'stats':stats},indent=2)+'\n')
print('PASS',len(checks),'proof cases and 64 CPU argument/register/SP/CCR comparisons')
