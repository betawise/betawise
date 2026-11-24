#!/usr/bin/env python3
"""Run m68k MSC guest against a deterministic USB packet host; no VHCI or root."""
from pathlib import Path
import argparse,asyncio,contextlib,hashlib,json,os,socket,struct,subprocess,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];BASE=HERE.parent
H=struct.Struct('!5I')
class Host:
 def __init__(self,r,w,out):self.r=r;self.w=w;self.seq=0;self.tag=0;self.log=(out/'packets.jsonl').open('w');self.count=0
 async def request(self,op,ep=0,p=b''):
  self.seq+=1;self.w.write(H.pack(0x44313150,self.seq,op,ep,len(p))+p);await self.w.drain()
  h=H.unpack(await asyncio.wait_for(self.r.readexactly(20),5));assert h[:2]==(0x44313150,self.seq)and h[3]==ep
  data=await self.r.readexactly(h[4]);self.log.write(json.dumps(dict(seq=self.seq,op=op,ep=ep,out=p.hex(),status=h[2],data=data.hex()))+'\n');self.log.flush();self.count+=1
  return h[2],data
 async def packet(self,op,ep=0,p=b'',stall=False):
  deadline=time.monotonic()+12
  while time.monotonic()<deadline:
   status,data=await self.request(op,ep,p)
   if status==0:return data
   if status==2 and stall:return None
   assert status==1,('packet error',op,ep,status)
   await asyncio.sleep(.001)
  raise TimeoutError(('packet deadline',op,ep))
 async def control(self,t,r,v=0,i=0,n=0,p=b'',stall=False):
  await self.packet(3,0,struct.pack('<BBHHH',t,r,v,i,n))
  if t&128:
   data=bytearray()
   while len(data)<n:
    part=await self.packet(5,stall=stall)
    if part is None:return None
    data.extend(part)
    if len(part)<8:break
   await self.packet(4);return bytes(data)
  for o in range(0,len(p),8):await self.packet(4,0,p[o:o+8])
  return await self.packet(5,stall=stall)
 async def bulk_out(self,p):
  for o in range(0,len(p),8):await self.packet(4,1,p[o:o+8])
 async def bulk_in(self,n):
  p=bytearray()
  while len(p)<n:
   b=await self.packet(5,1);p.extend(b)
   if len(b)<8:break
  return bytes(p)
 async def command(self,cdb,n=0,incoming=True,p=b'',want=0):
  self.tag+=1;cbw=struct.pack('<IIIBBB16s',0x43425355,self.tag,n,0x80 if incoming else 0,0,len(cdb),cdb)
  assert len(cbw)==31;await self.bulk_out(cbw)
  data=await self.bulk_in(n)if n and incoming else b''
  if n and not incoming:assert len(p)==n;await self.bulk_out(p)
  csw=await self.bulk_in(13);assert len(csw)==13,('CSW length',csw.hex())
  sig,tag,residue,status=struct.unpack('<IIIB',csw);assert(sig,tag,status)==(0x53425355,self.tag,want),(csw.hex(),want)
  if want==0:assert residue==max(0,n-len(data))if incoming else residue==0
  return data,residue
async def waitfile(p,timeout=30):
 async with asyncio.timeout(timeout):
  while not p.exists():await asyncio.sleep(.02)
