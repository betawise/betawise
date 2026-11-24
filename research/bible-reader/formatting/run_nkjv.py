#!/usr/bin/env python3
"""Reproduce and summarize the NKJV host formatting comparison."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from measure import read_formatting, heading_chunks, uvarint, APP
from nkjv import make_file
from combine import layout_parts
from small_huffman import heading_pool

HERE=Path(__file__).resolve().parent


def collect(paths):
    def read(name):
        value=json.loads((paths[name]/'results.json').read_text())
        assert value['status']=='passed',name
        return value
    sidecars=read('sidecars')
    learned=read('learned')
    data=read_formatting('nkjv')
    best=learned['best']
    font=(paths['learned']/(best.replace('/','-')+'.bin')).read_bytes()
    style_header,styles=layout_parts(font,1)
    layout=(paths['sidecars']/('layout-'+sidecars['layout_best'].replace('/','-')+'.bin')).read_bytes()
    layout_header,layouts=layout_parts(layout)
    head_header,heads=heading_chunks(data['headings'],'front_pool')
    head_header,_=heading_pool(head_header)
    header=uvarint(len(style_header))+style_header+layout_header
    format_only,fs=make_file(data,header,styles=styles,layouts=layouts)
    full,hs=make_file(data,header,styles=styles,layouts=layouts,heading_header=head_header,headings=heads)
    inline={name:read(name)for name in ['inline','inline_book','inline_layout','inline_layout_book','inline_learned']}
    heading_bytes=sidecars['heading']['bytes']
    rows={}
    for name,key in [('rice_sidecar','book/rice'),('run_huffman_sidecar','none/runs_huffman_small'),('smallcaps_defaults_sidecar','book/runs_huffman_small')]:
        row=sidecars['styles'][key]
        rows[name]=dict(formatting_bytes=row['format_only_bytes'],with_headings_bytes=row['bytes'])
    winner=min((v for v in inline.values()if v['layout_mode']=='inline'),key=lambda v:v['combined_delta'])
    rows['all_inline_best']=dict(formatting_bytes=winner['combined_delta'],with_headings_bytes=winner['combined_delta']+heading_bytes)
    rows['learned_italics_smallcaps_sidecar']=dict(formatting_bytes=len(format_only),with_headings_bytes=len(full))
    verification=read('inline_check')
    return dict(status='passed',version='NKJV',source_sha256=data['source_sha256'],source_flags=data['flags'],
        extra_headings=sum(map(len,data['headings'])),generated_titles=data['generated_titles'],
        layout_events=sum(map(len,data['layout'])),rows=rows,
        best_model=dict(name=best,**learned['variants'][best]),
        layout=dict(name=sidecars['layout_best'],**sidecars['layout_candidates'][sidecars['layout_best']]),
        heading=sidecars['heading'],baseline_resource_bytes=sum((APP/'build/data/nkjv'/n).stat().st_size for n in sidecars['resource_hashes']),
        unchanged_sidecar_resource_hashes=sidecars['resource_hashes'],
        validation=dict(inline_search_cases=sum(v['production_search_cases']for v in inline.values()),
            inline_atoms_checked=sum(v['atoms_checked']for v in verification['trials'].values())),
        scope='Incremental data only, including model/index/padding bytes; redletter flags, footnotes, renderer code and font assets excluded.',
        artifacts={n:str(p)for n,p in paths.items()})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=args.output.resolve()
    root.mkdir(parents=True,exist_ok=False)
    names=['sidecars','learned','inline','inline_book','inline_layout','inline_layout_book','inline_learned','inline_check']
    paths={name:root/name for name in names}
    commands=[('sidecars','nkjv.py',['--output',paths['sidecars']]),('learned','learned.py',['--output',paths['learned']])]
    for name,defaults,mode,profile in [('inline','none','sidecar','translation'),('inline_book','book','sidecar','translation'),('inline_layout','book','inline','translation'),('inline_layout_book','book','inline','book'),('inline_learned','learned','inline','book')]:
        commands.append((name,'inline.py',['--version','nkjv','--projection','typography','--word-defaults',defaults,'--layout-mode',mode,'--layout-defaults',profile,'--output',paths[name]]))
    commands.append(('inline_check','verify_inline.py',[paths[n]for n in names[2:7]]+['--output',paths['inline_check']]))
    for name,program,options in commands:
        print('Running',name,flush=True)
        with(root/(name+'.log')).open('w')as log:
            subprocess.run([sys.executable,str(HERE/program),*map(str,options)],stdout=log,stderr=subprocess.STDOUT,check=True)
    report=collect(paths)
    (root/'results.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report['rows'],indent=2))


if __name__=='__main__':
    main()
