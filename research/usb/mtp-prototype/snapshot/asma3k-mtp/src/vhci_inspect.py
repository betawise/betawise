#!/usr/bin/env python3
"""Attach only the prepared localhost PTP prototype; leave it for user inspection.
--detach releases only the recorded matching prototype and asks its server to exit.
No MTP/gphoto client is opened and no desktop discovery rules are changed.
"""
from pathlib import Path
import argparse,json,os,subprocess,time
BASE=Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser();p.add_argument('out',type=Path);p.add_argument('--detach',action='store_true');a=p.parse_args();out=a.out.resolve();assert out.is_relative_to(BASE/'runs')and os.geteuid()==0

def run(args):return subprocess.check_output(list(map(str,args)),text=True,stderr=subprocess.STDOUT,timeout=30)
def prototype():
 matches=[]
 for d in Path('/sys/bus/usb/devices').iterdir():
  try:
   if(d/'idVendor').read_text().strip()=='081e'and(d/'idProduct').read_text().strip()=='bdfd'and(d/'serial').read_text().strip()=='AS3KPTP1'and'vhci_hcd'in str(d.resolve()):matches.append(d)
  except(FileNotFoundError,NotADirectoryError):pass
 assert len(matches)<=1
 return matches[0]if matches else None
if a.detach:
 report=json.loads((out/'inspection.json').read_text());usb=prototype();rows=[r.split()for r in Path('/sys/devices/platform/vhci_hcd.0/status').read_text().splitlines()[1:]if len(r.split())>=7];row=next(r for r in rows if int(r[1])==report['vhci_port'])
 if row[2]!='004':
  assert usb and row[-1]==usb.name,'Recorded port now belongs to another device';print(run(['/usr/sbin/usbip','detach','-p',report['vhci_port']]))
 (out/'host-result.json').write_text(json.dumps({'result':'INSPECTED','inspection':report})+'\n');(out/'host-detached').write_text('detached by inspection helper\n');print('Detached; emulator will restore disposable state and exit.')
else:
 deadline=time.monotonic()+60
 while not(out/'vhci-ready.json').exists():
  assert time.monotonic()<deadline,'Bridge readiness deadline';time.sleep(.2)
 ready=json.loads((out/'vhci-ready.json').read_text());assert ready['pid']=='bdfd'and ready['port']==3242;assert prototype()is None,'Prototype already attached'
 print(run(['/usr/sbin/usbip','--tcp-port','3242','attach','-r','127.0.0.1','-b','1-1']))
 deadline=time.monotonic()+60;usb=None
 while not usb:
  assert time.monotonic()<deadline,'Enumeration deadline';usb=prototype();time.sleep(.1)
 props=run(['udevadm','info','--query=property','--path',usb]);(out/'udev-properties.txt').write_text(props);(out/'linux-descriptors.bin').write_bytes((usb/'descriptors').read_bytes())
 rows=[r.split()for r in Path('/sys/devices/platform/vhci_hcd.0/status').read_text().splitlines()[1:]if len(r.split())>=7];ports=[int(r[1])for r in rows if r[-1]==usb.name];assert len(ports)==1
 report={'usb':usb.name,'bus':int((usb/'busnum').read_text()),'device':int((usb/'devnum').read_text()),'vhci_port':ports[0],'personality':'plain PTP','readonly':True,'left_attached':True};(out/'inspection.json').write_text(json.dumps(report,indent=2)+'\n');print('Attached read-only AlphaSmart Files PTP. Open Thunar; no client or mount was forced.');print(json.dumps(report))
