"""Conservative standalone A5-slot removal for proven ordinary C frames.

First instruction must push A5. No MOVEM, frame pointer, CFI, inline assembly,
indexed SP or dynamic stack motion. Model original SP through the complete CFG;
only accesses above the removed slot change displacement. Reject the whole
function on uncertainty. Caller CCR is not an input to ordinary C functions.
"""
import hashlib,os,re
import flag_cleanup
from collections import deque
from functools import lru_cache
REPORTS={}
class Unsafe(Exception):pass

def enabled():
 return os.environ.get('OS3K_CLEANUP','1')=='1' and os.environ.get('OS3K_A5_CLEANUP','1')=='1'

def operands(text):
 result=[];depth=0;start=0
 for i,ch in enumerate(text):
  if ch in '([':depth+=1
  elif ch in ')]':depth-=1
  elif ch==',' and depth==0:result.append(text[start:i].strip());start=i+1
 result.append(text[start:].strip());return result

def immediate(text):
 if not re.fullmatch(r'#[-+]?(?:0x[0-9a-fA-F]+|\d+)',text):raise Unsafe('nonconstant-stack-motion')
 return int(text[1:],0) if 'x' in text.lower() else int(text[1:],10)

def displacement(text):
 if text=='(%sp)':return 0
 match=re.fullmatch(r'([-+]?\d+)\(%sp\)',text) or re.fullmatch(r'\(([-+]?\d+),%sp\)',text)
 if not match:raise Unsafe('unsupported-SP-address')
 return int(match[1])

_CC='eq|ne|lt|le|gt|ge|hi|ls|cc|cs|hs|lo|mi|pl|vc|vs'
_COND=re.compile(r'(?:j|b)(?:'+_CC+r')(?:\.[bswl])?$')
_PLAIN=re.compile(r'(?:movea?|moveq|lea|pea|adda?|suba?|addq|subq|cmpa?|cmpi|tst|clr|neg|not|and|or|eor|andi|ori|eori|muls|mulu|divs|divu|ext|swap|asl|asr|lsl|lsr|rol|ror|roxl|roxr|btst|bset|bclr|bchg|exg|s(?:'+_CC+r'|t|f))(?:\.[bwl])?$')


