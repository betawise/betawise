#!/usr/bin/env python3
"""One-shot administrator check of the isolated AS3000 virtual USB disk.
Attaches only localhost:3241/1-1. Reads only a block device under vhci_hcd
with the prototype's VID/PID and serial. Always unmounts and detaches.
"""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent
out=Path(sys.argv[1]).resolve()
assert out.is_relative_to(BASE/'runs') and out.is_dir()
assert os.geteuid()==0,'Run this one command with sudo'
assert not(out/'host-result.json').exists(),'Already checked; use a fresh run'
def run(args,timeout=30):
 p=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=timeout)
 with(out/'host-commands.log').open('a')as f:f.write('$ '+' '.join(map(str,args))+'\n'+p.stdout+p.stderr)
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
attached=False;mounted=False;port=None;result={'result':'FAIL'};mountpoint=out/'mount'
try:
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
 assert (b/'size').read_text().strip()=='64','Expected exactly 64 sectors'
 interfaces=[p for p in Path('/sys/bus/usb/devices').glob(usb.name+':*')if (p/'driver').exists()]
 assert any((p/'driver').resolve().name=='usb-storage'for p in interfaces),'usb-storage did not bind'
 for name in ['descriptors','uevent']:(out/('linux-usb-'+name)).write_bytes((usb/name).read_bytes())
 (out/'linux-block-uevent').write_bytes((b/'uevent').read_bytes())
 run(['dd','if='+str(dev),'of='+str(out/'linux-readback.img'),'bs=512','count=64','status=none'],120)
 actual=(out/'linux-readback.img').read_bytes();expected=(BASE/'build/disk.img').read_bytes();assert actual==expected,'Linux sector read differs'
 # An independent Linux FAT driver must read the file through this USB disk.
 mountpoint.mkdir(exist_ok=False)
 run(['mount','-t','vfat','-o','ro,nosuid,nodev,noexec',dev,mountpoint]);mounted=True
 text=(mountpoint/'README.TXT').read_bytes();root=expected[1536:2048];length=int.from_bytes(root[28:32],'little');assert text==expected[2048:2048+length]
 (out/'linux-README.TXT').write_bytes(text)
 options=run(['findmnt','-n','-o','FSTYPE,OPTIONS','--target',mountpoint]);assert options.split()[0]=='vfat'and 'ro'in options.split()[1].split(',')
 result={'result':'PASS','usb':usb.name,'block':b.name,'kernel_driver':'usb-storage','readonly':True,'sectors':64,'sha256':hashlib.sha256(actual).hexdigest(),'filesystem':'vfat','file':'README.TXT','mount_options':options.strip()}
 print('PASS Linux usb-storage: read-only 64-sector disk; all bytes match; Linux vfat read README.TXT',flush=True)
except BaseException as e:
 result={'result':'FAIL','error':repr(e)};print('FAIL',repr(e),flush=True)
finally:
 try:
  if mounted:run(['umount',mountpoint]);mounted=False
  if attached:
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
  (out/'host-detached').write_text('detached\n')
 except BaseException as e:result={'result':'FAIL','cleanup_error':repr(e),'previous':result}
 (out/'host-result.json').write_text(json.dumps(result,indent=2)+'\n')
 sys.exit(0 if result['result']=='PASS'else 1)
