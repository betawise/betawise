#!/usr/bin/env python3
"""Join accepted native-window/lazy measurements with production ROM/A5 sizes."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('readthrough',HERE/'profile-readthrough.py');rt=importlib.util.module_from_spec(spec);spec.loader.exec_module(rt)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--production',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();base=ROOT/'.research-work/bible-compression'
 memory={r['name']:r for r in json.loads((a.production/'results.json').read_text())}
 cases=[('native-original','Native, original wrapper','readthrough-native-line-v2','readthrough-native-page'),('native-optimized','Native, optimized full chapter','native-final-optimized-line','readthrough-native-direct-cmd-page'),('native-window','Native moving window','native-final2-window-line','native-final2-window-page'),('native-demand','Native append on demand','native-final2-demand-line','native-final2-demand-page'),('native-background','Native background completion','native-bg-responsive-line','native-bg-responsive-page'),('custom-repaint','Custom, full repaint','readthrough-stream-line','readthrough-stream-page'),('custom-lcd-roll','Custom, LCD roll','readthrough-stream-roll-line-v3','readthrough-stream-roll-page')]
 rows=[]
 for key,label,line,page in cases:
  runs={kind:rt.summarize(base/name)for kind,name in [('line',line),('page',page)]}
  assert all(r['version']=='NKJV'and r['wrapped_lines']==314 for r in runs.values())
  if key.startswith('native'):
   resident=[]
   for run in runs.values():
    reports=json.loads((Path(run['path'])/'results.json').read_text())['results']
    resident.extend(r['feed'][6]if r.get('feed')and r['feed'][6]else r['logical_caret']+r['gap'][1]-r['gap'][0]for r in reports)
   peak=max(resident)
  else:peak=0
  rows.append(dict(name=key,label=label,**{k:v for k,v in memory[key].items()if k!='name'},file_peak_bytes=peak,measurements=runs))
 feature_names=['native-window-features-v5','native-final2-demand-features','native-bg-responsive-features','native-font-window','native-font-demand-v2','native-bg-responsive-small','native-end-final-window','native-end-final-demand','native-end-final-background']
 features=[]
 for name in feature_names:
  path=base/name;d=json.loads((path/'results.json').read_text());assert d['status']=='passed';features.append(dict(path=str(path),checks=len(d['results'])))
 rapid=rt.summarize(base/'native-bg-responsive-rapid')
 events=json.loads((base/'native-bg-responsive-page/timings.json').read_text());start=next(r for r in events if r['check']==2 and r['phase']==1);first=next(r for r in events[events.index(start)+1:]if r['phase']==4)
 bg=[]
 for i,r in enumerate(events):
  if r['phase']==30 and r['time']>first['time']and r['check']==2:
   end=next(x for x in events[i+1:]if x['phase']==31);bg.append(end['time']-r['time'])
 ready=max(r['time']for r in events if r['phase']==31 and r['check']==2)-first['time']
 result=dict(version='NKJV',font='original system 6x16',source_bytes=12873,wrapped_lines=314,rows=rows,features=features,rapid_background=rapid,background_elapsed_to_ready_seconds=ready,background_largest_slice_seconds=max(bg),mame_sha256=hashlib.sha256((ROOT/'mame/neodiag').read_bytes()).hexdigest(),prototype_checkpoints=sum(r['measurements'][k]['checks']for r in rows if r['name']in ['native-window','native-demand','native-background']for k in ['line','page'])+sum(f['checks']for f in features)+rapid['checks'])
 a.output.write_text(json.dumps(result,indent=2)+'\n')
 for r in rows:print(r['name'],r['rom_bytes'],r['a5_bytes'],r['file_peak_bytes'],r['measurements']['page']['initial']['seconds'],r['measurements']['line']['total_seconds'],r['measurements']['page']['total_seconds'])
 print('background ready',ready,'largest slice',max(bg),'rapid total',rapid['total_seconds'],'prototype checks',result['prototype_checkpoints'])
if __name__=='__main__':main()
