#!/usr/bin/env python3
"""Measure production reader images, keeping corpus/index and font policy equal."""
import argparse,hashlib,importlib.util,json,re,shutil,struct,subprocess
from prototype_support import prototype_app, prototype_test
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];APP=prototype_app()
spec=importlib.util.spec_from_file_location('maintenance',Path(__file__).with_name('reader-maintenance.py'));maintenance=importlib.util.module_from_spec(spec);spec.loader.exec_module(maintenance)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);p.add_argument('--version',default='NKJV',choices=['KJV','NKJV']);p.add_argument('--only',help='measure one named variant');a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 data=ROOT/'.research-work/bible-compression/reader-viewer'/a.version.lower();shared=sum((data/f).stat().st_size for f in ['container.bin','search.bin','pruning.bin','verses.bin']);rows=[]
 for name,reader,mode,roll,fast in [('native-original','BibleReader',0,0,0),('native-optimized','BibleReader',0,0,1),('native-window','BibleReader',1,0,0),('native-demand','BibleReader',2,0,0),('native-background','BibleReader',3,0,0),('native-lookahead','BibleReader',4,0,0),('native-viewport','BibleReader',5,0,0),('native-prewrap','BibleReader',6,0,0),('native-prewrap-full','BibleReader',7,0,0),('custom-repaint','Streaming',0,0,0),('custom-lcd-roll','Streaming',0,1,0)]:
  if a.only and name!=a.only:continue
  flags=dict(READER=reader,VERSION=a.version,PRUNE=1,PROFILE=0,TEST_FONT=0,WORK_PROFILE=0,NATIVE_STREAM=mode,LCD_ROLL=roll,NATIVE_OPEN_TEST=fast,NATIVE_PAGE_TEST=int(reader=='BibleReader'and bool(mode or fast)))
  target=('BibleReader-Stream'if reader=='Streaming'else{0:'BibleReader',1:'BibleReader-NativeWindow',2:'BibleReader-NativeDemand',3:'BibleReader-NativeBG',4:'BibleReader-NativeLookahead',5:'BibleReader-NativeViewport',6:'BibleReader-NativePrewrap',7:'BibleReader-NativePrewrapFull'}[mode])+(''if a.version=='KJV'else'-'+a.version)+'.OS3KApp'
  folder=out/name;folder.mkdir();flags['LINK_MAP']=str(folder/'link.map')
  with(folder/'build.log').open('w')as f:subprocess.run(['make','-C',str(APP),*[f'{k}={v}'for k,v in flags.items()]],stdout=f,stderr=subprocess.STDOUT,check=True)
  image=(APP/target).read_bytes();assert image[:4]==bytes.fromhex('c0ffeead')
  shutil.copyfile(APP/target,folder/target)
  shutil.copyfile(APP/target.replace('.OS3KApp','.elf'),folder/target.replace('.OS3KApp','.elf'))
  for source in ['BibleReader.c','NativeFeed.h','NativePrewrap.h','Streaming.c','Makefile','HuffmanDecoder.c','Search.c','Superscript.h','generate_superscript.py']:
   shutil.copyfile(APP/source,folder/source)
  subprocess.run(['m68k-linux-gnu-nm','-n','-S',str(APP/target.replace('.OS3KApp','.elf'))],stdout=(folder/'symbols.txt').open('w'),check=True)
  for su in APP.glob('*.su'):shutil.copyfile(su,folder/su.name)
  metricsdir=folder/'maintenance'
  with(folder/'maintenance-build.log').open('w')as f:subprocess.run(['make','-C',str(APP),'maintenance-inputs',*[f'{k}={v}'for k,v in flags.items()],f'METRICS_DIR={metricsdir}'],stdout=f,stderr=subprocess.STDOUT,check=True)
  metrics=maintenance.analyze(metricsdir);(metricsdir/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
  # Retained input .text sections in the final link map include assembly syscall
  # stubs too; symbol STT_FUNC totals alone would miss those.
  text_bytes=0;section='';mapped=False
  for line in (folder/'link.map').read_text().splitlines():
   if 'Linker script and memory map'in line:mapped=True
   if not mapped:continue
   m=re.match(r'^ (\.\S+)(?:\s+(.*))?$',line)
   if m:section=m[1];tail=m[2]or''
   else:tail=line.strip()
   m=re.match(r'0x[0-9a-f]+\s+0x([0-9a-f]+)\s+.+',tail)
   if m and(section=='.text'or section.startswith('.text.')):text_bytes+=int(m[1],16);section=''
  symbols=(folder/'symbols.txt').read_text();font_bytes=sum(int(m[1],16)for line in symbols.splitlines()if(m:=re.match(r'^[0-9a-f]+\s+([0-9a-f]+)\s+[a-zA-Z]\s+(superscript_(?:widths|offsets|bitmaps))$',line)))
  navigation_bytes=sum(int(m[1],16)for line in symbols.splitlines()if(m:=re.match(r'^[0-9a-f]+\s+([0-9a-f]+)\s+[a-zA-Z]\s+books$',line)))
  assert navigation_bytes==1848,(name,navigation_bytes)
  assert text_bytes>0 and text_bytes<len(image)-shared,(name,text_bytes)
  rows.append(dict(application_rom_bytes=len(image)-shared-navigation_bytes,bible_navigation_bytes=navigation_bytes,executable_bytes=text_bytes,font_bytes=font_bytes,maintenance=metrics,name=name,flags=flags,rom_bytes=len(image),a5_bytes=struct.unpack_from('>I',image,8)[0],common_resource_bytes=shared,other_rom_bytes=len(image)-shared,sha256=hashlib.sha256(image).hexdigest(),binary=str(folder/target)))
 (out/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
 print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
