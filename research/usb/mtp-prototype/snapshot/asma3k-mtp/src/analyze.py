#!/usr/bin/env python3
from pathlib import Path
import collections,json,statistics
HERE=Path(__file__).resolve().parent;BASE=HERE.parent
result={}
for name,build in [('FAT12 read-only',BASE.parent/'asma3k-msc-fs/build'),('MTP read-only',BASE/'build-ro'),('MTP read-write',BASE/'build-rw')]:result[name]=json.loads((build/'build.json').read_text())
old=BASE/'runs/vhci-v3';new=BASE/'runs/vhci-v5/rw'
client=json.loads((old/'rw/kernel-result.json').read_text());group=collections.defaultdict(list)
for r in client['operations']:group[r['operation']].append(r)
result['vhci_kernel_operations']={op:{'count':len(rows),'total_seconds':sum(r['seconds']for r in rows),'median_seconds':statistics.median(r['seconds']for r in rows),'download_bytes':sum(r['download_bytes']for r in rows),'upload_bytes':sum(r['upload_bytes']for r in rows)}for op,rows in group.items()}
rows=[json.loads(x)for x in(new/'timings.jsonl').read_text().splitlines()];packets=[r for r in rows if r.get('op')in(4,5)and r.get('ep')==1];nak=[r for r in packets if r['status']==1];backoff=[r for r in rows if r.get('backoff')];urbs=[r for r in rows if r.get('urb')and r['ep']==1]
result['vhci_bridge']={'bulk_packet_requests':len(packets),'nak_requests':len(nak),'nak_fraction':len(nak)/len(packets),'packet_socket_seconds':sum(r['wire_seconds']for r in packets),'socket_seconds_on_nak':sum(r['wire_seconds']for r in nak),'backoff_seconds':sum(r['seconds']for r in backoff),'queue_wait_seconds':sum(r['queue_seconds']for r in packets),'bulk_urbs':len(urbs),'median_socket_request_ms':1000*statistics.median(r['wire_seconds']for r in packets),'note':'Combined independent-host and gphoto diagnostics, excludes idle status polling; queue/backoff may overlap other tasks, so totals are not an exclusive partition.'}
result['ro_host_stages']=json.loads((old/'ro/host-result.json').read_text())['timings']
result['rw_gphoto_stages']=json.loads((old/'rw/gphoto-progress.json').read_text())
for run in [BASE/'runs/resource-ro-v1',new,BASE/'runs/final-rw-v2']:
 if(run/'resources.jsonl').exists():
  rr=[json.loads(x)for x in(run/'resources.jsonl').read_text().splitlines()];result.setdefault('resources',{})[run.name]={'rss_peak_kib':max(r['rss_kib']for r in rr),'swap_peak_kib':max(r['swap_kib']for r in rr),'cpu_percent_median':statistics.median(r['cpu_percent']for r in rr if r['cpu_percent']is not None)}
 if(run/'stack.json').exists():result.setdefault('stack',{})[run.name]=json.loads((run/'stack.json').read_text())
fat_stack=BASE.parent/'asma3k-msc-fs/runs/footprint-v3/stack.json'
if fat_stack.exists():result.setdefault('stack',{})['FAT12 read-only']=json.loads(fat_stack.read_text())
(BASE/'comparison.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['vhci_kernel_operations'],indent=2));print(json.dumps(result['vhci_bridge'],indent=2))