def function(body):
 lines=body.splitlines();nodes=[];labels={}
 for pos,line in enumerate(lines):
  text=line.strip()
  if text in {'#APP','#NO_APP','#NOAPP'}:raise Unsafe('inline-assembly')
  if not text or text.startswith(('#','|')):continue
  if ';' in text or '/*' in text or '*/' in text:raise Unsafe('compound-assembly')
  if re.fullmatch(r'[\w.$]+:',text):labels[text[:-1]]=len(nodes);continue
  if text.startswith('.'):
   if re.match(r'\.(?:type|size|globl|global|hidden|local|align|p2align|reloc)\b',text):continue
   raise Unsafe('directive:'+text.split()[0])
  words=text.split(None,1);op=words[0];args=operands(words[1]) if len(words)>1 else []
  if op.startswith('movem'):raise Unsafe('MOVEM-frame')
  if op.startswith(('link','unlk')) or re.search(r'%(?:fp|a6)\b',text):raise Unsafe('frame-pointer')
  if set(re.findall(r'%([a-z][a-z0-9]*)',text))-{*(f'd{i}' for i in range(8)),*(f'a{i}' for i in range(6)),'sp','pc'}:raise Unsafe('special-register')
  nodes.append((pos,op,args))
 if not nodes or nodes[0][1:]!=('move.l',['%a5','-(%sp)']):raise Unsafe('not-first-standalone-save')
 if len(nodes)>4096:raise Unsafe('function-budget')
 states={0:(0,False,False)};todo=deque([0]);changes={};restores=0;exits=0;offsets=0
 def send(index,state):
  if not 0<=index<len(nodes):raise Unsafe('falls-off-function')
  if index in states:
   if states[index][:2]!=state[:2]:raise Unsafe('inconsistent-stack-join')
   if states[index][2] and not state[2]:states[index]=state;todo.append(index)
  else:states[index]=state;todo.append(index)
 def checked(depth,active):
  if depth<0 or depth>1048576 or (active and depth<4):raise Unsafe('crossed-save-slot')
 while todo:
  index=todo.popleft();depth,active,flags_dead=states[index];pos,op,args0=nodes[index];args=args0.copy()
  if index==0:
   if (depth,active)!=(0,False):raise Unsafe('save-reentry')
   changes[pos]='';send(index+1,(4,True,False));continue
  if op in {'move.l','movea.l'} and args==['(%sp)+','%a5']:
   if not active or depth!=4:raise Unsafe('unmatched-A5-restore')
   changes[pos]='';restores+=1;send(index+1,(0,False,flags_dead));continue
  if op=='rts':
   if depth or active:raise Unsafe('unbalanced-return')
   exits+=1;continue
  call=op in {'jsr','jbsr','bsr','bsr.w','bsr.s','bsr.l'}
  jump=op in {'jra','bra','bra.w','bra.s','bra.l','jmp'}
  conditional=bool(_COND.fullmatch(op)) or op in {'dbra','dbf'}
  if call or jump or conditional:
   if conditional and op not in {'dbra','dbf'} and not flags_dead:raise Unsafe('entry-CCR-read')
   if call:
    flags_dead=True  # ordinary C calls have no incoming/outgoing CCR contract
    if len(args)!=1 or '%sp' in args[0]:raise Unsafe('SP-call-target')
    send(index+1,(depth,active,flags_dead));continue
   target=args[-1] if args else ''
   if op in {'dbra','dbf'} and (len(args)!=2 or not re.fullmatch(r'%d[0-7]',args[0])):raise Unsafe('unknown-loop')
   if target in labels:
    send(labels[target],(depth,active,flags_dead))
   elif jump and not depth and not active:
    if len(args)!=1 or '%sp' in target:raise Unsafe('unknown-tail')
    exits+=1
   else:raise Unsafe('unresolved-branch')
   if conditional:send(index+1,(depth,active,flags_dead))
   continue
  if op=='nop':send(index+1,(depth,active,flags_dead));continue
  if not _PLAIN.fullmatch(op):raise Unsafe('opcode:'+op)
  if re.search(r'\(%a5\)\+|-\(%a5\)',','.join(args)):raise Unsafe('A5-written')
  if '%a5' in args:
   if op=='exg' or (args[-1]=='%a5' and not op.startswith(('cmp','tst','btst'))):raise Unsafe('A5-written')
  if not flags_dead:
   effect=flag_cleanup.effect(lines[pos])
   if effect=='write':flags_dead=True
   elif effect=='preserve' or op=='exg':pass
   elif op in {'add.l','add.w','add.b','addq.l','addq.w','addq.b','sub.l','sub.w','sub.b','subq.l','subq.w','subq.b'}:
    if not re.fullmatch(r'%(?:a[0-7]|sp|fp)',args[-1]):flags_dead=True
   else:raise Unsafe('entry-CCR-unknown:'+op)
  # Only constant, explicit stack allocation/cleanup is accepted.
  if args and args[-1]=='%sp':
   if len(args)!=2:raise Unsafe('SP-write')
   if op=='lea':delta=displacement(args[0])
   elif op in {'add.l','adda.l','addq.l','sub.l','suba.l','subq.l'}:
    delta=immediate(args[0])*( -1 if op.startswith('sub') else 1)
   else:raise Unsafe('SP-write')
   depth-=delta;checked(depth,active);send(index+1,(depth,active,flags_dead));continue
  width=4 if op=='moveq' else {'b':1,'w':2,'l':4}.get(op.rsplit('.',1)[-1],1)
  address_only=op in {'lea','pea'}
  for k,operand in enumerate(args):
   if '%sp' not in operand:continue
   if operand=='%sp':raise Unsafe('SP-alias')
   if operand=='-(%sp)':
    if address_only:raise Unsafe('address-autodecrement')
    depth+=2 if width==1 else width;checked(depth,active)
    continue
   if operand=='(%sp)+':
    if address_only:raise Unsafe('address-autoincrement')
    offset=0
   else:offset=displacement(operand)
   if offset<0:raise Unsafe('below-SP-reference')
   if active:
    lo=offset-depth;hi=lo+(0 if address_only else width-1)
    if lo>=0:new=offset-4
    elif hi < -4:new=offset
    else:raise Unsafe('save-slot-reference')
    if new!=offset:
     args[k]=(str(new)+'(%sp)') if new else '(%sp)';offsets+=1
   if operand=='(%sp)+':
    depth-=2 if width==1 else width;checked(depth,active)
  if op=='pea':depth+=4;checked(depth,active)
  if args!=args0:changes[pos]='\t'+op+' '+','.join(args)
  send(index+1,(depth,active,flags_dead))
 if len(states)!=len(nodes):raise Unsafe('unreachable-instructions')
 if not restores or not exits:raise Unsafe('missing-return')
 result='\n'.join(changes.get(i,line) for i,line in enumerate(lines))
 return result,{'restores':restores,'offsets_adjusted':offsets,'instructions_removed':1+restores}


