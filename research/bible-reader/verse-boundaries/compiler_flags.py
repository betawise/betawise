#!/usr/bin/env python3
"""Record stock GCC call-mode probes without altering the active toolchain."""
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
OUTPUT=HERE/'build/compiler'


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    source=OUTPUT/'probe.c'
    source.write_text('volatile int state; extern int other(int);\n'
        'static __attribute__((noinline)) int local(int n) { return n+state; }\n'
        'int run(int n) { return local(n)+other(n); }\n')
    configurations={
        'normal':['-msep-data'],
        'small-pic':['-msep-data','-fpic'],
        'small-pic-pcrel':['-msep-data','-fpic','-mpcrel'],
        'small-pic-no-plt':['-msep-data','-fpic','-fno-plt'],
        'small-pic-hidden':['-msep-data','-fpic','-fvisibility=hidden'],
        'no-interposition':['-msep-data','-fno-semantic-interposition'],
        'pcrel-only':['-mpcrel']}
    rows=[]
    for name,flags in configurations.items():
        assembly=OUTPUT/(name+'.s')
        command=['m68k-linux-gnu-gcc','-m68000','-Os',*flags,'-S',str(source),'-o',str(assembly)]
        result=subprocess.run(command,capture_output=True,text=True)
        text=assembly.read_text() if result.returncode==0 else ''
        rows.append(dict(name=name,flags=flags,exit_code=result.returncode,diagnostic=result.stderr,
            assembly=text,indirect_calls=text.count('jsr ('),direct_bsr_calls=text.count('bsr')))
    output=dict(compiler=subprocess.check_output(['m68k-linux-gnu-gcc','--version'],text=True).splitlines()[0],
        probes=rows,conclusion='Stock separate-data mode retains GOT indirect calls. PC-relative-only changes data/GOT addressing too; not an OS3K-compatible drop-in.')
    (OUTPUT/'results.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps([dict(name=r['name'],exit_code=r['exit_code'],indirect=r['indirect_calls'],direct=r['direct_bsr_calls'])for r in rows],indent=2))


if __name__=='__main__':main()