async def execute(out,port):
 await waitfile(out/'ready');r,w=await asyncio.open_connection('127.0.0.1',port);host=Host(r,w,out);checks=[]
 def check(name,condition=True):assert condition,name;checks.append(name);print('PASS',name,flush=True)
 try:
  await host.request(1);await host.request(2)
  async with asyncio.timeout(10):
   while True:
    state=(await host.request(0))[1]
    if len(state)==4 and state[1] and state[3]&0x80:break
    await asyncio.sleep(.002)
  dev=await host.control(0x80,6,0x100,n=18);check('device descriptor',len(dev)==18 and dev[7]==8 and dev[8:12]==bytes.fromhex('1e08ffbd'))
  await host.control(0,5,7)
  async with asyncio.timeout(5):
   while (await host.request(0))[1][3]!=0x87:await asyncio.sleep(.001)
  check('SET_ADDRESS after status')
  cfg=await host.control(0x80,6,0x200,n=32);check('MSC interface + 8-byte bulk endpoints',len(cfg)==32 and cfg[14:17]==bytes([8,6,0x50]) and cfg[20:24]==bytes.fromhex('81020800') and cfg[27:31]==bytes.fromhex('01020800'))
  serial=await host.control(0x80,6,0x303,0x409,255);check('string descriptor',serial[2:].decode('utf-16le')=='AS3K0001')
  await host.control(0,9,1);check('SET_CONFIGURATION',await host.control(0x80,8,n=1)==b'\1')
  check('GET_MAX_LUN',await host.control(0xa1,0xfe,n=1)==b'\0')
  inquiry,_=await host.command(bytes([0x12,0,0,0,36,0]),36);check('SCSI INQUIRY',inquiry[8:16]==b'ALPHASMT')
  await host.command(bytes(6));check('SCSI TEST UNIT READY')
  capacity,_=await host.command(bytes([0x25])+bytes(9),8);check('SCSI READ CAPACITY',struct.unpack('>II',capacity)==(63,512))
  mode,_=await host.command(bytes([0x1a,0,0x3f,0,4,0]),4);check('SCSI write-protect bit',mode[2]&0x80)
  def read10(lba,count):return bytes([0x28,0])+struct.pack('>I',lba)+bytes([0])+struct.pack('>H',count)+bytes([0])
  image=(BASE/'build/disk.img').read_bytes()
  first,_=await host.command(read10(0,1),512);check('boot sector exactly matches independent image',first==image[:512])
  data,_=await host.command(read10(1,4),2048);check('multi-sector READ(10) including FAT/root/file',data==image[512:2560]);(out/'readback.img').write_bytes(first+data)
  root=data[1024:1536];check('FAT12 README directory',root[:11]==b'README  TXT');size=int.from_bytes(root[28:32],'little');text=data[1536:1536+size];(out/'README.TXT').write_bytes(text);check('file contents',text.startswith(b'AlphaSmart 3000 USB mass-storage prototype.'))
  bad,res=await host.command(read10(64,1),512,want=1);check('out-of-range read fails with full residue',bad==b'' and res==512)
  sense,_=await host.command(bytes([3,0,0,0,18,0]),18);check('illegal LBA sense',sense[2]==5 and sense[12]==0x21)
  write=bytes([0x2a,0])+struct.pack('>I',4)+bytes([0,0,1,0]);_,res=await host.command(write,512,False,b'X'*512,want=1);check('WRITE(10) rejected',res==512)
  sense,_=await host.command(bytes([3,0,0,0,18,0]),18);check('DATA PROTECT sense',sense[2]==7 and sense[12]==0x27)
  after,_=await host.command(read10(4,1),512);check('write did not change backing sector',after==image[2048:2560])
  # Invalid CBW must stall, then class reset + clear halt recovers.
  await host.bulk_out(b'BAD!'+bytes(27));check('malformed CBW stalls IN',await host.packet(5,1,stall=True)is None)
  check('endpoint reports halt',await host.control(0x82,0,i=0x81,n=2)==b'\1\0')
  await host.control(0x21,0xff);await host.control(2,1,i=0x81);await host.control(2,1,i=1);await host.command(bytes(6));check('BOT reset recovery')
  check('unsupported EP0 request stalls',await host.control(0x80,0x77,n=1,stall=True)is None)
  check('new SETUP recovers EP0',await host.control(0xa1,0xfe,n=1)==b'\0')
  await host.request(2)
  async with asyncio.timeout(5):
   while not (await host.request(0))[1][3]&0x80:await asyncio.sleep(.001)
  await host.control(0,5,3);await host.control(0,9,1);again,_=await host.command(read10(0,1),512);check('bus reset and re-enumeration',again==first)
  await host.request(6);(out/'stop').write_text('stop\n');await waitfile(out/'restored');guest=json.loads((out/'guest.json').read_text());check('no ROM-owned I2C during takeover',guest['rom_gpio_writes']==0);check('no ROM USB code during takeover',guest['rom_usb_reads']==0);check('guest has CPU interrupts enabled',guest['telemetry'][11]&0x700==0);check('USB IRQ5 specifically masked',guest['telemetry'][10]&0x100000);check('USB IRQ began unmasked',not guest['telemetry'][9]&0x100000);check('USB IRQ pending observed',guest['telemetry'][17]&0x100000);check('no I2C NACK errors',guest['telemetry'][2]==0)
  (out/'results.json').write_text(json.dumps({'result':'PASS','checks':checks,'packet_requests':host.count,'guest':guest,'device':dev.hex(),'configuration':cfg.hex()},indent=2)+'\n');(out/'quit').write_text('quit\n')
 finally:
  if not(out/'restored').exists():
   with contextlib.suppress(Exception):await host.request(6)
   (out/'stop').write_text('stop after test completion/failure\n')
   with contextlib.suppress(Exception):await waitfile(out/'restored',5)
  (out/'quit').write_text('quit\n')
  host.log.close();w.close();await w.wait_closed()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('out',type=Path);ap.add_argument('--port',type=int,default=13246);ap.add_argument('--timeout',type=int,default=180);args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);assert not(out/'ready').exists(),'use a fresh run directory'
 symbols=json.loads((BASE/'build/symbols.json').read_text());binary=BASE/'build/msc.bin';disk=BASE/'build/disk.img'
 script=(HERE/'load.lua.in').read_text()
 for k,v in {'OUT':json.dumps(str(out)),'BINARY':json.dumps(str(binary)),'DISK':json.dumps(str(disk)),'ENTRY':str(symbols['msc_main']),'BSS':str(0x30000+binary.stat().st_size),'DEADLINE':str(60*(args.timeout+30))}.items():script=script.replace('@'+k+'@',v)
 assert '@'not in script;(out/'load.lua').write_text(script)
 cmd=[ROOT/'mame-usb/asma3k','asma3k','-rompath',ROOT/'mame/roms','-nvram_directory',out/'nvram','-cfg_directory',out/'cfg','-video','none','-sound','none','-autoboot_delay','0','-autoboot_script',out/'load.lua','-usb',f'socket.127.0.0.1:{args.port}','-seconds_to_run',str(args.timeout+60)]
 with(out/'mame.log').open('w')as log:
  proc=subprocess.Popen(list(map(str,cmd)),stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'SDL_VIDEODRIVER':'dummy'},cwd=out)
  try:asyncio.run(asyncio.wait_for(execute(out,args.port),args.timeout));proc.wait(timeout=15)
  finally:
   if proc.poll()is None:
    proc.terminate()
    try:proc.wait(timeout=5)
    except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
 print('PASS prototype; artifacts:',out)
if __name__=='__main__':main()
