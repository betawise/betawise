#!/usr/bin/env python3
"""Independent protocol acceptance through Linux VHCI/libusb, not the packet
socket. This is our test host, explicitly distinct from stock-client acceptance.
"""
from pathlib import Path
import asyncio,ctypes as C,hashlib,json,struct,sys,time,subprocess
import run
out=Path(sys.argv[1]);from target import target
if (out/'reattach-request').exists():
 print('Waiting for replacement disposable emulator',flush=True)
 deadline=time.monotonic()+500
 while not(out/'reattach-ready').exists():
  assert time.monotonic()<deadline,'replacement deadline';time.sleep(.2)
 subprocess.run(['/usr/sbin/usbip','--tcp-port','3242','attach','-r','127.0.0.1','-b','1-1'],check=True)
 (out/'reattach-request').unlink();(out/'reattach-ready').unlink()
 deadline=time.monotonic()+30
 while True:
  try:bus,number=target();break
  except AssertionError:
   assert time.monotonic()<deadline;time.sleep(.1)
else:bus,number=target()
cfg=json.loads((out/'prepared.json').read_text())
lib=C.CDLL('libusb-1.0.so.0')
def bind(n,ret,args):f=getattr(lib,'libusb_'+n);f.restype=ret;f.argtypes=args;return f
ctx=C.c_void_p();assert bind('init',C.c_int,[C.POINTER(C.c_void_p)])(C.byref(ctx))==0
ptr=C.POINTER(C.c_void_p)();count=bind('get_device_list',C.c_ssize_t,[C.c_void_p,C.POINTER(C.POINTER(C.c_void_p))])(ctx,C.byref(ptr));bn=bind('get_bus_number',C.c_uint8,[C.c_void_p]);dn=bind('get_device_address',C.c_uint8,[C.c_void_p]);matches=[ptr[i]for i in range(count)if bn(ptr[i])==bus and dn(ptr[i])==number];assert len(matches)==1
handle=C.c_void_p();assert bind('open',C.c_int,[C.c_void_p,C.POINTER(C.c_void_p)])(matches[0],C.byref(handle))==0
claim=bind('claim_interface',C.c_int,[C.c_void_p,C.c_int]);assert claim(handle,0)==0
bulk=bind('bulk_transfer',C.c_int,[C.c_void_p,C.c_ubyte,C.c_void_p,C.c_int,C.POINTER(C.c_int),C.c_uint]);control=bind('control_transfer',C.c_int,[C.c_void_p,C.c_ubyte,C.c_ubyte,C.c_uint16,C.c_uint16,C.c_void_p,C.c_uint16,C.c_uint]);assert control(handle,0x21,0x66,0,0,None,0,10000)==0
class Host:
 def __init__(self):self.packets=[];self.timings=[]
 def transfer(self,ep,data_or_length):
  incoming=ep&128;length=data_or_length if incoming else len(data_or_length);buffer=C.create_string_buffer(length or 1)if incoming else C.create_string_buffer(data_or_length);actual=C.c_int();t=time.monotonic();status=bulk(handle,ep,buffer,length,C.byref(actual),60000);self.timings.append({'ep':ep,'length':length,'actual':actual.value,'seconds':time.monotonic()-t});assert status==0,(ep,status,actual.value);return buffer.raw[:actual.value]
 async def bulk_out(self,p):await asyncio.to_thread(self.transfer,1,p)
 async def packet(self,op,ep=0,p=b''):
  assert op==5 and ep==1
  if not self.packets:
   data=await asyncio.to_thread(self.transfer,0x81,65536);self.packets=[data[i:i+8]for i in range(0,len(data),8)]
   if len(data)%8==0:self.packets.append(b'')
  return self.packets.pop(0)
async def main():
 host=Host();mtp=run.MTP(host);await mtp.op(0x1001);await mtp.op(0x1002,[1]);await mtp.op(0x1005,[0x10001]);data,_=await mtp.op(0x1007,[0xffffffff,0,0]);handles=list(struct.unpack('<'+'I'*(len(data)//4),data))[1:];objects={h:run.info((await mtp.op(0x1008,[h]))[0])for h in handles};expected=json.loads((out/'expected.json').read_text())['files'];
 if cfg['writable']:
  for h,o in list(objects.items()):
   if o['name']in {'VHCI0.BIN','VHCI513.BIN','VHCI4096.BIN','K0.BIN','K513.BIN','K4096.BIN'}:
    await mtp.op(0x100b,[h]);del objects[h]
 ram=(out/'native-before.ram').read_bytes();verified=0
 for h,o in objects.items():
  if o['format']==0x3001:continue
  wanted=[f for f in expected if f['app']==o['parent']-0x10000 and ram[f['record']+52:f['record']+68].split(b'\0')[0].decode('latin1')==o['name']];assert len(wanted)==1;f=wanted[0];data,_=await mtp.op(0x1009,[h]);assert len(data)==f['length']and hashlib.sha256(data).hexdigest()==f['sha256'];verified+=1
 assert verified==len(expected)
 if cfg['writable']:
  for size in (0,513,4096):
   payload=bytes((i*43+11)&255 for i in range(size));_,p=await mtp.op(0x100c,[0x10001,0x10001],run.object_info(f'K{size}.BIN',size,0x10001));h=p[2];await mtp.op(0x100d,payload=payload);assert(await mtp.op(0x1009,[h]))[0]==payload;await mtp.op(0x100b,[h])
 await mtp.op(0x1003);result={'result':'PASS','client':'independent test host through Linux VHCI/libusb','files_verified':verified,'writable':cfg['writable'],'operations':mtp.timings,'transfers':host.timings};(out/'kernel-result.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS kernel MTP',flush=True)
try:asyncio.run(main())
finally:bind('release_interface',C.c_int,[C.c_void_p,C.c_int])(handle,0);bind('close',None,[C.c_void_p])(handle)
