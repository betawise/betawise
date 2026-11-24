#!/usr/bin/env python3
"""Record original-image anchors and reconstruct the statically traced Manager stream.

This is a read-only data-flow reconstruction, not an executed USB/flash update.
"""
from pathlib import Path
import hashlib,json,re,struct,subprocess,sys
HERE=Path(__file__).resolve().parent;WS=HERE.parents[3]
out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
host=WS/'Ghidra/NEOManager3_9_3USPC-extracted/payload/Program Files/AlphaSmart/AlphaSmart Manager 2/NEOManager.exe'
h=host.read_bytes()
# PE file offsets match RVA for this executable's text section.
# Whole-file size, seek-to-zero, read(1024), then staged block programming.
# Record relevant complete disassembly windows; no decompiler type assumptions.
host_dis=subprocess.check_output(['objdump','-d','-Mintel',str(host)],text=True)
(out/'host-updater.dis').write_text('\n'.join(l for l in host_dis.splitlines() if (m:=re.match(r'\s*([0-9a-f]+):',l)) and any(a<=int(m[1],16)<b for a,b in [(0x431049,0x4310e0),(0x43176b,0x4317be),(0x431cf7,0x432101),(0x438370,0x43843a)]))+'\n')
entries=json.loads((WS/'betawise/research/abi-audit/rom-inventory.json').read_text());rows=[]
for e in entries:
 b=(WS/e['path']).read_bytes();assert sha(b)==e['sha256']
 seg=[]
 for p in range(0x50,0x70,8):
  addr,n=struct.unpack_from('>II',b,p)
  if addr==n==0:break
  seg.append((addr,(n+1023)&~1023))
 cursor=0;maps=[]
 for addr,extent in seg:
  count=min(extent,len(b)-cursor);data=b[cursor:cursor+count]
  maps.append({'destination_begin':hex(addr),'erase_map_end_exclusive':hex(addr+extent),'stream_source_offset':hex(cursor),'stream_bytes':count,'stream_destination_end_exclusive':hex(addr+count),'device_program_bytes':0 if e['name']=='neo_3_21' and addr==0x5ffc00 else count,'sha256':sha(data),'not_sent_remainder_bytes':extent-count,'device_note':'NEO13 SmallROM 401DDC..401DE4 discards staged count for compatibility segment' if e['name']=='neo_3_21' and addr==0x5ffc00 else 'Count-driven program worker; no zero-tail trimming'})
  cursor+=count
 assert cursor==len(b),'package stream exceeds segment capacity'
 # Streaming does not elide zeros or FF. Track every block's checksum/hash.
 blocks=[]
 for p in range(0,len(b),1024):
  block=b[p:p+1024];blocks.append({'offset':p,'bytes':len(block),'sum16':sum(block)&65535,'sha256':sha(block)})
 (out/(e['name']+'-blocks.json')).write_text(json.dumps(blocks,indent=2)+'\n')
 rows.append({'name':e['name'],'package_sha256':sha(b),'package_bytes':len(b),'blocks':len(blocks),'last_block_bytes':len(b)%1024 or 1024,'stream_maps':maps})
small_cases=[('as3000','Alphasmart 3000','SMALLOS3KROM.OS3KOS',0x402c96,0x402e42),('neo_3_01','Alphasmart 3000','SMALLOS3KNeoROM.OS3KOS',0x402126,0x402304),('neo_3_21','Alphasmart Neo','smallos3kneorom.os3kos',0x401c10,0x4025b8)]
small_manifest=[]
for name,folder,filename,begin,end in small_cases:
 path=WS/'Ghidra'/folder/'SmartApplets'/filename
 dis=subprocess.check_output(['m68k-linux-gnu-objdump','-D','-b','binary','-m','m68k:68000','--adjust-vma=0x400000',f'--start-address={begin}',f'--stop-address={end}',str(path)],text=True)
 (out/(name+'-smallrom-program.dis')).write_text(dis)
 small_manifest.append({'name':name,'path':str(path.relative_to(WS)),'sha256':sha(path.read_bytes())})
manifest={'host_path':str(host.relative_to(WS)),'host_sha256':sha(h),'scope':'Static host/device trace and reconstructed entire-file stream; no USB or NOR execution','packages':rows,'smallroms':small_manifest}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
