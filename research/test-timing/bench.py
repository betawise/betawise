"""Isolated research runner. It never edits maintained tests or original NVRAM."""
import argparse, ast, hashlib, importlib.util, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
ROOT=Path('/home/kirk/Projects/Alphasmart')
BASE=Path(__file__).resolve().parent
SRC=BASE/'sources'
sys.path.insert(0,str(SRC/'asneo'))
import neo_reader
FONT=ROOT/'betawise/applets/NeoFontTerminal/glyphs.png'
neo_reader.decode.__defaults__=(FONT,None)
neo_reader.stable_read.__defaults__=(FONT,2,None)
spec=importlib.util.spec_from_file_location('repl',SRC/'asneo/check-repl.py')
repl=importlib.util.module_from_spec(spec);spec.loader.exec_module(repl)


def instrument(script):
 script=script.replace('manager.machine:exit()', 'bench_exit()').replace('machine:exit()', 'bench_exit()')
 script=script.replace('emu.register_frame_done(function()', 'emu.register_frame_done(function() bench_frames=bench_frames+1')
 pre='''local bench_frames=0
local function bench_exit()
 print(string.format("BENCH time=%.9f frames=%d hz=%.6f",manager.machine.time:as_double(),bench_frames,manager.machine.screens[":screen"].refresh))
 manager.machine:exit()
end
'''
 return pre+'local function experiment()\n'+script+'\nend\nlocal ok,err=pcall(experiment);if not ok then print("FAIL setup: "..tostring(err));bench_exit() end\n'


def neo_script(job):
 s=repl.scenario(job.get('case','history'),'extra')
 lua=(SRC/'asneo/NeoHarness.lua').read_text()
 c=job.get('timing',{})
 hold=c.get('hold',6); step=c.get('step',24); gap=c.get('gap',12)
 lua=lua.replace('(hold or 6)',f'(hold or {hold})')
 lua=lua.replace('math.max(24,',f'math.max({step},').replace(f'(hold or {hold})+12',f'(hold or {hold})+{gap}')
 lua=lua.replace('wait(60)\n    at(t, capture)',f'wait({c.get("checkpoint",60)})\n    at(t, capture)')
 lua=lua.replace('t=t+24',f't=t+{c.get("capture_gap",24)}')
 if job.get('capture_fresh'):
  lua=lua.replace('local saved_cpu, saved_ram, saved_mode','local saved_cpu, saved_ram, saved_mode, saved_frameskip')
  lua=lua.replace('    capture_count = capture_count + 1','    saved_frameskip=machine.video.frameskip; machine.video.frameskip=0\n    capture_count = capture_count + 1')
  lua=lua.replace('            capture_tick = nil','            machine.video.frameskip=saved_frameskip\n            capture_tick = nil')
 if c.get('boot'):
  lua=lua.replace('local t = 1100','local t = 400')
  for old,new in [(150,60),(360,130),(740,240),(850,280),(910,310),(980,350)]:
   lua=lua.replace(f'press({old},',f'press({new},')
 if c.get("phase"):
  start=400 if c.get("boot") else 1100
  phase=c['phase']
  lua=lua.replace(f"local t = {start}",f"local t = {start+phase}")
 actions=[]
 for action in s.lua:
  match=re.fullmatch(r'wait\((\d+)\)',action)
  if match:
   n=int(match[1]); n=c.get('waits',{}).get(str(n),n)
   action=f'wait({n})'
  if c.get('interrupt_hold') is not None:
   action=action.replace(', 30)',f', {c["interrupt_hold"]})')
  actions.append(action)
 if job.get('adaptive'):
  from PIL import Image
  from logo_graphics import expected_image,SCENES
  original=(SRC/'asneo/NeoHarness.lua').read_text()
  prefix=original[:original.index('local function at(')]
  start=original.index('            if capture_tick then')
  end=original.index('            frame=frame+1',start)
  capture_ticks=original[start:end]
  engine=(BASE/'neo_adaptive.lua').read_text().replace('   -- CAPTURE_TICKS',capture_ticks)
  if job.get('ram'):
   engine=engine.replace('local function black(x,y) return (screen:pixel(x,y) & 0xffffff)==0x25302a end',(BASE/'neo_ram.lua').read_text())
   engine=engine.replace('local sig=screen:pixels()', 'local sig=refresh_lcd()')
   engine=engine.replace('then next_action();capture() end','then assert_ram_matches_screen();next_action();capture() end')

  font=Image.open(FONT).convert('L')
  glyphs={chr(code):''.join('1' if v<128 else '0' for v in font.crop((code*6,0,code*6+6,8)).getdata()) for code in range(32,127)}
  glyph_table='local glyphs={'+','.join('['+json.dumps(k)+']='+json.dumps(v) for k,v in glyphs.items())+'}\n'
  geometry={k:''.join('1' if v else '0' for v in expected_image(k).getdata()) for k in SCENES}
  geo_table='local graphics={'+','.join('['+json.dumps(k)+']='+json.dumps(v) for k,v in geometry.items())+'}\n'
  expected='local expectations={' + ','.join('{graphics='+json.dumps(x['graphics'])+'}' if 'graphics' in x else '{}' for x in s.checks)+'}\n'
  config=f'local key_hold={hold};local key_step={step};local key_gap={gap}\n'
  lua=prefix+glyph_table+geo_table+expected+config+engine
  actions=[a for a in actions if a not in ['run()']]
  # Suppress the static scheduler footer; this engine owns the dynamic timeline.
  return instrument(lua+'\n'+'\n'.join(actions)+'\nrun()\n'),s.checks
 return instrument(lua+'\n'+'\n'.join(actions)+'\nprint("SCHEDULE final="..t)\n'),s.checks


