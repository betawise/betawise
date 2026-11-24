#!/usr/bin/env python3
"""One-shot administrator check of the isolated AS3000 virtual USB disk.
Attaches only localhost:3241/1-1. Reads only a block device under vhci_hcd
with the prototype's VID/PID and serial. Leaves a successful --leave-mounted run attached for inspection.
"""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent
out=Path(sys.argv[1]).resolve()
assert out.is_relative_to(BASE/'runs') and out.is_dir()
assert os.geteuid()==0,'Run this one command with sudo'
assert not(out/'host-result.json').exists(),'Already checked; use a fresh run'
def run(args,timeout=30):
 with(out/'host-commands.log').open('a')as f:f.write('$ '+' '.join(map(str,args))+'\n')
 started=time.monotonic()
 try:p=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=timeout)
 except subprocess.TimeoutExpired:
  with(out/'host-commands.log').open('a')as f:f.write('TIMEOUT after '+str(timeout)+' seconds\n')
  raise
 with(out/'host-commands.log').open('a')as f:f.write(p.stdout+p.stderr+'elapsed_seconds='+str(round(time.monotonic()-started,3))+'\n')
 assert p.returncode==0,(args,p.returncode,p.stderr)
 return p.stdout
def until(predicate,timeout=120):
 deadline=time.monotonic()+timeout
 while time.monotonic()<deadline:
  value=predicate()
  if value:return value
  time.sleep(.1)
 raise TimeoutError('Condition deadline')
def prototype():
 matches=[]
 for d in Path('/sys/bus/usb/devices').iterdir():
  try:
   if ((d/'idVendor').read_text().strip(),(d/'idProduct').read_text().strip(),(d/'serial').read_text().strip())==('081e','bdff','AS3K0001') and 'vhci_hcd' in str(d.resolve()):matches.append(d)
  except (FileNotFoundError,NotADirectoryError):pass
 assert len(matches)<=1,'Ambiguous prototype device'
 return matches[0]if matches else None
