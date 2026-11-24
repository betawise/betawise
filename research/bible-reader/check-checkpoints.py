#!/usr/bin/env python3
"""Verify compact codec resume points, including grammar and spelling context."""
import argparse,hashlib,json,subprocess
from prototype_support import prototype_app, prototype_test
from pathlib import Path
root=Path(__file__).resolve().parents[3];app=prototype_app();here=Path(__file__).resolve().parent
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--container',type=Path,default=root/'.research-work/bible-compression/reader/kjv/container.bin');ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=False)
dense=a.container.read_bytes()[:8]==b'KJVDNS01';binary=a.output/'checkpoint-check'
subprocess.run(['cc','-O2','-DBIBLE_HUFFMAN=1','-DBIBLE_RAW_ONLY=1','-DBIBLE_CHECKPOINTS=1',f'-DBIBLE_DENSE={int(dense)}','-I'+str(app),str(app/'HuffmanDecoder.c'),str(here/'checkpoint_check.c'),'-o',str(binary)],check=True)
result=subprocess.check_output([str(binary),str(a.container)],text=True);(a.output/'native.log').write_text(result);report=dict(status='passed',container_sha256=hashlib.sha256(a.container.read_bytes()).hexdigest(),result=result.strip(),target_codec_point_bytes=10,target_page_point_bytes=20);(a.output/'results.json').write_text(json.dumps(report,indent=2)+'\n');print(result,end='')