def as_script(job):
 helper=(SRC/'asma3k/asma3k.lua').read_text()
 scale=job.get('scale',1)
 helper=helper.replace('    assert(not events[frame]',f'    if frame >= 530 then frame=530+math.floor((frame-530)*{scale}+0.5) end\n    assert(not events[frame]')
 helper=helper.replace('                machine.video:snapshot()\n            end','                machine.video:snapshot(); bench_exit()\n            end')
 if job.get('native'):
  # Parse the driver's US PORT_CHAR table, preserving physical matrix injection.
  mapping={}; col=None
  source=(ROOT/'mame/src/mame/skeleton/alphasma3k.cpp').read_text()
  for line in source.splitlines():
   m=re.search(r'PORT_START\("COL\.(\d+)"\)',line)
   if m:col=int(m[1])
   m=re.search(r'PORT_BIT\((0x[0-9a-fA-F]+),',line)
   if col is None or not m:continue
   mask=int(m[1],16)
   chars=re.findall(r"PORT_CHAR\(('(?:\\.|[^'])+')\)",line)
   for i,value in enumerate(chars):
    ch=ast.literal_eval(value)
    
    if len(ch)==1 and ord(ch)<127 and (ord(ch)>=32 or ch in '\r\n\t\b'):mapping.setdefault(ch,[col,mask,i==1])
  mapping['_']=[3,0x10,True]
  mapping['\r']=[9,0x40,False]
  table='{'+','.join(f'[{json.dumps(k)}]={{{v[0]},{v[1]},{str(v[2]).lower()}}}' for k,v in mapping.items())+'}'
  start=helper.index('local function text(');end=helper.index('\nlocal function field(',start)
  step=job.get('step',6);hold=job.get('hold',2)
  new=f'''local native_map={table}
local function raw_field(col,mask)
 for _,f in pairs(machine.ioport.ports[":COL."..col].fields) do if f.mask==mask then return f end end
 error('field')
end
local function text(frame,characters)
 local first=frame < 530 and frame or 530+math.floor((frame-530)*{scale}+0.5)
 for i=1,#characters do
  local code=assert(native_map[characters:sub(i,i)],'unmapped key')
  local key=raw_field(code[1],code[2]);local shift=raw_field(14,1)
  local f=first+(i-1)*{step}
  assert(not events[f] and not events[f+{hold}], 'overlapping native text')
  events[f]=function() if code[3] then shift:set_value(1) end;key:set_value(1) end
  events[f+{hold}]=function() key:clear_value();if code[3] then shift:clear_value() end end
 end
end
'''
  helper=helper[:start]+new+helper[end:]
 case=job.get('case','repl')
 name={'repl':'MicroPythonRepl.lua','profile':'MicroPythonProfile.lua','mini':'MicroPythonRepl.lua','latency':'MicroPythonRepl.lua'}[case]
 body=(SRC/'asma3k'/name).read_text()
 if case=='mini':
  body='''local frame=530
local function enter(cmd,expected)
 text(frame,cmd.."\\r")
 frame=frame+#cmd*12+180
 at(frame,function() expect_text(expected) end)
 frame=frame+20
end
enter('x=0; print("BENCH",1)','BENCH 1')
enter('x+=1; print("BENCH",x)','BENCH 1')
enter('x+=1; print("BENCH",x)','BENCH 2')
at(frame,function() pass();manager.machine:exit() end)
run()
'''
 if case=='latency':
  commands=['x=1;print("LATENCY",1)']
  commands += [f'exec("for i in range(900):\\n t=list(range(12))");print("LATENCY",{n})' for n in range(2,5)]
  body='local commands={'+','.join(json.dumps(c) for c in commands)+'}\n'+'''
local frame,stage,posted,empty_at,next_frame=0,1,nil,nil,530
emu.register_frame_done(function()
 frame=frame+1
 local ok,err=pcall(function()
  if events[frame] then events[frame]() end
  if frame<next_frame then return end
  if not posted then
   machine.natkeyboard:post(commands[stage].."\\r")
   posted=frame;empty_at=nil
  else
   if machine.natkeyboard.empty and not empty_at then empty_at=frame end
   if empty_at and lcd():find('LATENCY '..stage,1,true) then
    print(string.format('LATENCY stage=%d queue_frames=%d ready_after_empty=%d total_frames=%d',stage,empty_at-posted,frame-empty_at,frame-posted))
    stage=stage+1;posted=nil;next_frame=frame+15
    if stage>#commands then print('PASS research-latency');manager.machine:exit() end
   end
  end
 end)
 if not ok then print('FAIL latency '..tostring(err));manager.machine:exit() end
end)
'''
 if job.get('gc_extra'):
  body=body.replace('frame = frame + 200\nenter(\'assert completionvalue',f'frame = frame + {200+job["gc_extra"]}\nenter(\'assert completionvalue')
 if job.get('adaptive'):
  reader=helper[helper.index('local function lcd()'):helper.index('local function pass()')]
  reader=reader.replace('    assert(screen:find(expected, 1, true)', '    if expected=="KeyboardInterrupt" then assert(screen:match(">>>%s*$"),"interrupt still running") end\n    assert(screen:find(expected, 1, true)')
  engine=(BASE/'as_adaptive.lua').read_text().replace('-- LCD_READER',reader)
  use_native=bool(job.get('native'))
  config='local use_native='+str(use_native).lower()+'\n'
  if use_native:
   match=re.search(r'local native_map=(.*)\nlocal function raw_field',helper)
   config+='local native_map='+match[1]+'\n'
   config+=f'local native_step={job.get("step",4)};local native_hold={job.get("hold",2)}\n'
  helper=config+engine
  body=body.replace('if not ok then manager.machine:exit(); error(err) end','if not ok then error(err) end')
  body=body.replace("enter('for i in range(900):\\r t=list(range(12))\\r', nil)", (BASE/'alloc_line.lua').read_text().strip())
 script='local variant="extra"\nlocal test_case="research-'+case+'"\n'+helper+body
 return instrument(script+'\nprint("SCHEDULE final="..frame)\n'),None


