#!/usr/bin/env python3
"""Serve sequential RO/RW disposable MAME instances for one VHCI approval."""
from pathlib import Path
import argparse,asyncio,contextlib,importlib.util,json,os,subprocess,time
import run
import resources
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('usbip_bridge',ROOT/'mame-usb/scripts/alphasmart/usbip.py');bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
async def serve_one(out):
 cfg=json.loads((out/'prepared.json').read_text());log=(out/'mame.log').open('w');proc=subprocess.Popen(cfg['command'],stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'SDL_VIDEODRIVER':'dummy'},cwd=out,preexec_fn=resources.limits);watch=asyncio.create_task(resources.monitor(proc,out));writer=None;start=time.monotonic();request_log=(out/'timings.jsonl').open('w')
 class MeasuredLock:
  def __init__(self):self.lock=asyncio.Lock();self.samples={}
  async def __aenter__(self):
   t=time.monotonic();await self.lock.acquire();self.enter=time.monotonic();self.wait=self.enter-t
  async def __aexit__(self,*args):
   self.samples[asyncio.current_task()]=(self.wait,time.monotonic()-self.enter);self.lock.release()
 class TimedChip(bridge.Chip):
  def __init__(self,*args):super().__init__(*args);self.lock=MeasuredLock()
  async def packet(self,op,ep=0,data=b''):
   while True:
    status,response=await self.request(op,ep,data)
    if status==0:return response
    if status!=1:raise bridge.USBError(-32 if status==2 else -19)
    t=time.monotonic();await asyncio.sleep(.001);request_log.write(json.dumps({'backoff':True,'seconds':time.monotonic()-t})+'\n')
  async def request(self,op,ep=0,data=b''):
   t=time.monotonic();status,payload=await super().request(op,ep,data);queue,wire=self.lock.samples.pop(asyncio.current_task(),(0,0));request_log.write(json.dumps({'at':time.monotonic(),'seconds':time.monotonic()-t,'queue_seconds':queue,'wire_seconds':wire,'op':op,'ep':ep,'status':status,'bytes':len(data)+len(payload),'out':data.hex(),'data':payload.hex()})+'\n');return status,payload
 class TimedExport(bridge.Export):
  async def bulk(self,direction,ep,data,length,flags=0):
   t=time.monotonic();result=await super().bulk(direction,ep,data,length,flags);request_log.write(json.dumps({'urb':True,'at':time.monotonic(),'seconds':time.monotonic()-t,'direction':direction,'ep':ep,'length':length,'actual':len(result)if direction else len(data)})+'\n');return result
 try:
  await run.common.waitfile(out/'ready',60);reader,writer=await asyncio.open_connection('127.0.0.1',cfg['packet_port']);chip=TimedChip(reader,writer);await chip.request(1);export=TimedExport(chip);await export.discover();server=await asyncio.start_server(export.client,'127.0.0.1',3242)
  (out/'vhci-ready.json').write_text(json.dumps({'port':3242,'busid':'1-1','vid':export.device[8:10][::-1].hex(),'pid':export.device[10:12][::-1].hex(),'ready_seconds':time.monotonic()-start}));print('READY',out,flush=True)
  try:await run.common.waitfile(out/'host-detached',cfg.get('inspection_timeout',1200))
  finally:server.close();await server.wait_closed()
  await chip.request(6);(out/'stop').write_text('stop\n');await run.common.waitfile(out/'restored',20)
  guest=json.loads((out/'guest.json').read_text());assert guest['telemetry'][2]==guest['telemetry'][16]==guest['rom_usb_reads']==guest['rom_gpio_writes']==0
  report={'guest':guest,'stack':json.loads((out/'stack.json').read_text()),'host':json.loads((out/'host-result.json').read_text())}
  if not cfg['writable']:
   before=(out/'native-before.ram').read_bytes();after=(out/'native-after.ram').read_bytes()
   for f in json.loads((out/'expected.json').read_text())['files']:
    a,n,q=f['address'],f['length'],f['record'];assert before[q:q+72]==after[q:q+72]and before[a:a+n]==after[a:a+n]
  report['result']=report['host']['result'];(out/'results.json').write_text(json.dumps(report,indent=2)+'\n');print('FINISHED',out,report['result'],flush=True)
 finally:
  request_log.close()
  (out/'stop').write_text('stop\n');(out/'quit').write_text('quit\n')
  if writer:writer.close()
  try:await asyncio.to_thread(proc.wait,10)
  except subprocess.TimeoutExpired:
   proc.kill();await asyncio.to_thread(proc.wait,5)
  watch.cancel();await asyncio.gather(watch,return_exceptions=True)
  log.close()
async def main(base):
 variants=('rw',)if(base/'rw-only').exists()else('ro','rw')
 for variant in variants:await serve_one(base/variant)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('batch',type=Path);p.add_argument('--background',action='store_true');a=p.parse_args();base=a.batch.resolve()
 if a.background:
  with(base/'service.log').open('w')as log:proc=subprocess.Popen(['python3',str(Path(__file__).resolve()),str(base)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  (base/'service.pid').write_text(str(proc.pid));print('Started',proc.pid)
 else:asyncio.run(main(base))
