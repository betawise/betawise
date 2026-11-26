#!/usr/bin/env python3
"""Native BibleReader acceptance: private MAME flash/RAM, source/bitmap assertions."""
import argparse,hashlib,importlib.util,json,os,re,shutil,struct,subprocess,sys
from pathlib import Path
from PIL import ImageChops
from check import prepare_session,ROOT,HERE
from neo_reader import lcd_frames
from screen_bitmap import compare
from bible_layout import paragraph,render,typeset,system_font,captured_font
APP=ROOT/'betawise/applets/BibleReader'
spec=importlib.util.spec_from_file_location('repl_checks',HERE/'check-repl.py');repl=importlib.util.module_from_spec(spec);spec.loader.exec_module(repl)
def keys(text):return ['Space'if c==' 'else 'Semicolon'if c==':'else ['Left Shift','8']if c=='*'else c.upper() for c in text]
def reference(text):return ['G']+keys(text)+['Enter']
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--search-modes-ui',action='store_true');ap.add_argument('--search-modes-bench',action='store_true');ap.add_argument('--navigation-bench',action='store_true');ap.add_argument('--prefix-bench',action='store_true');ap.add_argument('--sample-search',action='store_true');ap.add_argument('--verse-boost',action='store_true');ap.add_argument('--clear-complete',action='store_true');ap.add_argument('--native-fast-load',action='store_true');ap.add_argument('--fast-bits',type=int,choices=[8,10,12],default=8);ap.add_argument('--bench-query',choices=['Methus','believ','love','God','in the beg','Jesus Jesus','th']);ap.add_argument('--search-index',choices=['full','compact','scan','none'],default='full');ap.add_argument('--version',choices=['KJV','NKJV'],default='KJV');ap.add_argument('--readthrough',choices=['line','page']);ap.add_argument('--work-profile',action='store_true');ap.add_argument('--background-rapid',action='store_true');ap.add_argument('--feed-end-smoke',action='store_true');ap.add_argument('--feed-font-smoke',action='store_true');ap.add_argument('--feed-features',action='store_true');ap.add_argument('--feed-quick',action='store_true');ap.add_argument('--native-stream',choices=['off','window','demand','background','lookahead','viewport','prewrap','prewrap-full'],default='off');ap.add_argument('--native-page-test',action='store_true');ap.add_argument('--native-open-test',choices=['baseline','direct','refresh-only','viewport-full'],default='baseline');ap.add_argument('--output',type=Path,required=True);ap.add_argument('--verify-only',action='store_true');ap.add_argument('--layout-bench',action='store_true');ap.add_argument('--position-probe',action='store_true');ap.add_argument('--dialog-probe',action='store_true');ap.add_argument('--vendor-font',choices=['small','medium','large','vlarge','xlarge','tiny']);ap.add_argument('--profile',action='store_true');ap.add_argument('--experiment',choices=['baseline','word-scdc','huffman-prune'],default='baseline');ap.add_argument('--system-font',action='store_true',help='test the production build starting in the native 4-line font');a=ap.parse_args();out=a.output.resolve()
 if a.verify_only:verify(out);return
 out.mkdir(parents=True,exist_ok=False)
 vendor=(ROOT/'betawise/fonts/BetaWiseTerminal-Tiny.OS3KApp'if a.vendor_font=='tiny'else ROOT/'Ghidra/Alphasmart Neo/SmartApplets'/('neofont'+a.vendor_font+'.os3kapp'))if a.vendor_font else None
 vendor_id=int.from_bytes(vendor.read_bytes()[20:22],'big')if vendor else 0
 stem=dict(off="BibleReader",window="BibleReader-NativeWindow",demand="BibleReader-NativeDemand",background="BibleReader-NativeBG",lookahead="BibleReader-NativeLookahead",viewport="BibleReader-NativeViewport",prewrap="BibleReader-NativePrewrap",**{"prewrap-full":"BibleReader-NativePrewrapFull"})[a.native_stream]+(""if a.version=="KJV"else"-"+a.version)
 if a.search_index!='full':stem+='-'+a.search_index
 extra=[]
 if a.experiment!='baseline':extra=([f'DENSE=1','PREBUILT_DATA=1',f'DATA_DIR={ROOT/".research-work/bible-compression/device-comparison/word-scdc"}']if a.experiment=='word-scdc'else['PRUNE=1'])
 with(out/'build.log').open('w')as log:subprocess.run(['make','-C',str(APP),'-B','READER=BibleReader',f'SEARCH_INDEX={a.search_index}',f'FAST_BITS={a.fast_bits}',f'VERSE_BOOST={int(a.verse_boost)}',f'FAST_NATIVE={int(a.native_fast_load)}',f'SEARCH_CLEAR_COMPLETE={int(a.clear_complete)}',f'BENCH_QUERY={-1 if not a.bench_query else ["Methus","believ","love","God","in the beg","Jesus Jesus","th"].index(a.bench_query)}',f'NATIVE_STREAM={["off","window","demand","background","lookahead","viewport","prewrap","prewrap-full"].index(a.native_stream)}',f'NATIVE_PAGE_TEST={int(a.native_page_test or a.native_stream!="off")}',f'NATIVE_OPEN_TEST={dict(baseline=0,direct=1,**{"refresh-only":2,"viewport-full":3})[a.native_open_test]}',f'VERSION={a.version}',f'WORK_PROFILE={int(a.work_profile)}',f'TEST_FONT={0 if a.system_font else 1}',f'PROFILE={int(a.profile)}',f'TEST_FONT_ID={hex(vendor_id) if vendor else ""}',*extra],stdout=log,stderr=subprocess.STDOUT,check=True)
 fw=ROOT/'Ghidra/Alphasmart Neo/SmartApplets';mame=ROOT/'mame/neodiag';prepare_session(out,fw,'extra',mame)
 flash=bytearray((out/'nvram/asneo/flashnv').read_bytes());flash[0x70000:]=b'\xff'*(len(flash)-0x70000);offset=0x70000
 images=[fw/'alphawordplus.os3kapp',APP/(stem+'.OS3KApp'),ROOT/'betawise/fonts/BetaWiseTerminal-Medium.OS3KApp'];(out/'artifacts').mkdir()
 if vendor:
  if a.vendor_font=='tiny':images[-1]=vendor
  else:images.append(vendor)
 for p in images:
  b=p.read_bytes();assert offset+len(b)<=len(flash);flash[offset:offset+len(b)]=b;offset+=len(b);shutil.copyfile(p,out/'artifacts'/p.name)
 (out/'nvram/asneo/flashnv').write_bytes(flash)
 nm=subprocess.check_output(['m68k-linux-gnu-nm','-n',str(APP/(stem+'.elf'))],text=True);symbols={s[2]:int(s[0],16)for l in nm.splitlines()if len(s:=l.split())==3};(out/'symbols.json').write_text(json.dumps(symbols,indent=2))
 data=ROOT/('.research-work/bible-compression/'+('reader-viewer'if a.experiment=='huffman-prune'else'reader')+'/'+a.version.lower());books=json.loads((data/'source.json').read_bytes());shutil.copyfile(data/'source.json',out/'source.json');ch=lambda b,c:sum(len(x['chapters'])for x in books[:b-1])+c-1
 checks=[dict(name='Genesis with superscripts',chapter=0,verse=1,numbered=1),
  dict(name='Jump John 3:16',keys=reference('43 3 16'),chapter=ch(43,3),verse=16,numbered=1),
  dict(name='Hide verse numbers',keys=['V'],chapter=ch(43,3),verse=16,numbered=0),
  dict(name='Psalm 119 last verse',keys=reference('19 119 176'),chapter=ch(19,119),verse=176,numbered=0),
  dict(name='Return Genesis',keys=reference('1 1 1'),chapter=0,verse=1,numbered=0),
  dict(name='Show numbers',keys=['V'],chapter=0,verse=1,numbered=1),
  dict(name='Exact believe first match',match='believe',keys=['Find','Tab']+keys('believe*')+['Enter'],chapter=ch(2,4),verse=1,numbered=1),
  dict(name='Next exact match',match='believe',keys=['N'],chapter=ch(2,4),verse=5,numbered=1),
  dict(name='Previous exact match',match='believe',keys=['P'],chapter=ch(2,4),verse=1,numbered=1),
  dict(name='Cmd+G next match',keys=[['Command','G']],chapter=ch(2,4),verse=5,numbered=1,match='believe'),
  dict(name='Shift+Cmd+G previous',keys=[['Left Shift','Command','G']],chapter=ch(2,4),verse=1,numbered=1,match='believe'),
  dict(name='Cmd+Find next match',keys=[['Command','Find']],chapter=ch(2,4),verse=5,numbered=1,match='believe'),
  dict(name='Shift+Cmd+Find previous',keys=[['Left Shift','Command','Find']],chapter=ch(2,4),verse=1,numbered=1,match='believe'),
  dict(name='CtrlG reference alias',keys=[['Left Ctrl','G']]+keys('2 4 1')+['Enter'],chapter=ch(2,4),verse=1,numbered=1),
  dict(name='Reset before search alias',keys=reference('1 1 1'),chapter=0,verse=1,numbered=1),
  dict(name='CtrlF exact search alias',keys=[['Left Ctrl','F']]+keys('believe*')+['Enter'],chapter=ch(2,4),verse=1,numbered=1,match='believe'),
  dict(name='Copy current verse with citation',keys=[['Left Ctrl','C']],chapter=ch(2,4),verse=1,numbered=1,mode=3,clipboard=True),
  dict(name='Dismiss copy notice',keys=['Escape'],chapter=ch(2,4),verse=1,numbered=1),
  dict(name='Invalid verse rejected',keys=reference('1 1 99'),chapter=ch(2,4),verse=1,numbered=1,mode=3),
  dict(name='Cancel error',keys=['Escape'],chapter=ch(2,4),verse=1,numbered=1),
  dict(name='Psalm 117',keys=reference('19 117 1'),chapter=ch(19,117),verse=1,numbered=1),
  dict(name='Page down',keys=['Space'],chapter=ch(19,117),numbered=1),
  dict(name='Named reference',keys=reference('John 3 16'),chapter=ch(43,3),verse=16,numbered=1),
  dict(name='Select from verse start',keys=[['Left Shift','Right']],chapter=ch(43,3),verse=16,numbered=1,selection=True),
  dict(name='Copy selection with citation',keys=[['Left Ctrl','C']],chapter=ch(43,3),verse=16,numbered=1,mode=3,clipboard=True,selection=True),
  dict(name='Cancel selection',keys=['Escape','Left'],chapter=ch(43,3),numbered=1),
  dict(name='System font picker',keys=[['Left Ctrl','Left Alt','Command','F'],'Home','Enter'],chapter=ch(43,3),verse=16,numbered=1,height=16),
  dict(name='Hide numbers in system font',keys=['V'],chapter=ch(43,3),verse=16,numbered=0,height=16),
  dict(name='Show numbers in system font',keys=['V'],chapter=ch(43,3),verse=16,numbered=1,height=16),
  dict(name='Largest chapter in system font',keys=reference('19 119 176'),chapter=ch(19,119),verse=176,numbered=1,height=16),
  dict(name='Empty exact search',keys=['Find']+keys('zzzzunknown')+['Enter'],chapter=ch(19,119),verse=176,numbered=1,height=16,mode=3,notice='No matches'),
  dict(name='Cancel search notice',keys=['Escape'],chapter=ch(19,119),verse=176,numbered=1,height=16),
  dict(name='Resume after AlphaWord round trip',keys=['Applets','Home','Enter','Applets','Down','Enter'],chapter=ch(19,119),verse=176,numbered=1,height=16,resume=True)]
 if a.layout_bench:
  chapter=ch(40,2)
  checks=[checks[0],dict(name='John3 fresh start',keys=['C'],chapter=ch(43,3),verse=1,numbered=1),dict(name='Median chapter fresh start',keys=['A'],chapter=chapter,verse=1,numbered=1,top_line=0),dict(name='Median cached redraw',keys=['R'],chapter=chapter,verse=1,numbered=1,top_line=0),dict(name='Position at bottom',keys=['Down']*3,chapter=chapter,numbered=1,top_line=0),dict(name='Median one line down',keys=['Down'],chapter=chapter,numbered=1,top_line=1),dict(name='Median one line up',keys=['Up']*4,chapter=chapter,numbered=1,top_line=0),dict(name='Position bottom again',keys=['Down']*3,chapter=chapter,numbered=1,top_line=0),dict(name='Median cached page forward',keys=['Space'],chapter=chapter,numbered=1,top_line=4),dict(name='Median cached next page',keys=['Space'],chapter=chapter,numbered=1,top_line=8),dict(name='Position at top',keys=['Up']*3,chapter=chapter,numbered=1,top_line=8),dict(name='Median cached page back',keys=[['Left Shift','Space']],chapter=chapter,numbered=1,top_line=4),dict(name='Median cached first page',keys=[['Left Shift','Space']],chapter=chapter,numbered=1,top_line=0),dict(name='Leave median chapter',keys=['C'],chapter=ch(43,3),verse=1,numbered=1),dict(name='Median fresh middle verse',keys=['B'],chapter=chapter,verse=12,numbered=1)]
 if a.position_probe:checks=[checks[0],checks[3]|dict(numbered=1),checks[-1]]
 if a.dialog_probe:
  checks=[checks[0],dict(name='Native jump prompt',keys=['G'],chapter=0,verse=1,numbered=1,mode=1,dialog=''),dict(name='Native reference input',keys=keys('43 3 17')+['Backspace','6'],chapter=0,verse=1,numbered=1,mode=1,dialog='43 3 16'),dict(name='Confirm native jump',keys=['Enter'],chapter=ch(43,3),verse=16,numbered=1)]
 if a.profile and not a.layout_bench:
  checks=[checks[0],dict(name='Decode Genesis only',keys=['T'],chapter=0,verse=1,numbered=1),checks[3]|dict(name='Load Psalm119',numbered=1),dict(name='Decode Psalm119 only',keys=['T'],chapter=ch(19,119),verse=176,numbered=1),next(c for c in checks if c['name']=='Exact believe first match'),next(c for c in checks if c['name']=='Next exact match'),dict(name='Full corpus rare-phrase scan',keys=['Y'],chapter=ch(2,4),verse=5,numbered=1,match='believe',scan_matches=0)]
  checks.insert(4,dict(name='Reset before profiled search',keys=reference('1 1 1'),chapter=0,verse=1,numbered=1))
 if vendor:
  for check in checks:check['font_vendor']=a.vendor_font
 if a.system_font:
  for check in checks:check['height']=16
 if not a.profile and not a.layout_bench and not a.dialog_probe and not a.position_probe:
  checks[1:1]=[dict(name='Native goto overlay',keys=['G'],chapter=0,verse=1,numbered=1,mode=1,dialog=''),dict(name='Cancel native goto',keys=['Escape'],chapter=0,verse=1,numbered=1)]
  extra=[dict(name='Reset before waters search',keys=reference('1 1 1'),chapter=0,verse=1,numbered=1),dict(name='Find waters',keys=['Find']+keys('waters')+['Enter'],chapter=0,verse=2,numbered=1,match='waters'),
   dict(name='Next waters',keys=[['Command','G']],chapter=0,verse=6,numbered=1,match='waters'),
   dict(name='Same-verse next occurrence',keys=[['Command','G']],chapter=0,verse=6,numbered=1,match='waters',occurrence=1),
   dict(name='Third occurrence in same verse',keys=[['Command','G']],chapter=0,verse=6,numbered=1,match='waters',occurrence=2),
   dict(name='Previous occurrence',keys=[['Left Shift','Command','G']],chapter=0,verse=6,numbered=1,match='waters',occurrence=1),
   dict(name='Return largest chapter',keys=reference('19 119 176'),chapter=ch(19,119),verse=176,numbered=1)]
  checks[-1:-1]=extra
 if a.readthrough:
  assert a.profile and a.system_font and not vendor,'read-through uses the real system 6x16 font'
  chapter=ch(19,119);ls,*_=typeset([c for b in books for c in b['chapters']][chapter],True);last=len(ls)-1
  checks=[dict(name='Initial Genesis',chapter=0,verse=1,numbered=1,height=16),dict(name='Load Psalm119',keys=reference('19 119 1'),chapter=chapter,verse=1,numbered=1,height=16,top_line=0,caret_line=0)]
  targets=list(range(1,last+1))if a.readthrough=='line'else list(range(4,last+1,4))+([last]if last%4 else[])
  for j,target in enumerate(targets):checks.append(dict(name='Readthrough '+str(j+1),keys=['Down'if a.readthrough=='line'else'Space'],chapter=chapter,numbered=1,height=16,top_line=max(0,target-3),caret_line=target))
  checks +=[dict(name='Finish at EOF',keys=['End'],chapter=chapter,numbered=1,height=16,top_line=max(0,last-3),caret_line=last),dict(name='Pure chapter decode',keys=['T'],chapter=chapter,numbered=1,height=16,top_line=max(0,last-3),caret_line=last)]
  (out/'readthrough.json').write_text(json.dumps(dict(reader=('native-'+a.native_stream if a.native_stream!='off'else('native'if a.native_open_test=='baseline'else'native-'+a.native_open_test))+('-cmd-page'if a.native_page_test else''),version=a.version,mode=a.readthrough,work=a.work_profile,background_policy=('rapid'if a.background_rapid else'finish_before_scroll')if a.native_stream=='background'else None,wrapped_lines=len(ls),source_bytes=sum(len(v)+1 for v in [c for b in books for c in b['chapters']][chapter])),indent=2))
 if a.feed_features:
  assert a.native_stream!='off'and a.system_font,'feature fixture uses native 6x16'
  ci=ch(19,119)
  checks=[dict(name='Initial Genesis',chapter=0,verse=1,numbered=1,height=16),dict(name='Load Psalm119',keys=reference('19 119 1'),chapter=ci,verse=1,numbered=1,height=16,top_line=0,caret_line=0)]
  checks +=[dict(name='Extend native selection page '+str(i),keys=[['Left Shift','Command','Down']],chapter=ci,numbered=1,height=16,top_line=4*i-3,caret_line=4*i,multi_select=True)for i in range(1,21)]
  checks +=[dict(name='Copy across evicted anchor',keys=[['Left Ctrl','C']],chapter=ci,numbered=1,height=16,top_line=77,caret_line=80,multi_select=True,mode=3,clipboard=True,copy_prefix_line=80),dict(name='Cancel long selection',keys=['Escape'],chapter=ci,numbered=1,height=16,top_line=77,caret_line=80),dict(name='Backward rebuild to chapter start',keys=[['Left Ctrl','Home']],chapter=ci,numbered=1,height=16,top_line=0,caret_line=0),dict(name='Select full chapter',keys=[['Left Ctrl','A']],chapter=ci,numbered=1,height=16,top_line=310,caret_line=313,multi_select=True),dict(name='Copy full chapter',keys=[['Left Ctrl','C']],chapter=ci,numbered=1,height=16,top_line=310,caret_line=313,multi_select=True,mode=3,clipboard=True,copy_entire=True),dict(name='Cancel full selection',keys=['Escape'],chapter=ci,numbered=1,height=16,top_line=310,caret_line=313),dict(name='Jump within resident last verse',keys=reference('19 119 176'),chapter=ci,verse=176,numbered=1,height=16),dict(name='Jump backwards to verse one',keys=reference('19 119 1'),chapter=ci,verse=1,numbered=1,height=16,top_line=0,caret_line=0)]
  j=next(i for i,c in enumerate(checks)if c['name']=='Backward rebuild to chapter start')
  checks[j:j]=[dict(name='Backward through eviction '+str(i),keys=['Up'],chapter=ch(19,119),numbered=1,height=16,caret_line=80-i,top_line=min(77,80-i))for i in range(1,13)]
  hits=[(ci,vi,m.start())for ci,chapter in enumerate(c for b in books for c in b['chapters'])for vi,v in enumerate(chapter,1)for m in re.finditer(r"[A-Za-z]+(?:'[A-Za-z]+)*",v)if m.group().lower().startswith('believe')]
  checks +=[dict(name='Reset before feed search',keys=reference('1 1 1'),chapter=0,verse=1,numbered=1,height=16)]
  for j in range(2):
   ci,vi,_=hits[j];checks +=[dict(name='Exact search hit '+str(j),keys=(['Find','Tab']+keys('believe*')+['Enter'])if not j else [['Command','Find']],chapter=ci,verse=vi,numbered=1,height=16,match='believe')]
  checks +=[dict(name='Retain lazy decoder and viewport across applets',keys=['Applets','Home','Enter','Applets','Down','Enter'],chapter=ci,verse=vi,numbered=1,height=16,match='believe',resume=True)]
  checks +=[dict(name='Hide native streaming verse numbers',keys=['V'],chapter=ci,verse=vi,numbered=0,height=16),dict(name='Restore native streaming verse numbers',keys=['V'],chapter=ci,verse=vi,numbered=1,height=16),dict(name='Copy current verse with citation',keys=[['Left Ctrl','C']],chapter=ci,verse=vi,numbered=1,height=16,mode=3,clipboard=True),dict(name='Dismiss current verse notice',keys=['Escape'],chapter=ci,verse=vi,numbered=1,height=16)]
 if a.feed_font_smoke:
  assert vendor and a.native_stream!='off'and not a.system_font
  height=dict(small=11,medium=13,large=16,vlarge=21,xlarge=32,tiny=6)[a.vendor_font];rows=64//height;ci=ch(19,119)
  checks=[dict(name='Vendor initial Genesis',chapter=0,verse=1,numbered=1,height=height,font_vendor=a.vendor_font),dict(name='Vendor Psalm119',keys=reference('19 119 1'),chapter=ci,verse=1,numbered=1,height=height)]
  checks +=[dict(name='Vendor page '+str(i),keys=['Space'],chapter=ci,numbered=1,height=height,caret_line=i*rows,top_line=i*rows-rows+1)for i in range(1,13)]
  checks +=[dict(name='Vendor final verse',keys=reference('19 119 176'),chapter=ci,verse=176,numbered=1,height=height),dict(name='Vendor backward jump',keys=reference('19 119 1'),chapter=ci,verse=1,numbered=1,height=height),dict(name='System font picker',keys=[['Left Ctrl','Left Alt','Command','F'],'Home','Enter'],chapter=ci,verse=1,numbered=1,height=16)]
 if a.feed_end_smoke:
  assert a.native_stream!='off'and a.system_font;ci=ch(19,119)
  checks=[dict(name='Initial Genesis',chapter=0,verse=1,numbered=1,height=16),dict(name='Load Psalm119',keys=reference('19 119 1'),chapter=ci,verse=1,numbered=1,height=16,top_line=0,caret_line=0),dict(name='Select lazy chapter',keys=[['Left Ctrl','A']],chapter=ci,numbered=1,height=16,top_line=310,caret_line=313,multi_select=True),dict(name='Copy lazy whole chapter',keys=[['Left Ctrl','C']],chapter=ci,numbered=1,height=16,top_line=310,caret_line=313,multi_select=True,mode=3,clipboard=True,copy_entire=True),dict(name='Cancel lazy whole selection',keys=['Escape'],chapter=ci,numbered=1,height=16,top_line=310,caret_line=313),dict(name='Native Home restores lazy start',keys=['Home'],chapter=ci,verse=1,numbered=1,height=16,top_line=0,caret_line=0),dict(name='Native End completes lazy chapter',keys=['End'],chapter=ci,verse=176,numbered=1,height=16,top_line=310,caret_line=313),dict(name='Native Home after end',keys=['Home'],chapter=ci,verse=1,numbered=1,height=16,top_line=0,caret_line=0)]
 # Historical whole-word fixtures now follow the independent prefix oracle.
 flat=[c for book in books for c in book['chapters']]
 bh=[(ci,vi,j)for ci,chv in enumerate(flat)for vi,v in enumerate(chv,1)for j,m in enumerate(re.finditer(r"[A-Za-z]+(?:'[A-Za-z]+)*",v))if m.group().lower().startswith('believe')]
 for c in checks:
  if c.get('match')=='believe'and c.get('chapter')==ch(2,4):
   which=1 if c.get('verse')==5 else 0;c['chapter'],c['verse'],c['hit_ordinal']=bh[which]
  elif c.get('chapter')==ch(2,4)and c['name']in['Copy current verse with citation','Dismiss copy notice','Invalid verse rejected','Cancel error']:
   c['chapter'],c['verse'],_=bh[0]
 if a.navigation_bench:
  assert a.profile and a.system_font and a.version=='KJV'
  sys.path.insert(0,str(ROOT/'betawise/research/bible-reader'));from navigation_cases import cases
  rows=cases(books);cache={}
  def occurrences(query):
   if query not in cache:
    qw=re.findall(r"[a-z]+(?:'[a-z]+)*",query.lower());hs=[]
    for ci,chv in enumerate(flat):
     for vi,v in enumerate(chv,1):
      tokens=re.findall(r"[a-z]+(?:'[a-z]+)*",v.lower());hs.extend((ci,vi,j)for j in range(len(tokens)-len(qw)+1)if all(tokens[j+k].startswith(w)for k,w in enumerate(qw)))
    cache[query]=hs
   return cache[query]
  for row in rows:
   origin=(row['chapter'],row['verse'],row['word']);hs=[h for h in occurrences(row['query'])if h>origin]if row['direction']>0 else[h for h in occurrences(row['query'])if h<origin]
   row['expected']=list(hs[0]if row['direction']>0 else hs[-1])if hs else None
  checks=[dict(name='Initial Genesis',chapter=0,verse=1,numbered=1,height=16)]
  j=ch(43,3);origin=(j,16,0);hs=occurrences('God');first=next(h for h in hs if h>=origin);second=next(h for h in hs if h>first)
  def hitcheck(name,keys,hit):return dict(name=name,keys=keys,chapter=hit[0],verse=hit[1],hit_ordinal=hit[2],match='god',numbered=1,height=16)
  checks +=[dict(name='Read John3:16 before search',keys=reference('43 3 16'),chapter=j,verse=16,numbered=1,height=16),hitcheck('Find from reading position',['Find','Tab']+keys('God*')+['Enter'],first),hitcheck('Find next from result',[["Command","Find"]],second),hitcheck('Find previous from result',[["Command","Left Shift","Find"]],first)]
  ps=ch(19,119);prior=[h for h in hs if h<(ps,80,0)][-1]
  checks +=[dict(name='Read Psalm119:80',keys=reference('19 119 80'),chapter=ps,verse=80,numbered=1,height=16),hitcheck('Previous outside history',[["Command","Left Shift","Find"]],prior)]
  checks.append({**checks[-1], 'name':'Complete navigation benchmark','keys':['X'],'scan_matches':int(rows[-1]['expected']is not None)})
  (out/'navigation-expected.json').write_text(json.dumps(rows,indent=2));(out/'search-option.json').write_text(json.dumps(dict(index=a.search_index,queries='navigation')))
 if a.search_modes_bench or a.search_modes_ui:
  assert a.profile and a.system_font and a.version=='KJV'
  sys.path.insert(0,str(ROOT/'betawise/research/bible-reader'));from search_modes_cases import cases
  spec_modes=importlib.util.spec_from_file_location('mode_oracle',ROOT/'betawise/research/bible-reader/check-search-modes.py');mo=importlib.util.module_from_spec(spec_modes);spec_modes.loader.exec_module(mo)
  cache={};rows=cases()
  for row in rows:
   k=(row['query'],row['mode'])
   if k not in cache:cache[k]=mo.oracle(flat,*k)
   origin=(row['chapter'],row['verse'],row['word']);hs=[h for h in cache[k]if h>origin]if row['direction']>0 else[h for h in cache[k]if h<origin]
   row['expected']=list(hs[0]if row['direction']>0 else hs[-1])if hs else None
  checks=[dict(name='Initial Genesis',chapter=0,verse=1,numbered=1,height=16)]
  current_mode=0
  # Validate all modes, explicit prefixes, both directions, and manual jumps.
  for mode,query in [(0,'faith works'),(1,'kingdom of God'),(2,'God loved'),(0,'be* bel*')]:
   checks.append(dict(name='Reset for mode '+str(mode)+' '+query,keys=reference('43 3 16'),chapter=ch(43,3),verse=16,numbered=1,height=16))
   hs=mo.oracle(flat,query,mode);first=next(h for h in hs if h>=(ch(43,3),16,0));second=next(h for h in hs if h>first)
   for label,ks,h in [('Search mode '+str(mode)+' '+query,['Find']+['Tab']*((mode-current_mode)%3)+keys(query)+['Enter'],first),('Next mode '+str(mode),[['Command','Find']],second),('Previous mode '+str(mode),[['Command','Left Shift','Find']],first)]:
    checks.append(dict(name=label,keys=ks,chapter=h[0],verse=h[1],hit_ordinal=h[2],match='mode',numbered=1,height=16))
   current_mode=mode
  if a.search_modes_ui:checks.append({**checks[-1],'name':'Cancel active phrase scan','keys':['Find','Tab']+keys('Jesus Jesus')+['Enter'],'cancel_after_frames':30})
  if a.search_modes_bench:checks.append({**checks[-1],'name':'Complete search mode benchmark','keys':['W'],'scan_matches':int(rows[-1]['expected']is not None)})
  (out/'navigation-expected.json').write_text(json.dumps(rows,indent=2));(out/'search-option.json').write_text(json.dumps(dict(index=a.search_index,queries='search-modes')))
 if a.prefix_bench:
  assert a.profile and a.system_font
  queries=['Methus','believ','love','God','in the beg','Jesus Jesus','th'];expected=[]
  for query in queries:
   qw=re.findall(r"[a-z]+(?:'[a-z]+)*",query.lower());hits=[];h=2166136261
   for ci,chv in enumerate(flat):
    for vi,v in enumerate(chv,1):
     tokens=re.findall(r"[a-z]+(?:'[a-z]+)*",v.lower())
     hits.extend((ci,vi,j)for j in range(len(tokens)-len(qw)+1)if all(tokens[j+k].startswith(w)for k,w in enumerate(qw)))
   for ci,vi,j in hits:h=(((h<<5)&0xffffffff)^(h>>27)^(ci*257)^(vi<<8)^j)&0xffffffff
   expected.append(dict(id=len(expected),query=query,hits=len(hits),hash=h,first=list(hits[0])if hits else None))
  if a.bench_query:expected=[e for e in expected if e['query']==a.bench_query]
  checks=[dict(name='Initial Genesis',chapter=0,verse=1,numbered=1,height=16)]
  for row in expected:
   if row['first'] is not None:
    ci,vi,j=row['first'];mode_keys=['Tab']if len(checks)==1 else[];checks.append(dict(name='Reset before '+row['query'],keys=reference('1 1 1'),chapter=0,verse=1,numbered=1,height=16));checks.append(dict(name='Prefix '+row['query'],keys=['Find']+mode_keys+keys(' '.join(w+'*'for w in row['query'].split()))+['Enter'],chapter=ci,verse=vi,numbered=1,height=16,match=row['query'].lower().split()[0],hit_ordinal=j))
  checks.append({**checks[-1], 'name':'Complete prefix benchmark','keys':['Z'],'scan_matches':expected[-1]['hits']})
  (out/'prefix-expected.json').write_text(json.dumps(expected,indent=2));(out/'search-option.json').write_text(json.dumps(dict(index=a.search_index,queries=queries)))
 if a.feed_quick:checks=checks[:24]
 (out/'checks.json').write_text(json.dumps(checks,indent=2))
 (out/'source-version.json').write_text(json.dumps(dict(version=a.version)))
 (out/'feed-config.json').write_text(json.dumps(dict(mode=a.native_stream)))
 script='local sample_search='+('true'if a.sample_search else'false')+'\nlocal search_bench_enabled='+('true'if a.prefix_bench or a.navigation_bench or a.search_modes_bench else'false')+'\nlocal search_bench_offset='+str(symbols.get('g_search_bench',0x80000000)-0x80000000)+'\nlocal feed_background_drain='+('true'if a.native_stream=='background'and not a.background_rapid else'false')+'\nlocal feed_file_offset='+str(symbols.get('feed_file',0x80000000)-0x80000000)+'\nlocal feed_offset='+str(symbols.get('g_feed',0x80000000)-0x80000000)+'\nlocal feed_enabled='+('true'if a.native_stream!='off'else'false')+'\nlocal lcd_module='+repl.lua(str(HERE/'NeoLCD.lua'))+'\nlocal capture_directory='+repl.lua(str(out))+'\nlocal checks='+repl.lua(checks)+'\nlocal work_offset='+str(symbols.get('g_decode_work',0x80000000)-0x80000000)+'\nlocal work_enabled='+('true'if a.work_profile else'false')+'\nlocal reader_offset='+str(symbols['g_reader']-0x80000000)+'\nlocal saved_offset='+str(symbols['g_saved']-0x80000000)+'\nlocal editor_offset='+str(symbols['editor']-0x80000000)+'\nlocal dialog_offset='+str(symbols['jump_dialog']-0x80000000)+'\n'+(HERE/'BibleReaderHarness.lua').read_text();(out/'run.lua').write_text(script)
 (out/'manifest.json').write_text(json.dumps([dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in images+[APP/'BibleReader.c',APP/'NativeFeed.h',APP/'Makefile',APP/'Search.c',HERE/'BibleReaderHarness.lua',HERE/'bible_layout.py',mame]],indent=2))
 with(out/'mame.log').open('w')as log:result=subprocess.run([str(mame),'asneo','-rompath',str(out/'roms'),'-nvram_directory',str(out/'nvram'),'-cfg_directory',str(out/'cfg'),'-video','none','-sound','none','-nothrottle','-autoboot_delay','0','-autoboot_script',str(out/'run.lua'),'-seconds_to_run','1500'],stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,SDL_VIDEODRIVER='dummy'),timeout=900)
 log=(out/'mame.log').read_text();assert result.returncode==0 and 'PASS BibleReader suite'in log and 'FAIL BibleReader'not in log,log[-2000:]
 verify(out)
