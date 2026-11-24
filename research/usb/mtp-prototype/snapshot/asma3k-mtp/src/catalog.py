"""Independent host catalogue for acceptance checks; never loaded into guest RAM."""
from pathlib import Path
import collections,gzip,hashlib,struct
APPS=32

def read_ram(path):
 p=Path(path);data=gzip.open(p,'rb').read()if p.suffix=='.gz'else p.read_bytes()
 assert len(data)==0x40000,'AS3000 capture must be exactly 256 KiB'
 return data

def catalogue(ram,flash):
 def u32(a):return struct.unpack_from('>I',ram,a)[0]
 def u16(a):return struct.unpack_from('>H',ram,a)[0]
 def text(b):return b.split(b'\0',1)[0]
 def file_at(p,name=None):
  assert 0x400<=p<=0x40000-72 and p%2==0
  address,length,_,capacity=struct.unpack_from('>4I',ram,p)
  assert length<=capacity and (not capacity or 0x400<=address<0x40000 and capacity<=0x40000-address)
  return dict(record=p,address=address,length=length,capacity=capacity,flags=u32(p+32),id=u16(p+68),tag=u16(p+70),name=name if name is not None else text(ram[p+52:p+68]))
 folders=[];owned_records=set()
 for a in range(APPS):
  p=u32(0xf42+8*a);count=ram[0xf46+8*a]
  assert not count or p%2==0 and 0x400<=p<=0x40000-count*72
  files=[file_at(p+72*i)for i in range(count)if p+72*i!=u32(0x344a)and u16(p+72*i+68)!=0xcb];owned_records.update(f['record']for f in files)
  h=u32(0xd82+4*a);name=b'APP';appid=0;present=bool(count or a==0)
  if h not in(0,0xffffffff):
   assert h%2==0 and 0x400000<=h<=0x4fff6c
   off=h-0x400000;assert flash[off:off+4]==bytes.fromhex('c0ffeead')
   appid=int.from_bytes(flash[off+20:off+22],'big');name=text(flash[off+24:off+60]);present=True
  if a==0:name=b'System'
  folders.append(dict(index=a,id=appid,name=name,present=present,files=files,table=p))
 folders=[f for f in folders if f['present']]
 def escaped(name):
  if not name:return 'FILE'
  result=''
  for i,c in enumerate(name):
   good=32<=c<127 and chr(c)not in '"*/:<>?\\|_~'and not(i==len(name)-1 and c in(32,46))
   result+=chr(c)if good else f'_{c:02X}'
  stem=result.split('.')[0].upper()
  if stem in {'CON','PRN','AUX','NUL',*[p+str(i)for p in('COM','LPT')for i in range(1,10)]}:result='_'+result
  return result
 def filename(f):
  n=escaped(f['name']);dot=f['name'].rfind(b'.')
  if not(0<dot<len(f['name'])-1):n+='.RAW'if f['flags']&4 else '.BIN'
  return n
 def disambiguate(names,ordinals,is_file):
  counts=collections.Counter(n.upper()for n in names);result=[]
  for n,i in zip(names,ordinals):
   if counts[n.upper()]>1:
    if is_file and '.'in n:stem,ext=n.rsplit('.',1);n=f'{stem}~{i:04X}.{ext}'
    else:n+=f'~{i:04X}'
   result.append(n)
  assert len({n.upper()for n in result})==len(result)
  return result
 dirnames=disambiguate([escaped(f['name'])for f in folders],[f['index']for f in folders],False)
 entries=[];directories=[]
 for folder,dirname in zip(folders,dirnames):
  directories.append(dirname)
  leaves=disambiguate([filename(f)for f in folder['files']],range(len(folder['files'])),True)
  for ordinal,(f,leaf)in enumerate(zip(folder['files'],leaves)):
   data=ram[f['address']:f['address']+f['length']]
   entries.append(dict(path=dirname+'/'+leaf,app=folder['index'],ordinal=ordinal,file_id=f['id'],tag=f['tag'],flags=f['flags'],record=f['record'],address=f['address'],length=f['length'],sha256=hashlib.sha256(data).hexdigest()))
 return {'directories':directories,'files':entries,'source':'native AS3000 records, raw logical bytes, no text conversion'}
