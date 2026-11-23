#!/usr/bin/env python3
"""Inventory original ROM dispatch candidates and vendor entry/transport pumps.

Static candidates are not a proof of reachability or of an indirect target.
--ghidra uses disposable projects and follows resolved immediate/direct calls.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
AUDIT = HERE.parents[1] / 'abi-audit'
# Reviewed roots: descriptor-derived callbacks, cached callbacks, and forwarding
# helpers. The prologue heuristic below does not define these function bounds.
EXTRA_ROOTS = {
    'as3000': [0x4c99bc,0x4c9fc0,0x4e4082,0x4e41c0,0x4e44b4,0x4e4a06,0x4c67ca,0x4c00a0, 0x4d255e, 0x4d2a6c, 0x4d2de6, 0x4d2f86, 0x4d3722, 0x4d3dfc],
    'neo_3_01': [0x5c91fe,0x5c9828,0x5c6932,0x5e6974,0x5e6a76,0x5e6d6a,0x5e72bc,0x5c00a0],
    'neo_3_21': [0x4100a0, 0x4108f8, 0x416dbe, 0x416f40, 0x4199c0,
                  0x419ff2, 0x43cea0,0x43d194, 0x43cd9e, 0x43d6e6, 0x426df2, 0x427458,
                  0x42882c, 0x4285ce, 0x42f200, 0x42f744, 0x422af4],
}
CACHED_CALLBACKS = {'as3000': [0x3dfa,0x3e24,0x4424,0x4428,0x4464,0x4468,0x446c,0x450e],
                    'neo_3_01': [0x3e52,0x5940],
                    'neo_3_21': [0x3e8a,0x3eb4,0x1193e]}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_ghidra(output, project, image, base, script, args, *, directory=False):
    (output/'java-home').mkdir(exist_ok=True)
    command = [os.environ.get('GHIDRA_HOME','/opt/ghidra')+'/support/analyzeHeadless',
               str(output), project, '-import', str(image)]
    if directory:
        command += ['-recursive']
    command += ['-loader','BinaryLoader','-loader-baseAddr',hex(base),
                '-processor','68000:BE:32:default','-noanalysis','-scriptPath',
                str(HERE), '-postScript',script]+args
    log = output/(project+'-ghidra.txt')
    with log.open('w') as f:
        subprocess.run(command, stdout=f, stderr=subprocess.STDOUT, check=True,
                       env={**os.environ,'JAVA_TOOL_OPTIONS':'-Duser.home='+str(output/'java-home')})
    text = log.read_text()
    assert 'Save succeeded' in text and 'ERROR REPORT SCRIPT ERROR' not in text, log


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    p.add_argument('--ghidra',action='store_true')
    p.add_argument('--pump-evidence',type=Path,help='Summarize an existing completed AuditMessageEntry run')
    a = p.parse_args()
    output = a.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    roms = json.loads((AUDIT/'rom-inventory.json').read_text())
    vendors = json.loads((AUDIT/'vendor-image-inventory.json').read_text())
    report = {'scope':'static candidate census; semantic claims require reviewed traces',
              'roms':[], 'applets':[], 'untracked_original_images':[]}
    known = {e['sha256'] for e in vendors}
    for image in (ROOT/'Ghidra').rglob('*'):
        if image.is_file() and image.suffix.lower()=='.os3kapp' and sha(image) not in known:
            report['untracked_original_images'].append(str(image.relative_to(ROOT)))
    for entry in roms:
        image = ROOT/entry['path']
        assert sha(image)==entry['sha256'],image
        command = ['m68k-linux-gnu-objdump','-D','-b','binary','-m','m68k:68000',
                   f"--adjust-vma={entry['base']}",str(image)]
        text = subprocess.check_output(command,text=True).replace(str(image),entry['path'])
        (output/(entry['name']+'.dis')).write_text(text)
        rows = []
        for line in text.splitlines():
            m = re.match(r'\s*([0-9a-f]+):\s+(?:[0-9a-f]{4} +)+\s*([a-z].*)$',line)
            if m:
                rows.append((int(m[1],16),m[2]))
        last = None
        headers, calls, cached, literals = [], [], [], []
        for n,(address,instruction) in enumerate(rows):
            if 'moveml' in instruction and '%sp@-' in instruction:
                last = address
            context = [{'address':hex(x),'instruction':y} for x,y in rows[max(0,n-5):n+6]]
            rec = {'address':hex(address),'instruction':instruction,
                   'prologue_hint':None if last is None else hex(last), 'context':context}
            if re.search(r'(?:movel|moveal|addl|addal) .*%a[0-6]@\(132\)',instruction):
                headers.append(rec)
            if re.search(r'\bjsr %a[0-6]@',instruction):
                calls.append(rec)
            if any(re.search(r'\b0x'+format(v,'x')+r'\b',instruction) for v in CACHED_CALLBACKS[entry['name']]):
                cached.append(rec)
            # Literal-shaped values remain candidates: many are masks, UI IDs,
            # addresses or resources. Do not promote them to Message_e blindly.
            if re.search(r'pea 0x[1-7]0[012][0-9a-f]{2}$',instruction):
                literals.append(rec)
        roots = sorted(set(EXTRA_ROOTS[entry['name']]) |
                       {int(x['prologue_hint'],16) for x in headers if x['prologue_hint']})
        report['roms'].append({**{k:entry[k] for k in ['name','path','base','sha256']},
                              'entry_field_references':headers,'indirect_register_calls':calls,
                              'cached_callback_references':cached,'message_shaped_literals':literals,
                              'dump_roots':[hex(x) for x in roots]})
        if a.ghidra:
            run_ghidra(output,entry['name'],image,entry['base'],'DumpMessageFunction.java',[format(x,'x') for x in roots])
    if a.ghidra:
        inputs=output/'inputs';inputs.mkdir(exist_ok=True)
        pumps=output/'pumps';pumps.mkdir(exist_ok=True)
        for n,e in enumerate(vendors):
            shutil.copyfile(ROOT/e['path'],inputs/(f'{n:02d}-'+Path(e['path']).name))
        run_ghidra(output,'entries',inputs,0,'AuditMessageEntry.java',[str(pumps)],directory=True)
        a.pump_evidence=pumps
    for n,e in enumerate(vendors):
        image=ROOT/e['path'];assert sha(image)==e['sha256'],image
        data=image.read_bytes();assert data[:4]==bytes.fromhex('c0ffeead'),image
        record={'name':e['name'],'path':e['path'],'sha256':e['sha256'],
                'entry':hex(int.from_bytes(data[0x84:0x88],'big'))}
        if a.pump_evidence:
            evidence=a.pump_evidence/(f'{n:02d}-'+image.name+'.txt')
            s=evidence.read_text();m=re.search(r'ENTRY_AUDIT_DONE functions=(\d+) pending=(\d+)',s)
            assert m and m[2]=='0',evidence
            record.update(evidence_sha256=sha(evidence),resolved_function_count=int(m[1]),
                          decompilation_failures=s.count('DECOMPILATION_FAILED'),
                          unresolved_decompiler_tables=s.count('Could not recover jumptable'),
                          resolved_tables=re.findall(r'RESOLVED_SWITCH ([^\n]+)',s))
        report['applets'].append(record)
    (output/'dispatch-inventory.json').write_text(json.dumps(report,indent=2)+'\n')
    compact={'scope':report['scope'],'untracked_original_images':report['untracked_original_images'],
             'roms':[{k:v for k,v in r.items() if k in ['name','path','base','sha256','dump_roots']} |
                     {'entry_field_reference_count':len(r['entry_field_references']),
                      'indirect_register_call_candidate_count':len(r['indirect_register_calls'])}
                     for r in report['roms']], 'applets':report['applets']}
    (output/'dispatch-summary.json').write_text(json.dumps(compact,indent=2)+'\n')
    print('PASS:',len(roms),'ROM hashes,',len(vendors),'applet hashes;',
          sum(len(r['entry_field_references']) for r in report['roms']),'entry-field references;',
          len(report['untracked_original_images']),'untracked original applet images')


if __name__=='__main__':
    main()