def verify(out):
 checks=json.loads((out/'checks.json').read_text());books=json.loads((out/'source.json').read_bytes());chapters=[c for b in books for c in b['chapters']];reports=[]
 feed_mode=json.loads((out/'feed-config.json').read_text())['mode']if(out/'feed-config.json').exists()else'off'
 for i,c in enumerate(checks,1):
  path=out/f'checkpoint-{i:02}.lcd.json';lcd_frames(path)
  e=(out/f'editor-{i:02}.bin').read_bytes();m=struct.unpack('>12I',(out/f'metrics-{i:02}.bin').read_bytes());cursor=json.loads((out/f'cursor-{i:02}.json').read_text())
  assert m[0]==0x42524452 and m[2]==4 and m[3]==0 and m[4]==c['chapter'];assert m[11]==c['numbered'];assert 0<=cursor['x']<264 and 0<=cursor['y']<64
  profile=captured_font(out,i)if(out/f'font-{i:02}.bin').exists()else None
  lines,positions,line_starts,verse_starts=typeset(chapters[c['chapter']],bool(c['numbered']),profile['widths']if profile else None)
  gap_start,gap_end=struct.unpack_from('>II',e,0x28)
  def logical(offset):return offset-(gap_end-gap_start) if offset>=gap_end else min(offset,gap_start)
  feed=struct.unpack('>12I',(out/f'feed-{i:02}.bin').read_bytes())if feed_mode!='off'else[0]*12
  base=feed[0]
  if feed_mode!='off'and(out/f'feed-file-{i:02}.bin').exists():
   raw=(out/f'feed-file-{i:02}.bin').read_bytes();body=raw[:gap_start]+raw[gap_end:]
   encoded=b' '.join((bytes([177,12,177])+bytes(144+int(d)for d in str(v))+bytes([178,12,178])if c['numbered']else b'')+text.encode('ascii')for v,text in enumerate(chapters[c['chapter']],1))
   assert body.replace(b'\x81',b' ').replace(b'\xad',b'-')==encoded[base:feed[1]],(c['name'],'native resident file matches chapter slice',base,feed[1])
  viewport=base+logical(struct.unpack_from('>I',e,0x18)[0]);caret=base+logical(struct.unpack_from('>I',e,0x24)[0])
  def position(offset):
   if offset in positions:return positions[offset]
   prior=max(p for p in positions if p<=offset);return positions[prior]
  top,x=position(viewport);row,cx=position(caret)
  if 'caret_line'in c:assert row==c['caret_line'],(c['name'],'expected source caret row',row,c['caret_line'])
  if 'top_line'in c:assert top==c['top_line'],(c['name'],'expected scroll extent',top,c['top_line'])
  assert x==0,(c['name'],'viewport not at line start',viewport,top,x)
  height=profile['height']if profile else c.get('height',8)
  if 'height'in c:assert height==c['height'],(c['name'],'selected font height',height,c['height'])
  if c['name']=='System font picker':assert struct.unpack_from('>I',e,0x4e)[0]==0x44af8e and not profile['proportional'],('system font actually selected')
  if i==1 and c.get('font_vendor'):assert height==dict(small=11,medium=13,large=16,vlarge=21,xlarge=32,tiny=6)[c['font_vendor']],('vendor primary font',height)
  assert 0<=row-top<64//height,(c['name'],'caret not visible',row,top)
  assert (cursor['x'],cursor['y'])==(cx,(row-top)*height),(c['name'],'source cursor geometry',cursor,(cx,(row-top)*height))
  assert struct.unpack_from('>HH',e,0x14)==((64//height)*height,)*2,(c['name'],'whole-row viewport')
  expected=render(lines[top:top+64//height],height,system_font() if height==16 and profile is None else None,profile)
  if c.get('selection'):
   anchor=base+logical(struct.unpack_from('>I',e,0x38)[0]);state=struct.unpack_from('>H',e,0x36)[0];assert state!=0 and anchor!=caret,(c['name'],'native selection')
   ar,ax=position(anchor);cr,cx2=position(caret);assert ar==cr,(c['name'],'fixture selects one glyph')
   box=(min(ax,cx2),(ar-top)*height,max(ax,cx2),(ar-top+1)*height)
   selected=expected.crop(box);expected.paste(ImageChops.invert(selected.convert('L')).convert('1'),box)
  if c.get('multi_select'):
   assert feed[9]and feed[8]==0,(c['name'],'chapter-global selection anchor')
   assert base+logical(struct.unpack_from('>I',e,0x38)[0])==base,(c['name'],'native clipped anchor')
   for rr in range(top,min(row+1,top+64//height)):
    right=cx if rr==row else 264
    if right:
     box=(0,(rr-top)*height,right,(rr-top+1)*height);expected.paste(ImageChops.invert(expected.crop(box).convert('L')).convert('1'),box)
  if 'dialog'in c:
   dialog=(out/f'dialog-{i:02}.bin').read_bytes();input_state=(out/f'input-{i:02}.bin').read_bytes();ui_profile=captured_font(out,i,'dialogfont')
   assert struct.unpack_from('>H',dialog)[0]==1 and dialog[3]==14
   assert struct.unpack_from('>4H',dialog,4+0xd0)==(53,0,264,11)
   text='Go to: '+c['dialog'];assert input_state[4:4+len(text)]==text.encode('ascii')
   expected.paste(0,(0,53,264,64));px=expected.load();x=2
   for dx in range(264):px[dx,52]=1
   for char in text:
    width=ui_profile['widths'][ord(char)];glyph=ui_profile['glyphs'][ord(char)]
    for y in range(11):
     for dx in range(width):
      if(glyph[(y//8)*width+dx]>>(y%8))&1:px[x+dx,53+y]=1
    x+=width
   reverse=struct.unpack_from('>H',input_state,2)[0];caret_at=len(text)-reverse
   caret_x=2+sum(ui_profile['widths'][ord(ch)]for ch in text[:caret_at])
   assert dialog[4+0x112]==2 and dialog[4+0x113]==1 and dialog[4+0x11c]==0
   for y in range(56,64):
    for dx in range(2):px[caret_x+dx,y]=1
  if c.get('mode')==3:
   # Explicit overlay expectations, drawn over the independently typeset body.
   from bible_layout import font
   from PIL import Image
   def ui(row,text):
    expected.paste(0,(0,row*8,264,row*8+8));px=expected.load()
    for col,ch in enumerate(text[:44]):
     for dy in range(8):
      for dx in range(6):
       if font[dy*1536+ord(ch)*6+dx]:px[col*6+dx,row*8+dy]=1
   ui(6,c.get('notice','Copied verse(s) with citation' if c.get('clipboard') else 'Invalid or ambiguous reference'))
   ui(7,'Esc: return    G: go to    Find: search')
  reference_file=out/f'expected-{i:02}.png';ImageChops.invert(expected.convert('L')).save(reference_file)
  comparison=compare([path],reference_file,out/f'comparison-{i:02}')
  record=json.loads(path.read_text())
  for sample in record['samples']:
   for controller in sample['controllers']:
    assert not any(b&1 for b in bytes.fromhex(controller['ram'])[8*132:9*132]),(c['name'],'independent physical row 65 must be blank')
    for flag,value in dict(m_start_line=0,m_display_on=1,m_adc=0,m_com_reverse=0,m_reverse=0,m_all_points=0,m_reset=0).items():assert controller[flag]==value,(c['name'],flag)
  if 'scan_matches'in c:assert m[10]==c['scan_matches'],('full corpus benchmark hit count',m[10])
  if 'match'in c:
   verse_text=chapters[c['chapter']][c['verse']-1]
   hits=list(re.finditer(r"[A-Za-z]+(?:'[A-Za-z]+)*",verse_text))if 'hit_ordinal'in c else[m for m in re.finditer(r"[A-Za-z]+(?:'[A-Za-z]+)*",verse_text)if m.group().lower().startswith(c['match'])]
   raw_start=verse_starts[c['verse']-1]+(6+len(str(c['verse']))if c['numbered']else 0)+hits[c.get('hit_ordinal',c.get('occurrence',0))].start()
   assert caret==raw_start,(c['name'],'exact found-word anchor',caret,raw_start)
   assert cursor['mode']==15,(c['name'],'found word cursor must be visible')
  if 'verse'in c:assert caret>=verse_starts[c['verse']-1] and (c['verse']==len(verse_starts) or caret<verse_starts[c['verse']]),(c['name'],'source verse anchor')
  if c.get('resume'):
   calls,status,saved_position,saved_chapter,saved_numbers=struct.unpack('>5I',(out/f'saved-{i:02}.bin').read_bytes())
   assert calls>=1 and status==0 and saved_chapter==c['chapter'] and saved_numbers==c['numbered'],(c['name'],'native saved state')
   assert saved_position==struct.unpack_from('>I',e,0x18)[0],(c['name'],'saved native viewport',saved_position,viewport)
   assert reports[-1]['logical_viewport']==viewport and reports[-1]['logical_caret']==caret,(c['name'],'A5 caret and viewport retained')
  if c.get('clipboard')and(c.get('copy_entire')or'copy_prefix_line'in c):
   span_end=len(encoded)if c.get('copy_entire')else line_starts[c['copy_prefix_line']]
   events=[];off=0
   for vv,text in enumerate(chapters[c['chapter']],1):
    if vv>1:events.append((off,' ',vv-1));off+=1
    if c['numbered']:off+=6+len(str(vv))
    for char in text:events.append((off,char,vv));off+=1
   selected=[(char,vv)for off,char,vv in events if off<span_end];last=selected[-1][1]
   b=next(b for b in reversed(range(66))if sum(len(x['chapters'])for x in books[:b])<=c['chapter']);local=c['chapter']-sum(len(x['chapters'])for x in books[:b])+1
   cite=books[b]['name']+f' {local}:1'+(f'-{last}'if last>1 else'')+f' ({json.loads((out/"source-version.json").read_text())["version"]})'
   assert(out/f'clipboard-{i:02}.bin').read_bytes()==(''.join(ch for ch,v in selected)+'\r'+cite).encode('ascii'),(c['name'],'exact selected text and citation')
  elif c.get('clipboard'):
   b=next(b for b in reversed(range(66))if sum(len(x['chapters'])for x in books[:b])<=c['chapter']);local=c['chapter']-sum(len(x['chapters'])for x in books[:b]);verse=c['verse'];expected=chapters[c['chapter']][verse-1]+'\r'+books[b]['name']+f' {local+1}:{verse} ('+(json.loads((out/"source-version.json").read_text())["version"]if(out/"source-version.json").exists()else'KJV')+')';assert(out/f'clipboard-{i:02}.bin').read_bytes()==expected.encode('ascii')
  reports.append(dict(logical_viewport=viewport,logical_caret=caret,name=c['name'],chapter=m[4],verse=m[5],cursor=cursor,viewport=struct.unpack_from('>I',e,0x18)[0],caret=struct.unpack_from('>I',e,0x24)[0],gap=struct.unpack_from('>II',e,0x28),feed=list(feed),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bitmap=comparison,font_height=height,proportional=profile['proportional'] if profile else False))
 (out/'results.json').write_text(json.dumps(dict(status='passed',results=reports),indent=2)+'\n');print(json.dumps(reports,indent=2))
if __name__=='__main__':main()
