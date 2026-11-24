#!/usr/bin/env python3
"""Exercise the installed, unmodified libmtp through a VHCI USB device.
ctypes layouts follow libmtp/src/libmtp.h.in; no custom MTP host is used here.
Only the supplied VHCI bus/device with 081e:bdfe may be opened.
"""
import ctypes as C,hashlib,json,os,sys,time
from pathlib import Path
out=Path(sys.argv[1]);bus,devnum=map(int,sys.argv[2:4]);writable=json.loads((out/'prepared.json').read_text())['writable'];timings=[]
class Entry(C.Structure):_fields_=[('vendor',C.c_char_p),('vid',C.c_uint16),('product',C.c_char_p),('pid',C.c_uint16),('flags',C.c_uint32)]
class Raw(C.Structure):_fields_=[('entry',Entry),('bus',C.c_uint32),('number',C.c_uint8)]
class File(C.Structure):pass
File._fields_=[('id',C.c_uint32),('parent',C.c_uint32),('storage',C.c_uint32),('name',C.c_char_p),('size',C.c_uint64),('modified',C.c_long),('type',C.c_int),('next',C.POINTER(File))]
lib=C.CDLL('libmtp.so.9')
def bind(name,ret,args):
 f=getattr(lib,'LIBMTP_'+name);f.restype=ret;f.argtypes=args;return f
init=bind('Init',None,[]);detect=bind('Detect_Raw_Devices',C.c_int,[C.POINTER(C.POINTER(Raw)),C.POINTER(C.c_int)]);open_device=bind('Open_Raw_Device_Uncached',C.c_void_p,[C.POINTER(Raw)]);release=bind('Release_Device',None,[C.c_void_p]);storage=bind('Get_Storage',C.c_int,[C.c_void_p,C.c_int]);listing=bind('Get_Files_And_Folders',C.POINTER(File),[C.c_void_p,C.c_uint32,C.c_uint32]);destroy=bind('destroy_file_t',None,[C.POINTER(File)]);download=bind('Get_File_To_File',C.c_int,[C.c_void_p,C.c_uint32,C.c_char_p,C.c_void_p,C.c_void_p]);upload=bind('Send_File_From_File',C.c_int,[C.c_void_p,C.c_char_p,C.POINTER(File),C.c_void_p,C.c_void_p]);delete=bind('Delete_Object',C.c_int,[C.c_void_p,C.c_uint32]);errors=bind('Dump_Errorstack',None,[C.c_void_p])
def timed(name,fn,*args):
 start=time.monotonic();r=fn(*args);timings.append({'stage':name,'seconds':time.monotonic()-start});(out/'libmtp-progress.json').write_text(json.dumps(timings));print(name,timings[-1]['seconds'],flush=True);return r
init();raw=C.POINTER(Raw)();n=C.c_int();assert timed('detect',detect,C.byref(raw),C.byref(n))==0
matches=[i for i in range(n.value)if(raw[i].entry.vid,raw[i].entry.pid,raw[i].bus,raw[i].number)==(0x081e,0xbdfe,bus,devnum)];assert len(matches)==1
mtp=timed('open',open_device,C.byref(raw[matches[0]]));assert mtp
try:
 assert timed('storage',storage,mtp,0)==0
 def files(parent):
  result=[];p=timed('list:'+hex(parent),listing,mtp,0x10001,parent)
  while p:
   f=p.contents;result.append({'id':f.id,'parent':f.parent,'name':f.name.decode(),'size':f.size,'type':f.type});q=C.cast(f.next,C.c_void_p).value;f.next=C.POINTER(File)();destroy(p);p=C.cast(q,C.POINTER(File))
  return result
 roots=files(0xffffffff);assert {f['name']for f in roots}=={'System','AlphaWord Plus','Keywords'},roots
 ram=(out/'native-before.ram').read_bytes();expected=json.loads((out/'expected.json').read_text())['files'];count=0;downloads=out/'downloads';downloads.mkdir(exist_ok=True)
 for folder in roots:
  entries=files(folder['id']);wanted={ram[f['record']+52:f['record']+68].split(b'\0')[0].decode('latin1'):f for f in expected if f['app']==folder['id']-0x10000};assert {f['name']for f in entries}==set(wanted)
  for f in entries:
   target=downloads/(str(f['id'])+'.bin');assert timed('download:'+str(f['size']),download,mtp,f['id'],os.fsencode(target),None,None)==0
   data=target.read_bytes();e=wanted[f['name']];assert len(data)==e['length']and hashlib.sha256(data).hexdigest()==e['sha256'];count+=1
 if writable:
  for length in (0,513,4096):
   name=f'VHCI{length}.BIN';payload=bytes((i*43+11)&255 for i in range(length));source=out/name;source.write_bytes(payload);f=File();f.parent=0x10001;f.storage=0x10001;f.name=name.encode();f.size=length;f.type=44 # LIBMTP_FILETYPE_UNKNOWN in installed ABI
   status=timed('upload:'+str(length),upload,mtp,os.fsencode(source),C.byref(f),None,None)
   if status:errors(mtp)
   assert status==0
   dest=downloads/('upload-'+str(length));assert timed('readback:'+str(length),download,mtp,f.id,os.fsencode(dest),None,None)==0;assert dest.read_bytes()==payload
   assert timed('delete:'+str(length),delete,mtp,f.id)==0
 else:
  # Confirm the existing client sees a read-only storage via the wire test;
  # do not ask it to delete an existing native document as a negative test.
  pass
 result={'result':'PASS','client':'system libmtp.so.9','files_verified':count,'writable':writable,'timings':timings}
 (out/'libmtp-result.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS libmtp',flush=True)
finally:timed('release',release,mtp)
