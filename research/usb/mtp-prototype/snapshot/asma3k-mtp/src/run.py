#!/usr/bin/env python3
"""MTP packet acceptance, with disposable firmware RAM and per-operation timings."""
from pathlib import Path
import argparse,asyncio,contextlib,hashlib,importlib.util,json,os,struct,subprocess,sys,time
import resources
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('packet_host',ROOT/'.research-work/asma3k-msc/src/run.py');common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
def container(kind,code,tid,body=b''):return struct.pack('<IHHI',12+len(body),kind,code,tid)+body
class TimedHost(common.Host):
 async def request(self,op,ep=0,p=b''):
  start=time.monotonic();status,data=await super().request(op,ep,p)
  self.log.write(json.dumps({'timing':True,'op':op,'ep':ep,'status':status,'seconds':time.monotonic()-start,'at':time.monotonic(),'bytes':len(p)+len(data)})+'\n')
  return status,data
class MTP:
 def __init__(self,host):self.host=host;self.tid=0;self.timings=[]
 async def receive(self):
  data=bytearray()
  while len(data)<12 or len(data)<struct.unpack_from('<I',data)[0]:
   p=await self.host.packet(5,1);assert p,('premature ZLP',bytes(data).hex());data.extend(p)
  n,kind,code,tid=struct.unpack_from('<IHHI',data);assert n==len(data)
  if n%8==0:assert await self.host.packet(5,1)==b''
  return kind,code,tid,bytes(data[12:])
 async def op(self,code,params=(),payload=None,want=0x2001):
  start=time.monotonic();self.tid+=1;tid=self.tid
  await self.host.bulk_out(container(1,code,tid,struct.pack('<'+'I'*len(params),*params)))
  if payload is not None:await self.host.bulk_out(container(2,code,tid,payload))
  a=await self.receive();data=b''
  if a[0]==2:
   assert a[1:3]==(code,tid);data=a[3];a=await self.receive()
  assert a[:3]==(3,want,tid),(hex(code),a,want)
  self.timings.append({'operation':hex(code),'seconds':time.monotonic()-start,'download_bytes':len(data),'upload_bytes':len(payload)if payload is not None else 0})
  return data,list(struct.unpack('<'+'I'*(len(a[3])//4),a[3]))
def string(data,off):
 n=data[off];return data[off+1:off+1+2*max(0,n-1)].decode('utf-16le'),off+1+2*n
def info(data):
 name,_=string(data,52);return dict(storage=struct.unpack_from('<I',data)[0],format=struct.unpack_from('<H',data,4)[0],size=struct.unpack_from('<I',data,8)[0],parent=struct.unpack_from('<I',data,38)[0],name=name)
def object_info(name,size,parent):
 b=bytearray(52);struct.pack_into('<IHHI',b,0,0x10001,0x3000,0,size);struct.pack_into('<I',b,38,parent);return bytes(b)+bytes([len(name)+1])+name.encode('utf-16le')+b'\0\0'+b'\0\0\0'
async def checks(host,out,writable):
 await host.request(1);await host.request(2)
 async with asyncio.timeout(15):
  while not(await host.request(0))[1][3]&0x80:await asyncio.sleep(.002)
 await asyncio.sleep(.05) # USB reset recovery, matching bridge discovery
 dev=await host.control(0x80,6,0x100,n=18);assert dev[7]==8
 cfg=await host.control(0x80,6,0x200,n=39);assert cfg[14:17]==b'\6\1\1'and cfg[32:]==bytes([7,5,0x82,3,8,0,16])
 await host.control(0,5,7);await host.control(0,9,1)
 mtp=MTP(host);device_info,_=await mtp.op(0x1001);
 if json.loads((Path(json.loads((out/'prepared.json').read_text())['build'])/'build.json').read_text()).get('plain_ptp'):
  assert dev[10:12]==bytes.fromhex('fdbd')and struct.unpack_from('<I',device_info,2)[0]==0
  serial=await host.control(0x80,6,0x303,0x409,255);assert serial[2:].decode('utf-16le')=='AS3KPTP1'
  assert await host.control(0x80,6,0x3ee,0,18,stall=True)is None
 await mtp.op(0x1002,[1]);await mtp.op(0x1004);storage,_=await mtp.op(0x1005,[0x10001]);assert struct.unpack_from('<H',storage,4)[0]==(0 if writable else 1)
 data,_=await mtp.op(0x1007,[0xffffffff,0,0]);handles=list(struct.unpack('<'+'I'*(len(data)//4),data))[1:];objects={}
 for h in ([] if os.getenv("MTP_QUICK") else handles):objects[h]=info((await mtp.op(0x1008,[h]))[0])
 ram=(out/'native-before.ram').read_bytes();expected=json.loads((out/'expected.json').read_text());bykey={(f['app'],f['ordinal']):f for f in expected['files']};actual=[]
 for h,o in ([] if os.getenv("MTP_QUICK") else objects.items()):
  if o['format']==0x3001:continue
  parent=o['parent'];folder=objects[parent]['name'];payload,_=await mtp.op(0x1009,[h]);matches=[f for f in expected['files']if f['app']==parent-0x10000 and ram[f['record']+52:f['record']+68].split(b'\0')[0].decode('latin1')==o['name']];assert len(matches)==1
  f=matches[0];assert len(payload)==o['size']==f['length']and hashlib.sha256(payload).hexdigest()==f['sha256'];actual.append(folder+'/'+o['name'])
 assert os.getenv('MTP_QUICK')or len(actual)==len(expected['files']);tests=['enumeration','all native file metadata and SHA256','clipboard excluded','8-byte header/data splits']
 if writable:
  async def event(code,h,tid=None):
   data=await host.packet(5,2);data+=await host.packet(5,2);assert data==container(4,code,mtp.tid if tid is None else tid,struct.pack('<I',h));assert await host.packet(5,2)==b''
  original_handles=objects.copy();made=[]
  for size in [0,1,7,8,9,127,128,129,511,512,513,4096]:
   name=f'T{size}.BIN';payload=bytes((i*73+19)&255 for i in range(size));_,p=await mtp.op(0x100c,[0x10001,0x10001],object_info(name,size,0x10001));h=p[2]
   await mtp.op(0x100d,payload=payload)
   await event(0x4002,h,mtp.tid-1 if size==0 else mtp.tid)
   data,_=await mtp.op(0x1009,[h]);assert data==payload;made.append((h,payload))
  tests+=['native FileCreate/write/read: zero, packet/chunk/sector boundaries and 4KiB binary']
  # Removing an early upload renumbers later native IDs. Existing MTP handles
  # must retain their identity, including objects created after that upload.
  await mtp.op(0x100b,[made[1][0]]);await event(0x4003,made[1][0])
  for h,payload in made[2:]:assert(await mtp.op(0x1009,[h]))[0]==payload
  await mtp.op(0x1008,[made[1][0]],want=0x2009)
  for h,_ in [made[0]]+made[2:]:
   await mtp.op(0x100b,[h]);await event(0x4003,h)
  tests+=['stable handles across delete/renumber','deleted handles rejected','interrupt EP2 ObjectAdded/Removed containers split over 8-byte packets and terminated by ZLP']
  await mtp.op(0x100c,[0x10001,0x10001],object_info('NameTooLong123456.BIN',10,0x10001),want=0xa806)
  await mtp.op(0x100c,[0x10001,0x10001],object_info('HUGE.BIN',0x30000,0x10001),want=0x200c)
  _,p=await mtp.op(0x100c,[0x10001,0x10001],object_info('CANCEL.BIN',4096,0x10001));cancelled=p[2]
  mtp.tid+=1;await host.bulk_out(container(1,0x100d,mtp.tid));await host.bulk_out(struct.pack('<IHHI',4108,2,0x100d,mtp.tid)+b'x'*128)
  await host.control(0x21,0x64,n=6,p=struct.pack('<HI',0x4001,mtp.tid));await mtp.op(0x1002,[2]);await mtp.op(0x1007,[0xffffffff,0,0]);tests+=['overlong name rejected','out-of-space rejected','partial upload cancelled through EP0']
 else:
  await mtp.op(0x100b,[257],want=0x2005);tests+=['write operations not advertised/rejected']
 await mtp.op(0x1003)
 return {'result':'PASS','tests':tests,'files':len(actual),'paths':actual,'operations':mtp.timings}
async def execute(out):
 cfg=json.loads((out/'prepared.json').read_text());log=(out/'mame.log').open('w');proc=subprocess.Popen(cfg['command'],stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'SDL_VIDEODRIVER':'dummy'},cwd=out,preexec_fn=resources.limits);watch=asyncio.create_task(resources.monitor(proc,out));host=None;start=time.monotonic()
 try:
  await common.waitfile(out/'ready',60);r,w=await asyncio.open_connection('127.0.0.1',cfg['packet_port']);host=TimedHost(r,w,out)
  result=await checks(host,out,cfg['writable']);await host.request(6);(out/'stop').write_text('stop\n');await common.waitfile(out/'restored',20)
  guest=json.loads((out/'guest.json').read_text());assert guest['telemetry'][2]==guest['telemetry'][16]==guest['rom_usb_reads']==guest['rom_gpio_writes']==0,guest
  from catalog import catalogue
  after_catalog=catalogue((out/'native-after.ram').read_bytes(),(out/'flash-memory.bin').read_bytes())
  key=lambda f:(f['path'],f['length'],f['sha256'])
  assert sorted(map(key,after_catalog['files']))==sorted(map(key,json.loads((out/'expected.json').read_text())['files'])),'original native files changed or incomplete upload leaked'
  if not cfg['writable']:
   before=(out/'native-before.ram').read_bytes();after=(out/'native-after.ram').read_bytes()
   for f in json.loads((out/'expected.json').read_text())['files']:
    q=f['record'];a=f['address'];n=f['length'];assert before[q:q+72]==after[q:q+72]and before[a:a+n]==after[a:a+n],'read-only native file modified' 
  result.update(guest=guest,wall_seconds=time.monotonic()-start,stack=json.loads((out/'stack.json').read_text()));(out/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
 finally:
  if host:
   with contextlib.suppress(Exception):await host.request(6)
   (out/'stop').write_text('stop\n')
   with contextlib.suppress(Exception):await common.waitfile(out/'restored',8)
   host.log.close();host.w.close()
  (out/'quit').write_text('quit\n')
  try:await asyncio.to_thread(proc.wait,10)
  except subprocess.TimeoutExpired:proc.kill();await asyncio.to_thread(proc.wait,5)
  watch.cancel();await asyncio.gather(watch,return_exceptions=True)
  log.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('out',type=Path);a=p.parse_args();asyncio.run(asyncio.wait_for(execute(a.out.resolve()),900))
