#!/usr/bin/env python3
"""Unmodified gphoto2/libgphoto2 interoperability through the actual VHCI device."""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys,time
out=Path(sys.argv[1]);from target import target
bus,device=target();writable=json.loads((out/'prepared.json').read_text())['writable'];times=[]
base=['gphoto2','--debug','--debug-logfile',str(out/'gphoto-debug.log'),'--camera','USB PTP Class Camera','--port',f'usb:{bus:03},{device:03}']
def call(stage,args):
 t=time.monotonic();p=subprocess.run(base+list(map(str,args)),capture_output=True,text=True,timeout=180,env={**os.environ,'LC_ALL':'C'});times.append({'stage':stage,'seconds':time.monotonic()-t});(out/'gphoto-progress.json').write_text(json.dumps(times));print(stage,times[-1]['seconds'],flush=True)
 with(out/'gphoto.log').open('a')as f:f.write('$ '+' '.join(base+list(map(str,args)))+'\n'+p.stdout+p.stderr)
 assert p.returncode==0,(stage,p.returncode,p.stderr);return p.stdout
listing=call('enumerate',['--list-files','--recurse']);ram=(out/'native-before.ram').read_bytes();expected=json.loads((out/'expected.json').read_text())['files'];verified=0
for app,folder in [(1,'AlphaWord Plus'),(2,'Keywords')]:
 paths=re.findall(r"files? in folder '([^']*)'",listing);matches=[x for x in paths if x.endswith('/'+folder)];assert len(set(matches))==1,(folder,listing);remote=matches[0]
 dest=out/'gphoto-downloads'/folder;dest.mkdir(parents=True,exist_ok=True);call('download-folder:'+folder,['--folder',remote,'--get-all-files','--filename',str(dest/'%f'),'--force-overwrite'])
 for f in [x for x in expected if x['app']==app]:
  name=ram[f['record']+52:f['record']+68].split(b'\0')[0].decode('latin1');data=(dest/name).read_bytes();assert len(data)==f['length']and hashlib.sha256(data).hexdigest()==f['sha256'];verified+=1
 if writable and app==1:
  for leftover in ('VHCI0.BIN','VHCI513.BIN','VHCI4096.BIN'):
   if not(dest/leftover).exists()and not(dest/Path(leftover).stem).exists():continue
   current=call('list-empty-client-leftover',['--folder',remote,'--list-files']);ids=re.findall(r'^#(\d+)\s+'+re.escape(leftover)+r'(?:\s|$)',current,re.M);assert len(ids)==1;call('delete-empty-client-leftover',['--folder',remote,'--delete-file',ids[0]])
  for size in (513,4096):
   name=f'VHCI{size}.BIN';payload=bytes((i*43+11)&255 for i in range(size));source=out/name;source.write_bytes(payload)
   call('upload:'+str(size),['--folder',remote,'--upload-file',source])
   call('readback:'+str(size),['--folder',remote,'--get-all-files','--filename',str(dest/'%f'),'--force-overwrite']);assert(dest/Path(name).stem).read_bytes()==payload
   current=call('list-before-delete:'+str(size),['--folder',remote,'--list-files']);matches=re.findall(r'^#(\d+)\s+'+re.escape(name)+r'(?:\s|$)',current,re.M);assert len(matches)==1,(name,current);call('delete:'+str(size),['--folder',remote,'--delete-file',matches[0]])
result={'result':'PASS','client':'unmodified gphoto2/libgphoto2','writable':writable,'files_verified':verified,'empty_upload':'gphoto2 rejects zero-byte upload before sending data; independently validated via kernel_client','timings':times};(out/'gphoto-result.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS gphoto2',flush=True)