def run(job):
 out=BASE/'runs'/job['id'];out.mkdir(parents=True,exist_ok=False)
 platform=job['platform']
 if platform=='neo':
  for name in ['cfg','nvram','roms']:shutil.copytree(BASE/'neo-seed'/name,out/name,symlinks=True)
  script,checks=neo_script(job)
  (out/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
  exe=ROOT/'mame/neodiag';driver='asneo';rompath=str(out/'roms');extra=[]
 else:
  script,checks=as_script(job)
  (out/'cfg').mkdir();(out/'nvram').mkdir()
  exe=ROOT/'mame/mame';driver='asma3k'
  rompath=str(ROOT/'mame/roms')
  extra=['-applet',str(ROOT/'betawise/applets/MicroPython/build-extra/MicroPython.OS3KApp')]
 (out/'scenario.lua').write_text(script)
 options=job.get('options',['-nothrottle','-frameskip','0'])
 command=[str(exe),driver,'-noreadconfig','-rompath',rompath,'-cfg_directory',str(out/'cfg'),'-nvram_directory',str(out/'nvram'),
   '-snapshot_directory',str(out/'snap'),'-video','none','-sound','none','-skip_gameinfo',*options,*extra,
   '-autoboot_delay','0','-autoboot_script',str(out/'scenario.lua'),'-seconds_to_run',str(job.get('deadline',600))]
 (out/'job.json').write_text(json.dumps(dict(job,command=command),indent=2)+'\n')
 load_before=Path('/proc/loadavg').read_text().strip()
 before=time.perf_counter()
 try:
  with (out/'mame.log').open('w') as log:
   completed=subprocess.run(['/usr/bin/time','-f','{"wall":%e,"user":%U,"sys":%S,"maxrss":%M,"exit":%x}',
      '-o',str(out/'time.json'),*command],cwd=out,env=dict(os.environ,SDL_VIDEODRIVER='dummy'),stdout=log,stderr=subprocess.STDOUT,timeout=300)
  perf=json.loads((out/'time.json').read_text().splitlines()[-1])
  content=(out/'mame.log').read_text()
  if 'Out-of-range' in content:raise ValueError('unsupported requested option: '+content.splitlines()[0])
  if completed.returncode or 'LUA ERROR' in content or 'FAIL' in content:raise ValueError('MAME failure: '+content[-1800:])
  if platform=='neo':count=repl.verify(out,checks)
  else:
   if 'PASS research-' not in content:raise ValueError('no PASS: '+content[-1500:])
   count='full '+job.get('case','repl')
  status='PASS';error=None
 except Exception as e:
  perf=json.loads((out/'time.json').read_text().splitlines()[-1]) if (out/'time.json').exists() else {}
  content=(out/'mame.log').read_text();status='FAIL';error=str(e)
 telemetry=re.findall(r'BENCH time=([\d.]+) frames=(\d+) hz=([\d.]+)',content)
 result=dict(job,**perf,status=status,error=error,wall_measured=time.perf_counter()-before,load_before=load_before,load_after=Path('/proc/loadavg').read_text().strip())
 if telemetry:
  et,frames,hz=telemetry[-1];result.update(emu_seconds=float(et),frames=int(frames),hz=float(hz))
 cpu=result.get('user',0)+result.get('sys',0)
 result['cpu_seconds']=round(cpu,3)
 if result.get('wall'):result['cpu_percent']=round(cpu/result['wall']*100,1)
 (out/'measurement.json').write_text(json.dumps(result,indent=2)+'\n')
 with (BASE/'measurements.jsonl').open('a') as f:f.write(json.dumps(result)+'\n')
 print(json.dumps(result),flush=True)
 return result


if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('jobs',type=Path);args=parser.parse_args()
 for job in json.loads(args.jobs.read_text()):run(job)