leave_mounted='--leave-mounted'in sys.argv[2:];attached=False;mounted=False;port=None;result={'result':'FAIL'};mountpoint=out/'mount'
try:
 if '--cleanup-stale'in sys.argv:
  stale=Path(sys.argv[sys.argv.index('--cleanup-stale')+1]).resolve();assert stale.is_relative_to(BASE/'runs')and stale!=out
  oldmount=stale/'mount'
  mounted_old=subprocess.run(['findmnt','-n','--mountpoint',str(oldmount)],capture_output=True,text=True)
  if mounted_old.returncode==0:run(['umount',oldmount],120)
 until(lambda:(out/'vhci-ready.json').exists(),600)
 config=json.loads((out/'vhci-ready.json').read_text());assert config['port']==3241 and config['busid']=='1-1'
 assert prototype()is None,'Prototype already attached'
 before=Path('/sys/devices/platform/vhci_hcd.0/status').read_text()
 run(['/usr/sbin/usbip','--tcp-port','3241','attach','-r','127.0.0.1','-b','1-1']);attached=True
 usb=until(prototype);device=usb.resolve()
 def block():
  found=list(device.glob('**/block/*'))
  found=[p for p in found if (p/'dev').is_file()]
  assert len(found)<=1,'Ambiguous block device'
  return found[0]if found else None
 b=until(block);dev=Path('/dev')/b.name
 until(lambda:dev.exists())
 major,minor=map(int,(b/'dev').read_text().split(':'));st=dev.stat()
 assert os.major(st.st_rdev)==major and os.minor(st.st_rdev)==minor
 assert (b/'ro').read_text().strip()=='1','Kernel must report read-only'
 assert (b/'size').read_text().strip()=='4096','Expected 4096 virtual sectors'
 interfaces=[p for p in Path('/sys/bus/usb/devices').glob(usb.name+':*')if (p/'driver').exists()]
 assert any((p/'driver').resolve().name=='usb-storage'for p in interfaces),'usb-storage did not bind'
 for name in ['descriptors','uevent']:(out/('linux-usb-'+name)).write_bytes((usb/name).read_bytes())
 (out/'linux-block-uevent').write_bytes((b/'uevent').read_bytes())
 # Read files through Linux FAT directly; do not spend time reading unused
 # virtual sectors or allocating a guest disk image.
 expected=json.loads((out/'expected.json').read_text())
 mountpoint.mkdir(exist_ok=False)
 run(['mount','-t','vfat','-o','ro,nosuid,nodev,noexec',dev,mountpoint],300);mounted=True
 actual_files={p.relative_to(mountpoint).as_posix():p for p in mountpoint.rglob('*')if p.is_file()}
 actual_dirs=sorted(p.relative_to(mountpoint).as_posix()for p in mountpoint.rglob('*')if p.is_dir())
 assert actual_dirs==sorted(expected['directories']),'directory set differs'
 assert set(actual_files)=={f['path']for f in expected['files']},'file set differs'
 for f in expected['files']:
  assert all(part not in {'','.', '..'}for part in Path(f['path']).parts)
  data=actual_files[f['path']].read_bytes();assert len(data)==f['length']and hashlib.sha256(data).hexdigest()==f['sha256'],f['path']
 options=run(['findmnt','-n','-o','FSTYPE,OPTIONS','--target',mountpoint]);assert options.split()[0]=='vfat'and 'ro'in options.split()[1].split(',')
 result={'result':'PASS','usb':usb.name,'block':b.name,'kernel_driver':'usb-storage','readonly':True,'sectors':4096,'filesystem':'vfat','files':len(actual_files),'directories':actual_dirs,'mount_options':options.strip(),'mountpoint':str(mountpoint),'left_mounted':leave_mounted}
 rows=Path('/sys/devices/platform/vhci_hcd.0/status').read_text().splitlines()[1:]
 candidates=[r.split()[1]for r in rows if len(r.split())>=7 and r.split()[-1]==usb.name];assert len(candidates)==1
 result['vhci_port']=int(candidates[0])
 print('PASS Linux usb-storage: all native files matched through the read-only FAT12 mount',flush=True)
except BaseException as e:
 result={'result':'FAIL','error':repr(e)};print('FAIL',repr(e),flush=True)
finally:
 try:
  mounted=mounted or subprocess.run(['findmnt','-n','--mountpoint',str(mountpoint)],capture_output=True).returncode==0
  if mounted and not(leave_mounted and result['result']=='PASS'):run(['umount',mountpoint]);mounted=False
  if attached and not(leave_mounted and result['result']=='PASS'):
   # Match only the new active VHCI port whose local bus ID is this prototype.
   usb=prototype()
   if usb:
    rows=Path('/sys/devices/platform/vhci_hcd.0/status').read_text().splitlines()[1:]
    candidates=[r.split()[1]for r in rows if len(r.split())>=7 and r.split()[-1]==usb.name]
    assert len(candidates)==1,('Cannot uniquely identify imported port',candidates)
    port=str(int(candidates[0]));run(['/usr/sbin/usbip','detach','-p',port])
   else:
    after=Path('/sys/devices/platform/vhci_hcd.0/status').read_text().splitlines()[1:]
    old={r.split()[1]:r.split()[2]for r in before.splitlines()[1:]if len(r.split())>=7}
    candidates=[r.split()[1]for r in after if len(r.split())>=7 and r.split()[2]!='004'and old.get(r.split()[1])=='004']
    assert len(candidates)==1,('Cannot identify failed import port',candidates)
    run(['/usr/sbin/usbip','detach','-p',str(int(candidates[0]))])
  if leave_mounted and result['result']=='PASS':(out/'host-mounted').write_text('left mounted read-only\n')
  else:(out/'host-detached').write_text('detached\n')
 except BaseException as e:result={'result':'FAIL','cleanup_error':repr(e),'previous':result}
 (out/'host-result.json').write_text(json.dumps(result,indent=2)+'\n')
 sys.exit(0 if result['result']=='PASS'else 1)
