import os,sys,json
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'tests/qemu/build'/'asm-proof';OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'tools'))
os.environ['OS3K_CLEANUP']='1'
os.environ.update(OS3K_ASM_LIVENESS='1',OS3K_ASM_CFG='1',OS3K_TST_CLEANUP='0',OS3K_A5_CLEANUP='0')
import relative_calls as adapter,asm_liveness as live
with patch.dict(os.environ, {}, clear=True):
 assert live.enabled()
with patch.dict(os.environ, {'OS3K_CLEANUP':'0','OS3K_ASM_LIVENESS':'1'}, clear=True):
 assert not live.enabled()
with patch.dict(os.environ, {'OS3K_ASM_LIVENESS':'0'}, clear=True):
 assert not live.enabled()
rows=[]
def check(name,following,wanted,cfg=True,destination='%d0',allowed=('%a0',)):
 source='.type f,@function\nf:\n\tmove.l value@GOT(%a5),'+destination+'\n'+following+'\n\trts\n.size f,.-f\n'
 r=adapter.make_record(source,OUT/(name+'.o'));r['asm_allowed']=list(allowed)
 os.environ['OS3K_ASM_CFG']='1' if cfg else '0'
 result=adapter.render(r,set(),{s['label'] for s in r['sites']})
 item=next(x for x in live.REPORTS[r['object']] if x['label']==r['sites'][0]['label'])
 assert bool(item['scratch'])==wanted,(name,item,result)
 rows.append({'case':name,'rewrite':wanted,'proof':item['proof']})
for i,body in enumerate(['move.l %d0,%a0','move.w %d0,%a0','movea.l #0,%a0','movea.w #0,%a0','lea 4(%a5),%a0','movem.l (%sp)+,#256','movem.w (%sp)+,%a0/%a2','movem.l 4(%a2),%a0-%a1','movem.l #60,-(%sp)\nmovem.l (%sp)+,#15360\nmove.l #0,%a0','pea 16(%sp)\nmove.l (%sp)+,%d1\nmove.l #0,%a0']):
 check('kill-'+str(i),body,True)
for i,body in enumerate(['move.l %a0,%d1','move.l 4(%a0),%d1','move.l %d0,(%a0)+','adda.l #4,%a0','lea 4(%a0),%a0','exg %d0,%a0','movem.l #128,-(%sp)','movem.l %a0/%d0,4(%sp)','movem.l (%a0)+,#256','unlk %a0','rts','rte','jsr (%a1)','bsr called','jmp (%a1)','unknown %d0','move.w %sr,%d0','move.l %usp,%a0','trap #0','#APP\nmove.l #0,%a0\n#NO_APP','.cfi_startproc']):
 check('barrier-'+str(i),body+'\nmove.l #0,%a0',False)
body='tst.l %d1\njeq .Lkill\nmove.l #0,%a0\njra .Lend\n.Lkill:\nmove.w #1,%a0\n.Lend:'
check('both-paths',body,True);check('linear-stops',body,False,cfg=False)
check('one-path-read','tst.l %d1\njeq .Lread\nmove.l #0,%a0\njra .Lend\n.Lread:\nmove.l %a0,%d1\n.Lend:',False)
check('skip-unreachable','jra .Lkill\nunknown\n.Lkill:\nmove.l #0,%a0',True)
check('cycle','.Lloop:\nsubq.l #1,%d1\njne .Lloop\nmove.l #0,%a0',False)
check('budget','nop\n'*65+'move.l #0,%a0',False)
check('destination-read','move.l #0,%a0',False,destination='(%a0)')
check('uppercase-read','move.l %A0,%d1\nmove.l #0,%a0',False)
check('bare-register-read','move.l a0,%d1\nmove.l #0,%a0',False)
check('uppercase-destination','move.l #0,%a0',False,destination='(%A0)')
check('bare-destination','move.l #0,%a0',False,destination='(a0)')
check('fixed-or-missing','move.l #0,%a0',False,allowed=())
check('other-register','move.l #0,%a0\nmove.l #0,%a1',True,allowed=('%a1',))
# Call lowering is authoritative: do not trust a target load removed by BSR.
source='.type f,@function\nf:\n\tmove.l value@GOT(%a5),%d0\n\tmove.l called@GOT(%a5),%a0\n\tjsr (%a0)\n\trts\n.size f,.-f\n'
r=adapter.make_record(source,OUT/'calls.o');r['asm_allowed']=['%a0'];call=next(s for s in r['sites'] if s['kind']=='call');address=next(s for s in r['sites'] if s['kind']=='address')
for disabled,wanted in [(set(),False),({call['label']},True)]:
 adapter.render(r,disabled,{address['label']});item=next(x for x in live.REPORTS[r['object']] if x['label']==address['label']);assert bool(item['scratch'])==wanted
 rows.append({'case':'actual-GOT-call' if wanted else 'actual-BSR-call','rewrite':wanted,'proof':item['proof']})
# Numeric masks differ in predecrement stores and normal restores.
for number in range(16):
 assert live.effect('movem.l #'+str(1<<(15-number))+',-(%sp)','%a0')==('read' if number==8 else 'preserve')
 assert live.effect('movem.w (%sp)+,#'+str(1<<number),'%a0')==('kill' if number==8 else 'preserve')
assert live.effect('movem.l #0200,-(%sp)','%a0')=='read'
assert live.effect('movem.l (%sp)+,#0400','%a0')=='kill'
assert live.effect('movem.l #0x80,-(%sp)','%a0')=='read'
assert live.register_list('#09') is None
assert not any(m in sys.modules for m in ['rtl_hints','pic_rtl'])
(OUT/'unit-results.json').write_text(json.dumps(rows,indent=2)+'\n');print('PASS',len(rows),'proof cases, 32 MOVEM-mask checks, and no RTL imports')
