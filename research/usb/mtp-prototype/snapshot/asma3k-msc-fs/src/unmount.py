#!/usr/bin/env python3
"""Unmount this experiment, detach only its recorded VHCI device, release service."""
import json,os,subprocess,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent
out=Path(sys.argv[1]).resolve();assert out.is_relative_to(BASE/'runs')and os.geteuid()==0,'Run with sudo for this experiment directory'
host=json.loads((out/'host-result.json').read_text());assert host['result']=='PASS'
mountpoint=out/'mount';assert str(mountpoint)==host['mountpoint']
def command(args):
 result=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=120)
 with(out/'shutdown.log').open('a')as f:f.write('$ '+' '.join(map(str,args))+'\n'+result.stdout+result.stderr)
 assert result.returncode==0,result.stderr
 return result.stdout
probe=subprocess.run(['findmnt','-n','-o','SOURCE,FSTYPE,OPTIONS','--mountpoint',str(mountpoint)],capture_output=True,text=True)
if probe.returncode==0:
 source,fs,options=probe.stdout.split();assert source=='/dev/'+host['block']and fs=='vfat'and 'ro'in options.split(',')
 command(['umount',mountpoint])
status=Path('/sys/devices/platform/vhci_hcd.0/status').read_text().splitlines()[1:]
rows=[r.split()for r in status if len(r.split())>=7 and int(r.split()[1])==host['vhci_port']]
assert len(rows)==1
if rows[0][2]!='004':
 assert rows[0][-1]==host['usb'],'VHCI port now belongs to a different device'
 command(['/usr/sbin/usbip','detach','-p',str(host['vhci_port'])])
(out/'release').write_text('unmounted and detached; stop service\n')
deadline=time.monotonic()+40
while not(out/'restored').exists()and time.monotonic()<deadline:time.sleep(.1)
assert(out/'restored').exists(),'Service release requested, but guest restoration has not completed'
(out/'shutdown.json').write_text(json.dumps({'unmounted':True,'detached':True,'guest_restored':True})+'\n')
print('Unmounted, detached, guest restored; emulator/bridge exiting.')