@lru_cache(maxsize=384)
def _transform(assembly,identity):
 lines=assembly.splitlines();out=[];reports=[];i=0
 inline=set();inside=False
 for pos,line in enumerate(lines):
  if line.strip()=='#APP':inside=True
  if inside:inline.add(pos)
  if line.strip() in {'#NO_APP','#NOAPP'}:inside=False
 while i<len(lines):
  match=re.match(r'\s*\.type\s+([\w.$]+),\s*@function\s*$',lines[i])
  if not match:out.append(lines[i]);i+=1;continue
  name=match[1];end=i+1
  while end<len(lines) and not re.match(r'\s*\.size\s+'+re.escape(name)+r'\s*,',lines[end]):end+=1
  if end==len(lines):out.extend(lines[i:]);break
  block=lines[i:end+1];entry=next((j for j,l in enumerate(block) if l.strip()==name+':'),None)
  marker='__bw_a5_'+hashlib.sha256((identity+'\0'+name).encode()).hexdigest()[:24]
  report={'function':name,'marker':marker,'accepted':False}
  try:
   if any(pos in inline for pos in range(i,end+1)):raise Unsafe('inline-assembly')
   if entry is None:raise Unsafe('missing-entry-label')
   # Nested type declarations / data in a function are not supported.
   if any(re.match(r'\s*\.type\s',l) for l in block[1:]):raise Unsafe('nested-type')
   rewritten,stats=function('\n'.join(block[entry+1:-1]))
   block=block[:entry+1]+rewritten.splitlines()+[block[-1]];report.update(stats,accepted=True)
  except Unsafe as error:report['reason']=str(error)
  if entry is not None:block[entry+1:entry+1]=['.globl '+marker,'.hidden '+marker,marker+':']
  reports.append(report);out.extend(block);i=end+1
 return '\n'.join(out)+'\n',reports


def transform(assembly,identity):
 text,reports=_transform(assembly,identity);REPORTS[identity]=reports
 return text


def live_stats(records,image):
 details=[]
 for record,_,_ in records:
  details.extend(dict(r,object=record['object']) for r in REPORTS.get(record['object'],[]) if r['marker'] in image.values)
 details=list({r['marker']:r for r in details}.values())
 return {'enabled':enabled(),'live_functions':details,
         'accepted_functions':sum(r['accepted'] for r in details),
         'removed_instructions':sum(r.get('instructions_removed',0) for r in details),
         'adjusted_offsets':sum(r.get('offsets_adjusted',0) for r in details)}
