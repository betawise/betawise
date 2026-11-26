#!/usr/bin/env python3
"""Record the production cached-layout change and fresh direct marker timings."""
import hashlib
import json
from pathlib import Path
import struct
from summarize import scan_timings

HERE=Path(__file__).resolve().parent
BUILD=HERE/'build'
APP=HERE.parents[2]/'applets/BibleWise'


def suite(name, timings=False):
    path=BUILD/name
    result=json.loads((path/'results.json').read_text())
    assert result['status']=='passed'
    row=dict(name=name,status='passed',checkpoints=result['checkpoints'])
    if timings:
        row['timings']=scan_timings(path)
    return row


def main():
    before=struct.unpack_from('>II',(BUILD/'cached-prod-before.OS3KApp').read_bytes(),4)
    after_image=(APP/'build/NKJV/BibleWise-NKJV.OS3KApp').read_bytes()
    after=struct.unpack_from('>II',after_image,4)
    production=[suite(name) for name in ('cached-prod-interactions','cached-prod-usage',
        'cached-prod-family-picker','cached-prod-kjv-pages-final','cached-prod-long-selection-v4',
        'cached-prod-system-focus','cached-prod-local-ui-fixed')]
    origin=json.loads((BUILD/'cached-prod-long-selection-v4/paging-origin-results.json').read_text())
    lookups=[suite(name,True) for name in ('cached-direct-marker-bench',
        'cached-direct-bmh-bench-aligned','cached-direct-binary-bench')]
    profile=suite('cached-layout-final-profile')
    relocation=suite('cached-layout-relocation-final')
    old_base,new_base=struct.unpack('>II',(BUILD/'cached-layout-relocation-final/file-relocation-03.bin').read_bytes())
    assert 0<old_base<0x80000 and 0<new_base<0x80000 and old_base!=new_base
    relocation.update(before_address=old_base,after_address=new_base,displacement=new_base-old_base)
    result=dict(status='passed',production=production,
        production_checkpoints=sum(item['checkpoints'] for item in production),
        paging_origin=origin,lookups=lookups,final_cached_profile=profile,allocation_stress=relocation,
        before=dict(rom=before[0],a5=before[1]),after=dict(rom=after[0],a5=after[1]),
        rom_delta=after[0]-before[0],a5_delta=after[1]-before[1],
        image_sha256=hashlib.sha256(after_image).hexdigest(),
        source_sha256=hashlib.sha256((APP/'BibleWise.c').read_bytes()).hexdigest(),
        scope='Production promotes only editable cached paging/focus. Font-provider changes retain the refresh/reflow fallback; built-in ROM System face can reuse cached layout. Production chapter offset tables and search formats are unchanged. Direct lookup alternatives remain research.',
        marker_comparison='Fresh direct-memory known-verse boundary reconstruction on cached-layout source; preceding-number pattern search shares gap handling and full parser with binary. Marker variants retain binary caret-position classification. KJV/NKJV have no missing verses; these patterns are not a generalized omitted-verse implementation.',
        validation_notes='Local-UI fixture updated only its key sequences for the family menu; font-ID and exact pixel assertions preserved. Earlier failed menu and page-origin fixtures retained, excluded from accepted totals. Direct BMH byte-pattern initializer explicitly aligned(2) after a compiler-emitted odd-address longword store fault.',
        research_reference='Historical variants use reference/BibleWise.c (post-batched-write, pre-cached-layout); cached-direct-* uses current production source. This prevents the historical preparation scripts from silently changing baseline UI.')
    (BUILD/'cached-adoption-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS',result['production_checkpoints'],'production checkpoints; ROM delta',result['rom_delta'],'A5 delta',result['a5_delta'])


if __name__=='__main__':
    main()
