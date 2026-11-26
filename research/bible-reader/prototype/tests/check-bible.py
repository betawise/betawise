#!/usr/bin/env python3
"""Disposable Neo benchmark; exact source expectations + controller RAM oracle."""
import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

from check import prepare_session, ROOT, HERE
from neo_reader import stable_read

spec=importlib.util.spec_from_file_location('repl_checks',HERE/'check-repl.py')
repl=importlib.util.module_from_spec(spec);spec.loader.exec_module(repl)
APP=ROOT/'betawise/applets/BibleReader'


def page(text, title, offset=0):
    text=text.replace('’',"'").replace('æ','ae').replace('Æ','AE').replace('…','...').replace('—','-')
    rows=[[' ']*44 for _ in range(7)];r=c=0
    while r<7 and offset<len(text):
        ch=text[offset];offset+=1
        assert ch=='\n' or 32<=ord(ch)<=126
        if ch=='\n':r+=1;c=0
        else:
            rows[r][c]=ch;c+=1
            if c==44:r+=1;c=0
    return (title+'\n'+'\n'.join(''.join(row).rstrip()for row in rows)).rstrip('\n'),offset


def verify_run(out, seek=None):
    checks=json.loads((out/'checks.json').read_text())
    timings=json.loads((out/'timings.json').read_text());reports=[]
    prior=json.loads((out/'results.json').read_text())if(out/'results.json').exists()else{}
    for i,check in enumerate(checks,1):
        path=out/f'checkpoint-{i:02}.lcd.json';reading,_=stable_read([path]);assert reading.text==check['equals'],(i,reading.text)
        record=json.loads(path.read_text())
        expected_flags=dict(m_start_line=0,m_display_on=1,m_adc=0,m_com_reverse=0,m_reverse=0,m_all_points=0,m_reset=0)
        for sample in record['samples']:
            for controller in sample['controllers']:
                assert all(controller[k]==v for k,v in expected_flags.items()),(i,'controller flags')
        metrics=json.loads((out/f'metrics-{i:02}.json').read_text());assert metrics[2]==4 and metrics[12]==0
        if check.get('full'):
            cached=(out/f'cache-{i:02}.bin').read_bytes()
            expected=(out/check['expected_file']).read_bytes()
            assert cached==expected and len(cached)==metrics[10],(i,'chapter cache')
        times={t['phase']:t['emulated_seconds']for t in timings if t['serial']==metrics[1]}
        row=dict(name=check['name'],serial=metrics[1],firmware_ms=dict(seek=metrics[7]-metrics[6],layout=metrics[8]-metrics[7],paint=metrics[9]-metrics[8],total=metrics[9]-metrics[6]),chapter_prefix_symbols=metrics[10],page_symbols=metrics[11],workspace_bytes=metrics[13],screen_bytes=metrics[14],init_ms=metrics[15],lcd_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),reading=asdict(reading),controller_flags_verified=True)
        row['firmware_timer_valid']=all(v>=0 for v in row['firmware_ms'].values())
        row['cpu_clock_hz']=sorted({t['cpu_clock']for t in timings if t['serial']==metrics[1]})
        row['kind']='full-chapter'if metrics[5]==2 else 'page'
        if check.get('full'):row.update(cached_bytes=len(cached),cache_sha256=hashlib.sha256(cached).hexdigest())
        if all(p in times for p in [1,2,3,4]):row['emulated_ms']=dict(seek=1000*(times[2]-times[1]),layout=1000*(times[3]-times[2]),paint=1000*(times[4]-times[3]),total=1000*(times[4]-times[1]))
        reports.append(row)
    artifact=out/'artifacts/BibleReader.OS3KApp'
    size=artifact.stat().st_size if artifact.exists()else prior.get('applet_bytes')
    result=dict(status='passed',seek_checkpoints=prior.get('seek_checkpoints',False)if seek is None else seek,applet_bytes=size,results=reports)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps([dict(name=r['name'],emulated_ms=r.get('emulated_ms'),firmware_timer_valid=r['firmware_timer_valid'])for r in reports],indent=2))
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path)
    ap.add_argument('--verify-only',type=Path,help='replay exact text and controller assertions from saved RAM records')
    ap.add_argument('--mame',type=Path,default=ROOT/'mame/neodiag')
    ap.add_argument('--firmware',type=Path,default=ROOT/'Ghidra/Alphasmart Neo/SmartApplets')
    ap.add_argument('--source',type=Path,default=ROOT/'.research-work/bible-compression/ascii-huffman/kjv-ascii.json')
    ap.add_argument('--seek',action='store_true',help='use eight-verse decoder-state checkpoints')
    ap.add_argument('--dataset',type=Path,help='verified comparison resource instead of the legacy corpus')
    ap.add_argument('--codec',choices=['arithmetic','huffman'],default='huffman')
    ap.add_argument('--ascii',action=argparse.BooleanOptionalAction,default=True,help='compile an ASCII-only display path')
    ap.add_argument('--full-chapters',action='store_true',help='measure complete chapter-to-RAM decoding as well as pages')
    args=ap.parse_args()
    if args.verify_only:verify_run(args.verify_only.resolve());return
    if args.codec=='huffman'and args.seek:ap.error('Huffman does not need/use arithmetic state checkpoints')
    if args.dataset is None and args.codec=='arithmetic':args.dataset=ROOT/'.research-work/bible-compression/ascii-huffman/arithmetic/container.bin'
    if not args.output:ap.error('--output is required for a new run')
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    with (out/'build.log').open('w')as log:
        for directory in [ROOT/'betawise/os3k',ROOT/'betawise/fonts',APP]:
            cmd=['make','-C',str(directory),'-j2']
            if directory==APP:cmd+=['-B','READER=Benchmark',f'USE_SEEK={int(args.seek)}']
            if directory==APP:
                cmd += [f'CODEC={args.codec}',f'ASCII={int(args.ascii)}',f'FULL_CACHE={int(args.full_chapters)}']
                if args.dataset:cmd += [f'BIBLE_DATA={args.dataset.resolve()}',f'BIBLE_SHA256={hashlib.sha256(args.dataset.read_bytes()).hexdigest()}']
            subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
    # Reuse firmware placement/hash qualification, then replace only the applet
    # region in this newly-created disposable image. No existing session read.
    prepare_session(out,args.firmware,'extra',args.mame)
    flash=bytearray((out/'nvram/asneo/flashnv').read_bytes());flash[0x70000:]=b'\xff'*(len(flash)-0x70000)
    images=[args.firmware/'alphawordplus.os3kapp',APP/'BibleReader.OS3KApp',ROOT/'betawise/fonts/build/BetaWiseTerminal-Medium/BetaWiseTerminal-Medium.OS3KApp']
    (out/'artifacts').mkdir()
    offset=0x70000
    for path in images:
        b=path.read_bytes();assert int.from_bytes(b[4:8],'big')==len(b) and offset+len(b)<=len(flash)
        flash[offset:offset+len(b)]=b;offset+=len(b)
        if path.parent==APP or path.name=='BetaWiseTerminal-Medium.OS3KApp':shutil.copyfile(path,out/'artifacts'/path.name)
    (out/'nvram/asneo/flashnv').write_bytes(flash)
    nm=subprocess.check_output(['m68k-linux-gnu-nm','-n',str(APP/'BibleReader.elf')],text=True)
    symbols={s[2]:int(s[0],16)for line in nm.splitlines()if len(s:=line.split())==3}
    (out/'symbols.json').write_text(json.dumps(symbols,indent=2)+'\n')
    books=json.loads(args.source.read_text(encoding='utf-8-sig'))
    refs=[(1,1,1,None),(1,1,1,'Down'),(43,3,16,'2'),(1,1,31,'1'),
          (19,119,1,'3'),(19,119,88,'4'),(19,119,176,'5'),
          (66,22,21,'6'),(19,117,1,'7'),(40,5,1,'8'),(23,53,5,'9'),
          (43,3,16,'2'),(19,119,176,'5'),
          (40,22,21,'goto'),(43,3,23,'goto'),(2,17,16,'goto'),(2,32,32,'goto')]
    if args.full_chapters:
        refs=[(1,1,1,None),(1,1,1,'Down'),(43,3,16,'2'),(19,119,1,'3'),
              (19,119,1,'full'),(1,1,1,'0'),(1,1,1,'full'),
              (19,117,1,'7'),(19,117,1,'full'),(19,119,1,'3'),(19,119,1,'full')]
    checks=[];prior_offset=0
    for i,(book,chapter,verse,key)in enumerate(refs):
        name=books[book-1]['name'];text='\n'.join(books[book-1]['chapters'][chapter-1][verse-1:])+'\n'
        title=f'KJV {name} {chapter}:{verse}'+(' +1'if key=='Down'else'')
        expected,prior_offset=page(text,title,prior_offset if key=='Down'else 0)
        check=dict(name=f'{name} {chapter}:{verse}'+(' next page'if key=='Down'else''),serial=i+1,key=key,equals=expected)
        if key=='full':
            raw=('\n'.join(books[book-1]['chapters'][chapter-1])+'\n').encode('ascii')
            digest=2166136261
            for byte in raw:digest=((digest^byte)*16777619)&0xffffffff
            check.update(name=f'{name} {chapter} full chapter',key='T',full=True,byte_count=len(raw),expected_file=f'expected-chapter-{i:02}.bin',equals=f'KJV {name} {chapter}:1\nFull chapter decoded\nBytes: {len(raw)}\nHash: {digest:08X}')
            (out/check['expected_file']).write_bytes(raw)
        if key=='goto':check['keys']=['G']+['Space'if ch==' 'else ch for ch in f'{book} {chapter} {verse}']+['Enter']
        checks.append(check)
    (out/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    bootstrap=repl.bootstrap([],out)
    # bootstrap declares an expectations variable; this harness uses checks.
    script=bootstrap+'\nlocal checks='+repl.lua(checks)+'\nlocal bench_offset='+str(symbols['g_bible_bench']-0x80000000)+'\nlocal cache_offset='+str(symbols.get('g_chapter_cache',0x80000000)-0x80000000)+'\n'+(HERE/'BibleHarness.lua').read_text()
    (out/'run.lua').write_text(script)
    manifest=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in images+[args.source,APP/'Decoder.c',APP/'HuffmanDecoder.c',APP/'Benchmark.c',HERE/'BibleHarness.lua',args.mame]]
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    command=[str(args.mame),'asneo','-rompath',str(out/'roms'),'-cfg_directory',str(out/'cfg'),'-nvram_directory',str(out/'nvram'),'-snapshot_directory',str(out/'snap'),'-video','none','-sound','none','-nothrottle','-frameskip','0','-noautoframeskip','-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(out/'run.lua'),'-seconds_to_run','1500']
    with(out/'mame.log').open('w')as log:
        result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=900,env=dict(os.environ,SDL_VIDEODRIVER='dummy'))
    log=(out/'mame.log').read_text()
    if result.returncode or 'PASS Bible benchmark completed'not in log or 'FAIL Bible' in log:
        raise RuntimeError('MAME benchmark failed; see '+str(out/'mame.log'))
    verify_run(out,args.seek)


if __name__=='__main__':main()
