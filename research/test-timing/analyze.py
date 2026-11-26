from pathlib import Path
import csv, datetime, hashlib, json, re, statistics, subprocess
from zoneinfo import ZoneInfo
BASE=Path(__file__).resolve().parent
ROOT=Path('/home/kirk/Projects/Alphasmart')
rows=[]
for line in (BASE/'measurements.jsonl').read_text().splitlines():
 r=json.loads(line);out=BASE/'runs'/r['id'];log=(out/'mame.log').read_text()
 if 'Out-of-range' in log:r['excluded_reason']='Unsupported frameskip 11 was rejected and reverted to 0.'
 elif "field 'bench_exit'" in log:r['excluded_reason']='Research exit wrapper error after underlying test PASS.'
 elif 'duplicate frame' in log or 'overlapping native text' in log:r['excluded_reason']='Invalid initial research schedule (event collision).'
 r['controller_parity_checks']=log.count('RAM_SCREEN_PARITY')
 r['completion_waits']={}
 for kind,n in re.findall(r'ADAPT action=\d+ kind=(\w+) frames=(\d+)',log):r['completion_waits'].setdefault(kind,[]).append(int(n))
 for kind,values in list(r['completion_waits'].items()):
  r['completion_waits'][kind]={'count':len(values),'max_frames':max(values),'total_frames':sum(values)}
 rows.append(r)
(BASE/'annotated-measurements.json').write_text(json.dumps(rows,indent=2)+'\n')
keys=['id','platform','case','status','emu_seconds','wall','cpu_seconds','cpu_percent','excluded_reason']
with (BASE/'measurements.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(rows)
lookup={r['id']:r for r in rows}
perf={}
for platform in ['as3k','neo']:
 perf[platform]={}
 for fs in [0,6,10]:
  a=[r for r in rows if r['id'].startswith('perf-') and r['platform']==platform and r.get('options',[])[-2:]==['-frameskip',str(fs)] and '-speed' not in r.get('options',[]) and not r.get('excluded_reason')]
  perf[platform][str(fs)]={'cpu_seconds':[r['cpu_seconds'] for r in a],'wall_seconds':[r['wall'] for r in a],
     'passed':sum(r['status']=='PASS' for r in a),'total':len(a),'cpu_median':statistics.median(r['cpu_seconds'] for r in a)}
summary={'date':'2026-11-19','trials':len(rows),'excluded_trials':sum(bool(r.get('excluded_reason')) for r in rows),
 'successful_prototypes':{k:lookup[k] for k in ['as3k-adaptive-natural','neo-adaptive-history-3-8','neo-adaptive-graphics-3-8','neo-adaptive-graphics-3-8-repeat','neo-adaptive-graphics-2-4','neo-adaptive-graphics-ram']},
 'rendering_benchmarks':perf,'maintained_test_changes':[]}
meta=json.loads((BASE/'metadata.json').read_text())
for name,digest in meta['sources'].items():
 p=ROOT/'betawise/tests/mame'/name
 if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()!=digest:summary['maintained_test_changes'].append(name)
summary['end_git']={repo:{'head':subprocess.check_output(['git','-C',str(ROOT/repo),'rev-parse','HEAD'],text=True).strip(),'status':subprocess.check_output(['git','-C',str(ROOT/repo),'status','--short'],text=True)} for repo in ['betawise','mame']}
# Another chat rebuilt the shared applet after every AS3000 trial finished.
p=ROOT/'betawise/applets/MicroPython/build/extra/MicroPython.OS3KApp'
summary['provenance']={'initial_applet_preserved':'inputs/MicroPython-extra.OS3KApp',
 'shared_applet_rebuilt_later_at':datetime.datetime.fromtimestamp(p.stat().st_mtime,ZoneInfo('America/Denver')).isoformat(),
 'as3k_trials_overlapping_later_rebuild':[r['id'] for r in rows if r['platform']=='as3k' and (BASE/'runs'/r['id']/'time.json').stat().st_mtime>p.stat().st_mtime],
 'mame_executables_unchanged':all(hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest for name,digest in meta['inputs'].items() if name.endswith('/mame') or name.endswith('/neodiag'))}
(BASE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'trials':len(rows),'excluded':summary['excluded_trials'],'perf':perf,'maintained_test_changes':summary['maintained_test_changes'],'provenance':summary['provenance']},indent=2))
