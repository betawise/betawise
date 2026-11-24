#!/usr/bin/env python3
"""Launch only when explicitly requested later. Prepared run required."""
import argparse,asyncio,contextlib,hashlib,importlib.util,json,os,struct,subprocess,sys
from pathlib import Path
from walk_fat import walk,compare
from catalog import catalogue
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];BASE=HERE.parent
spec=importlib.util.spec_from_file_location('packet_host',ROOT/'.research-work/asma3k-msc/src/run.py');common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
async def packet_checks(host,out):
 await host.request(1)
 async with asyncio.timeout(10):
  while not (await host.request(0))[1][3]&0x80:await asyncio.sleep(.002)
 dev=await host.control(0x80,6,0x100,n=18);assert dev[7]==8
 await host.control(0,5,7);await host.control(0,9,1)
 assert await host.control(0xa1,0xfe,n=1)==b'\0'
 capacity,_=await host.command(bytes([0x25])+bytes(9),8);assert struct.unpack('>II',capacity)==(4095,512)
 async def sector(lba):
  cdb=bytes([0x28,0])+struct.pack('>I',lba)+bytes([0,0,1,0]);data,_=await host.command(cdb,512);return data
 actual=await walk(sector);expected=json.loads((out/'expected.json').read_text());compare(actual,expected)
 before=await sector(0);cdb=bytes([0x2a])+bytes(6)+bytes([0,1,0]);await host.command(cdb,512,False,b'X'*512,want=1);assert await sector(0)==before
 return {'result':'PASS','files':len(actual['files']),'directories':actual['directories'],'sectors_read':actual['sectors_read']}
async def vhci_checks(host,out,leave_mounted=False):
 spec=importlib.util.spec_from_file_location('usbip_bridge',ROOT/'mame-usb/scripts/alphasmart/usbip.py');bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
 class LoggedChip(bridge.Chip):
  async def request(self,op,ep=0,data=b''):
   # Retain bridge cancellation/stream-draining semantics.
   result=await super().request(op,ep,data)
   host.log.write(json.dumps(dict(seq=self.sequence,op=op,ep=ep,out=data.hex(),status=result[0],data=result[1].hex()))+'\n');host.log.flush();host.count+=1
   return result
 chip=LoggedChip(host.r,host.w);export=bridge.Export(chip);await chip.request(1);await export.discover()
 server=await asyncio.start_server(export.client,'127.0.0.1',3241)
 try:
  (out/'vhci-ready.json').write_text(json.dumps({'port':3241,'busid':'1-1','vid':'081e','pid':'bdff'})+'\n')
  print('READY: sudo python3 '+str(HERE/'vhci_check.py')+' '+str(out)+(' --leave-mounted'if leave_mounted else ''),flush=True)
  await common.waitfile(out/'host-result.json',720);result=json.loads((out/'host-result.json').read_text());assert result['result']=='PASS',result
  if not leave_mounted:await common.waitfile(out/'host-detached')
  return result
 finally:
  if not leave_mounted or not(out/'host-result.json').exists()or json.loads((out/'host-result.json').read_text()).get('result')!='PASS':server.close();await server.wait_closed()
  else:host.server=server
