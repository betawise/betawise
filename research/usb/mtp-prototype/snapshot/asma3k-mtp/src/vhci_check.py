#!/usr/bin/env python3
"""One approval: attach RO then RW localhost MTP prototypes, run installed
libmtp against their exact VHCI bus/device, detach each even on failure.
No mounts, physical USB devices, real RAM sessions or flash writes.
"""
from pathlib import Path
import argparse,json,os,subprocess,sys,time
HERE=Path(__file__).resolve().parent;BASE=HERE.parent
p=argparse.ArgumentParser();p.add_argument('batch',type=Path);a=p.parse_args();batch=a.batch.resolve();assert batch.is_relative_to(BASE/'runs')and os.geteuid()==0
# Bound helper lifetime even if a client/library blocks indefinitely.
def until(fn,timeout=120):
 deadline=time.monotonic()+timeout
 while time.monotonic()<deadline:
  r=fn()
  if r:return r
  time.sleep(.1)
 raise TimeoutError('deadline')
def prototype():
 found=[]
 for d in Path('/sys/bus/usb/devices').iterdir():
  try:
   if (d/'idVendor').read_text().strip()=='081e'and(d/'idProduct').read_text().strip()=='bdfe'and(d/'serial').read_text().strip()=='AS3KMTP1'and'vhci_hcd'in str(d.resolve()):found.append(d)
  except(FileNotFoundError,NotADirectoryError):pass
 assert len(found)<=1
 return found[0]if found else None
for mode in ('ro','rw'):
 out=batch/mode;timings=[];attached=False;result={'result':'FAIL'};before={}
 def stage(name,fn):
  t=time.monotonic()
  try:return fn()
  finally:timings.append({'stage':name,'seconds':time.monotonic()-t})
 def command(args,timeout=40):
  with(out/'host-commands.log').open('a')as f:
   f.write('$ '+' '.join(map(str,args))+'\n');f.flush();subprocess.run(list(map(str,args)),stdout=f,stderr=subprocess.STDOUT,timeout=timeout,check=True)
 try:
  until(lambda:(out/'vhci-ready.json').exists(),1200);assert prototype()is None
  before={r.split()[1]:r.split()[2]for r in Path('/sys/devices/platform/vhci_hcd.0/status').read_text().splitlines()[1:]if len(r.split())>=7}
  stage('usbip_attach',lambda:command(['/usr/sbin/usbip','--tcp-port','3242','attach','-r','127.0.0.1','-b','1-1']));attached=True
  usb=stage('kernel_enumeration',lambda:until(prototype));(out/'linux-descriptors.bin').write_bytes((usb/'descriptors').read_bytes())
  assert not list(usb.resolve().glob('**/block/*')),'MTP must not create a block disk'
  bus=int((usb/'busnum').read_text());number=int((usb/'devnum').read_text())
  clients={}
  for client in ('gphoto','kernel'):
   try:
    stage(client+'_client',lambda:command([sys.executable,HERE/(client+'_client.py'),out,bus,number],600));clients[client]=json.loads((out/(client+'-result.json')).read_text())
   except BaseException as e:clients[client]={'result':'FAIL','error':repr(e)}
  if any(r['result']!='PASS'for r in clients.values()):
   (out/'client-failed.json').write_text(json.dumps(clients,indent=2));print(mode,'client failed; holding attachment for diagnostics for up to 10 minutes',flush=True)
   deadline=time.monotonic()+600
   while time.monotonic()<deadline:
    retry=out/'retry-clients'
    if retry.exists():
     name=retry.read_text().strip();retry.unlink()
     if name=='finish':break
     assert name in ('gphoto','kernel')
     try:
      stage(name+'_retry',lambda:command([sys.executable,HERE/(name+'_client.py'),out,bus,number],600));clients[name]=json.loads((out/(name+'-result.json')).read_text())
     except BaseException as e:clients[name]={'result':'FAIL','error':repr(e)}
     (out/'client-failed.json').write_text(json.dumps(clients,indent=2))
     if all(r['result']=='PASS'for r in clients.values()):break
    time.sleep(.2)
  result={'result':'PASS'if all(r['result']=='PASS'for r in clients.values())else'FAIL','mode':mode,'usb':usb.name,'clients':clients}

 except BaseException as e:result={'result':'FAIL','mode':mode,'error':repr(e)};print(mode,'FAIL',repr(e),flush=True)
 finally:
  if attached:
   usb=prototype();rows=Path('/sys/devices/platform/vhci_hcd.0/status').read_text().splitlines()[1:]
   ports=[r.split()[1]for r in rows if len(r.split())>=7 and((usb and r.split()[-1]==usb.name)or(not usb and r.split()[2]!='004'and before.get(r.split()[1])=='004'))];assert len(ports)==1,ports
   stage('usbip_detach',lambda:command(['/usr/sbin/usbip','detach','-p',str(int(ports[0]))]))
  result['timings']=timings;(out/'host-result.json').write_text(json.dumps(result,indent=2)+'\n');(out/'host-detached').write_text('detached\n');print(mode,result['result'],flush=True)
