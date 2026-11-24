"""Independent, strict FAT12/VFAT reader for host-side acceptance checks."""
import hashlib,struct
async def walk(read_sector):
 cache={}
 async def sector(lba):
  if lba not in cache:
   b=await read_sector(lba);assert len(b)==512;cache[lba]=b
  return cache[lba]
 boot=await sector(0);assert boot[510:]==b'\x55\xaa'
 u16=lambda b,o:int.from_bytes(b[o:o+2],'little')
 bps=u16(boot,11);spc=boot[13];reserved=u16(boot,14);copies=boot[16];root_entries=u16(boot,17);total=u16(boot,19);spf=u16(boot,22)
 assert (bps,spc,copies,total)==(512,1,2,4096)
 root=reserved+copies*spf;root_sectors=(root_entries*32+511)//512;data=root+root_sectors;clusters=(total-data)//spc;assert clusters<4085
 async def fat(c):
  off=c+c//2;block=off//512;within=off%512
  a=await sector(reserved+block);b=await sector(reserved+spf+block);assert a==b,'FAT copies differ'
  x=a[within]
  if within==511:
   a2=await sector(reserved+block+1);b2=await sector(reserved+spf+block+1);assert a2==b2;y=a2[0]
  else:y=a[within+1]
  return ((x|y<<8)>>4 if c&1 else x|y<<8)&0xfff
 assert await fat(0)==0xff8 and await fat(1)==0xfff
 async def chain(c):
  result=[];seen=set()
  while c<0xff8:
   assert 2<=c<clusters+2 and c not in seen,(c,'bad/cyclic chain');seen.add(c);result.append(c);c=await fat(c)
  return result
 def checksum(alias):
  x=0
  for b in alias:x=(((x&1)<<7)+(x>>1)+b)&255
  return x
 def decode(entries):
  result=[];pending=[]
  for e in entries:
   if e[0]==0:assert not pending,'orphan LFN';break
   if e[0]==0xe5:assert not pending;continue
   if e[11]==0x0f:pending.append(e);continue
   if e[11]&8:assert not pending;continue
   alias=e[:11]
   if pending:
    n=pending[0][0]&31;assert len(pending)==n and pending[0][0]&0x40
    parts={}
    for i,p in enumerate(pending):
     assert p[0]==(n-i|(0x40 if i==0 else 0))and p[12]==0 and p[26:28]==b'\0\0'and p[13]==checksum(alias)
     parts[n-i]=p[1:11]+p[14:26]+p[28:32]
    raw=b''.join(parts[i]for i in range(1,n+1));units=struct.unpack('<'+'H'*(len(raw)//2),raw)
    end=units.index(0);assert all(v==0xffff for v in units[end+1:]);name=raw[:end*2].decode('utf-16le');pending=[]
   else:name=alias[:8].decode('ascii').rstrip()+('.'+alias[8:].decode('ascii').rstrip()if alias[8:].strip()else'')
   assert name not in {'','/'}and '/'not in name and '\\'not in name
   result.append((name,e))
  return result
 async def directory(c):
  if c==0:return [b[i:i+32]for lba in range(root,root+root_sectors)for b in[await sector(lba)]for i in range(0,512,32)]
  return [b[i:i+32]for cluster in await chain(c)for b in[await sector(data+cluster-2)]for i in range(0,512,32)]
 directories=[];files={};assigned=set()
 async def visit(c,prefix,depth):
  assert depth<=1,'unexpected nested directory'
  for name,e in decode(await directory(c)):
   if name in{'.','..'}:continue
   path=prefix+name;start=u16(e,26);size=int.from_bytes(e[28:32],'little');assert u16(e,20)==0
   if e[11]&0x10:directories.append(path);await visit(start,path+'/',depth+1)
   else:
    assert e[11]&1,'file must be read-only'
    seq=await chain(start)if start else[];assert len(seq)==(size+511)//512
    assert not set(seq)&assigned,'shared data cluster';assigned.update(seq)
    payload=b''.join([await sector(data+cluster-2)for cluster in seq]);assert payload[size:]==bytes(len(payload)-size),'file slack leaks native RAM'
    files[path]={'length':size,'sha256':hashlib.sha256(payload[:size]).hexdigest()}
 await visit(0,'',0)
 assert await sector(total-1)==bytes(512),'unallocated space must read as zero'
 return {'directories':sorted(directories),'files':files,'sectors_read':len(cache),'data_lba':data,'clusters':clusters}
def compare(actual,expected):
 assert actual['directories']==sorted(expected['directories']),('directory set',actual['directories'],expected['directories'])
 want={f['path']:{'length':f['length'],'sha256':f['sha256']}for f in expected['files']}
 assert actual['files']==want,('file contents/names differ',set(actual['files'])^set(want))
