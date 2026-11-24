#!/usr/bin/env python3
"""Summarize deterministic NKJV Psalm 119 native/streaming MAME read-throughs.

Run check-bible-reader.py --version NKJV --profile --system-font --experiment
huffman-prune --readthrough {line,page}, or check-bible-stream.py --version NKJV
--readthrough {line,page}. Repeat with --work-profile for decoder counts.
Pass the eight output directories here. Counter builds are never timing inputs.
"""
import argparse,json,statistics,struct
from pathlib import Path

def summarize(path):
 meta=json.loads((path/'readthrough.json').read_text())
 result=json.loads((path/'results.json').read_text())
 assert result['status']=='passed',path
 checks=json.loads((path/'checks.json').read_text())
 events=json.loads((path/'timings.json').read_text())
 valid_lcd_counter=len({x.get('lcd_writes')for x in events})>1
 def pair(index,start,end,last_start=False):
  rows=[r for r in events if r['check']==index]
  a=([r for r in rows if r['phase']==start][-1] if last_start else next(r for r in rows if r['phase']==start))
  b=next(r for r in rows[rows.index(a)+1:] if r['phase']==end)
  assert b['time']>=a['time']
  return dict(seconds=b['time']-a['time'],work=[y-x for x,y in zip(a['work'],b['work'])],**({'lcd_writes':b['lcd_writes']-a['lcd_writes']} if valid_lcd_counter and 'lcd_writes'in a and 'lcd_writes'in b else {}))
 # Prove traversal reached source EOF, rather than merely timing enough keys.
 chapters=[c for b in json.loads((path/'source.json').read_text()) for c in b['chapters']]
 verses=chapters[596]
 assert len(verses)==176 and sum(len(v)+1 for v in verses)==meta['source_bytes']
 if meta['reader'].startswith('native'):
  final=result['results'][-2]
  expected=sum(map(len,verses))+len(verses)-1+sum(6+len(str(i)) for i in range(1,177))
  assert final['logical_caret']==expected
  state=struct.unpack('>12I',(path/f'metrics-{len(checks):02}.bin').read_bytes())
  assert state[10]==meta['source_bytes'] and state[6]+(final.get('feed')or[0])[0]==expected
 else:
  state=struct.unpack('>35I',(path/f'stream-{len(checks):02}.bin').read_bytes())
  assert state[23]==meta['source_bytes']-1 and state[10]==meta['source_bytes']
  if meta['reader']=='streaming-roll':assert state[33]==(meta['wrapped_lines']-4 if meta['mode']=='line'else 0),('hardware roll count',state[33])
 initial=pair(2,1,4,last_start=True) # Exclude streaming prompt-open paint earlier in this check.
 movements=[]
 for i,c in enumerate(checks,1):
  if c['name'].startswith('Readthrough') or c['name'].startswith('Finish'):
   movements.append(pair(i,20 if meta['reader'].startswith('native') else 1,21 if meta['reader'].startswith('native') else 4))
 # Explicit End case name is kept independent of the traversal command count.
 used={i for i,c in enumerate(checks,1) if c['name'].startswith(('Readthrough','Finish'))}
 for i,c in enumerate(checks,1):
  if i>2 and i<len(checks) and i not in used:
   movements.append(pair(i,20 if meta['reader'].startswith('native') else 1,21 if meta['reader'].startswith('native') else 4))
 pure=pair(len(checks),7,8)
 background=[]
 if meta['reader'].startswith(('native-background','native-lookahead','native-viewport','native-prewrap')):
  opened=next(r['time']for r in events if r['check']==2 and r['phase']==1)
  # Nested instrumentation can restore phase 30 inside the same idle slice.
  # Count the enclosing 30..31 interval once.
  j=0
  while j<len(events):
   r=events[j]
   if r['phase']==30 and r['time']>=opened and r['check']<len(checks):
    k=next(k for k in range(j+1,len(events))if events[k]['phase']==31);q=events[k]
    background.append(dict(seconds=q['time']-r['time'],work=[y-x for x,y in zip(r['work'],q['work'])]));j=k
   j+=1
 totalwork=[sum(x['work'][i] for x in [initial]+movements+background) for i in range(len(initial['work']))]

 if meta['work']:
  assert pure['work'][1]==meta['source_bytes'],(path,pure)
  assert pure['work'][0]==meta['source_bytes']+1,(path,pure)
 out=dict(**meta,path=str(path.resolve()),checks=len(checks),initial=initial,scroll_seconds=sum(x['seconds']for x in movements),background_seconds=sum(x['seconds']for x in background),total_seconds=initial['seconds']+sum(x['seconds']for x in movements+background),final_end=movements[-1],movement_commands=len(movements),movement_median_seconds=statistics.median(x['seconds']for x in movements),movement_max_seconds=max(x['seconds']for x in movements),pure_decode=pure,total_work=totalwork)
 if meta['reader'].startswith('native'):
  out['initial_decode_and_file_fill']=pair(2,3,2)
  out['initial_editor_refresh']=pair(2,2,6)
  out['initial_jump']=pair(2,6,4)
 return out

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('directories',nargs='+',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 runs=[summarize(d)for d in a.directories]
 a.output.write_text(json.dumps(runs,indent=2)+'\n')
 for r in runs:
  print(r['reader'],r['mode'],'work'if r['work']else'timing',f"initial={r['initial']['seconds']:.6f} scroll={r['scroll_seconds']:.6f} total={r['total_seconds']:.6f} pure={r['pure_decode']['seconds']:.6f}",r['total_work'])
if __name__=='__main__':main()