async def execute(out,vhci,leave_mounted=False):
 config=json.loads((out/'prepared.json').read_text());assert not(out/'ready').exists(),'prepare a fresh run'
 assert hashlib.sha256((BASE/'build/msc.bin').read_bytes()).hexdigest()==config['build_sha256'],'re-prepare after rebuild'
 with(out/'mame.log').open('w')as log:
  command=list(config['command'])
  if leave_mounted:
   i=command.index('-seconds_to_run');del command[i:i+2]
  proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'SDL_VIDEODRIVER':'dummy'},cwd=out);host=None;result=None
  try:
   await common.waitfile(out/'ready',60);r,w=await asyncio.open_connection('127.0.0.1',config['packet_port']);host=common.Host(r,w,out)
   result=await(vhci_checks(host,out,leave_mounted)if vhci else packet_checks(host,out))
   if leave_mounted:
    (out/'keep-mounted').write_text('keep serving until explicit release\n');(out/'inspect').write_text('inspect\n');await common.waitfile(out/'inspected')
    expected=json.loads((out/'expected.json').read_text());before=(out/'native-before.ram').read_bytes();after=(out/'native-live.ram').read_bytes()
    for f in expected['files']:assert before[f['record']:f['record']+72]==after[f['record']:f['record']+72],'native record changed'
    assert catalogue(after,(out/'flash-memory.bin').read_bytes())==expected
    guest=json.loads((out/'guest-live.json').read_text());assert guest['rom_gpio_writes']==guest['rom_usb_reads']==0 and guest['telemetry'][2]==guest['telemetry'][16]==0
    (out/'results.json').write_text(json.dumps({'result':'PASS','host':result,'guest':guest,'native_records_unchanged':True,'left_mounted':True},indent=2)+'\n')
    print('PASS filesystem checks; LEFT MOUNTED at '+str(out/'mount'),flush=True);(out/'inspection-ready').write_text('mounted and serving\n')
    while not(out/'release').exists():
     assert proc.poll()is None,'MAME stopped during inspection'
     await asyncio.sleep(.5)
    if hasattr(host,'server'):host.server.close();await host.server.wait_closed()

   await host.request(6);(out/'stop').write_text('stop\n');await common.waitfile(out/'restored')
   before=(out/'native-before.ram').read_bytes();after=(out/'native-after.ram').read_bytes();expected=json.loads((out/'expected.json').read_text())
   for f in expected['files']:assert before[f['record']:f['record']+72]==after[f['record']:f['record']+72],'native record changed'
   assert catalogue(after,(out/'flash-memory.bin').read_bytes())==expected,'native content changed'
   guest=json.loads((out/'guest.json').read_text());assert guest['rom_gpio_writes']==guest['rom_usb_reads']==0 and guest['telemetry'][2]==guest['telemetry'][16]==0
   (out/'results.json').write_text(json.dumps({'result':'PASS','host':result,'guest':guest,'native_records_unchanged':True},indent=2)+'\n');print('PASS full AS3000 filesystem export; native records/content unchanged',flush=True)
  finally:
   if host:
    with contextlib.suppress(Exception):await host.request(6)
    (out/'stop').write_text('stop\n')
    with contextlib.suppress(Exception):await common.waitfile(out/'restored',5)
    host.log.close();host.w.close()
   (out/'quit').write_text('quit\n')
   try:await asyncio.to_thread(proc.wait,10)
   except subprocess.TimeoutExpired:
    proc.terminate()
    try:await asyncio.to_thread(proc.wait,3)
    except subprocess.TimeoutExpired:proc.kill();await asyncio.to_thread(proc.wait,3)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('out',type=Path);ap.add_argument('--vhci',action='store_true');ap.add_argument('--leave-mounted',action='store_true');ap.add_argument('--background',action='store_true');ap.add_argument('--status',action='store_true');args=ap.parse_args();assert not args.leave_mounted or args.vhci
 if args.status:
  import subprocess as status_process
  rows=status_process.check_output(['ps','-eo','pid,ppid,stat,etime,args'],text=True).splitlines()
  seeds=set()
  for row in rows:
   if str(args.out.resolve())in row and 'ps -eo'not in row:
    seeds.add(row.split()[0]);print(row)
  for row in rows:
   if len(row.split())>1 and row.split()[1]in seeds and row.split()[0]not in seeds:print(row)
  mount_probe=status_process.run(['findmnt','--mountpoint',str(args.out.resolve()/'mount')],capture_output=True,text=True)
  print(mount_probe.stdout)
  if(args.out/'release').exists():
   import socket as status_socket
   connection=None
   try:connection=status_socket.create_connection(('127.0.0.1',3241),timeout=1)
   except OSError:pass
   bridge_open=connection is not None
   if connection:connection.close()
   pid=int((args.out/'service.pid').read_text());process=Path('/proc')/str(pid)/'status'
   live=False
   if process.exists():
    state=next(line for line in process.read_text().splitlines()if line.startswith('State:'));live=state.split()[1]!='Z'
   report={'mounted':mount_probe.returncode==0,'bridge_listening':bridge_open,'service_running':live,'guest_restored':(args.out/'restored').exists()}
   (args.out/'shutdown-verified.json').write_text(json.dumps(report)+'\n');print(json.dumps(report))
  raise SystemExit(0)
 if args.background:
  command=[sys.executable,str(Path(__file__).resolve()),str(args.out.resolve())]+(['--vhci']if args.vhci else[])+(['--leave-mounted']if args.leave_mounted else[])
  with(args.out/'service.log').open('w')as log:proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  (args.out/'service.pid').write_text(str(proc.pid)+'\n');print('Started persistent test service:',proc.pid);raise SystemExit(0)
 asyncio.run(execute(args.out.resolve(),args.vhci,True)if args.leave_mounted else asyncio.wait_for(execute(args.out.resolve(),args.vhci),900))
