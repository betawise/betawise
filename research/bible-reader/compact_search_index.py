#!/usr/bin/env python3
"""Pack host experimental index records to 32 bits and terminal IDs to 14 bits."""
import argparse,json,struct
from pathlib import Path

def pack14(values):
 out=bytearray();acc=bits=0
 for n in values:
  assert 0<=n<16384
  acc=(acc<<14)|n;bits+=14
  while bits>=8:bits-=8;out.append((acc>>bits)&255)
 if bits:out.append((acc<<(8-bits))&255)
 return bytes(out)
def unpack14(b,count):
 values=[];acc=bits=0
 for c in b:
  acc=(acc<<8)|c;bits+=8
  while bits>=14 and len(values)<count:bits-=14;values.append((acc>>bits)&16383)
 assert len(values)==count
 return values

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('experiment',type=Path);a=ap.parse_args();report=json.loads((a.experiment/'results.json').read_text());results=[]
 for record in report['index_experiments']:
  if record['kind']!='hybrid':continue
  group=record['group'];old=(a.experiment/f'index-hybrid-group{group}.bin').read_bytes();magic,nw,nt,g,np=struct.unpack_from('>8sHHII',old)
  assert magic==b'IDXEXP01'and g==group and nw+2<16384 and nt<16384 and np<1<<18
  records=[]
  for j in range(nw+1):
   term=int.from_bytes(old[20+5*j:22+5*j],'big');offset=int.from_bytes(old[22+5*j:25+5*j],'big');assert term<1<<14 and offset<1<<18;records.append((term<<18)|offset)
  mapstart=20+5*(nw+1);mapping=list(struct.unpack_from('>'+str(nt)+'H',old,mapstart));compact=[nw if x==65534 else nw+1 if x==65535 else x for x in mapping]
  table=pack14(compact);payload=old[mapstart+2*nt:];assert len(payload)==np
  new=struct.pack('>8sHHII',b'IDXEXP02',nw,nt,group,np)+struct.pack('>'+str(len(records))+'I',*records)+table+payload
  path=a.experiment/f'index-packed-group{group}.bin';path.write_bytes(new);saved=path.read_bytes();assert saved[20:20+4*(nw+1)]==struct.pack('>'+str(len(records))+'I',*records)
  unmap=unpack14(saved[20+4*(nw+1):20+4*(nw+1)+len(table)],nt);assert unmap==compact and saved[-np:]==payload
  for j in range(nw+1):
   val=struct.unpack_from('>I',saved,20+4*j)[0];assert val>>18==int.from_bytes(old[20+5*j:22+5*j],'big')and val&((1<<18)-1)==int.from_bytes(old[22+5*j:25+5*j],'big')
  r=dict(record,kind='packed-hybrid',bytes=len(new),all_packed_fields_roundtrip_exact=True,field_savings_bytes=len(old)-len(new));results.append(r);print(group,len(new),flush=True)
 (a.experiment/'compact-results.json').write_text(json.dumps(results,indent=2)+'\n')
if __name__=='__main__':main()
