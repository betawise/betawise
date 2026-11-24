#!/usr/bin/env python3
"""Reproduce host-only formatting experiments against already-built KJV data."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from report import collect

HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=args.output.resolve()
    root.mkdir(parents=True,exist_ok=False)
    paths={name:root/name for name in ['sidecars','compact','layouts','word','small','inline_type','inline_all','inline_pred_type','inline_pred_all','inline_check']}
    commands=[
        ('sidecars','measure.py',['--output',paths['sidecars']]),
        ('compact','compact.py',[paths['sidecars'],'--output',paths['compact']]),
        ('layouts','layout.py',['--output',paths['layouts']]),
        ('word','word_defaults.py',['--output',paths['word']]),
        ('small','small_huffman.py',['--output',paths['small']]),
    ]
    for name,projection,predicted in [('inline_type','typography',False),('inline_all','all_styles',False),('inline_pred_type','typography',True),('inline_pred_all','all_styles',True)]:
        options=['--projection',projection,'--output',paths[name]]
        if predicted:
            options+=['--word-defaults','book']
        commands.append((name,'inline.py',options))
    commands.append(('inline_check','verify_inline.py',[paths[n]for n in ['inline_type','inline_all','inline_pred_type','inline_pred_all']]+['--output',paths['inline_check']]))
    for name,program,options in commands:
        print('Running',name,flush=True)
        with (root/(name+'.log')).open('w')as log:
            subprocess.run([sys.executable,str(HERE/program),*map(str,options)],check=True,stdout=log,stderr=subprocess.STDOUT)
    result=collect(paths)
    (root/'results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result['recommended'],indent=2))


if __name__=='__main__':
    main()
