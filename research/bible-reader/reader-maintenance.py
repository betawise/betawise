#!/usr/bin/env python3
"""Reproducible active-C maintenance proxies, independent of source formatting.

GCC preprocesses each production variant with its real flags; Clang parses the
result for function/decision counts. Exclude SDK, generated assets and firmware.
Reader/frontend totals are separate from the shared Huffman/search modules.
CC = 1/function + if/for/while/do/case/?:/&&/||. This is a structural proxy,
not a subjective maintainability score or a substitute for interface stability.
"""
import argparse,bisect,json,re,subprocess
from prototype_support import prototype_app, prototype_test
from pathlib import Path
APP=prototype_app()
TOKEN=re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_]\w*|(?:0[xX][0-9a-fA-F]+|\d+(?:\.\d*)?)(?:[uUlLfF]*)|>>=|<<=|->|\+\+|--|&&|\|\||==|!=|<=|>=|<<|>>|\+=|-=|\*=|/=|%=|&=|\|=|\^=|[^\s]')
MARKER=re.compile(r'^#\s+\d+\s+"([^"]+)"')
OWN={'BibleReader.c','NativeFeed.h','NativePrewrap.h','Streaming.c','HuffmanDecoder.c','Search.c'}
def decision_count(node):
 n=int(node.get('kind')in{'IfStmt','ForStmt','WhileStmt','DoStmt','CaseStmt','ConditionalOperator','BinaryConditionalOperator'})
 n+=int(node.get('kind')=='BinaryOperator'and node.get('opcode')in{'&&','||'})
 return n+sum(decision_count(x)for x in node.get('inner',[]))
def analyze(folder):
 units=[]
 for path in sorted(folder.glob('*.i')):
  code=path.read_text();offset=0;current='';starts=[];files=[];pieces={}
  for line in code.splitlines(keepends=True):
   marker=MARKER.match(line)
   if marker:current=Path(marker[1]).name
   starts.append(offset);files.append(current)
   if not marker and current in OWN:pieces.setdefault(current,[]).append(line)
   offset+=len(line.encode())
  astfile=path.with_suffix('.ast.json')
  with astfile.open('w')as out:subprocess.run(['clang','-target','m68k-unknown-elf','-fshort-enums','-fpack-struct=2','-fsyntax-only','-Wno-everything','-Xclang','-ast-dump=json',str(path)],stdout=out,stderr=subprocess.PIPE,check=True)
  ast=json.loads(astfile.read_text());functions=[]
  for node in ast.get('inner',[]):
   if node.get('kind')!='FunctionDecl':continue
   body=next((x for x in node.get('inner',[])if x.get('kind')=='CompoundStmt'),None)
   if body is None:continue
   loc=node.get('loc',{});loc=loc.get('expansionLoc',loc);pos=loc.get('offset')
   if pos is None:continue
   source=files[bisect.bisect_right(starts,pos)-1]
   if source not in OWN:continue
   functions.append(dict(name=node['name'],source=source,cc=1+decision_count(body)))
  units.append(dict(unit=path.stem,source_tokens={k:len(TOKEN.findall(''.join(v)))for k,v in pieces.items()},functions=functions))
 def total(frontend):
  fs=[f for u in units for f in u['functions']if(not frontend or f['source']in{'BibleReader.c','NativeFeed.h','NativePrewrap.h','Streaming.c'})]
  tokens=sum(n for u in units for k,n in u['source_tokens'].items()if(not frontend or k in{'BibleReader.c','NativeFeed.h','NativePrewrap.h','Streaming.c'}))
  return dict(c_tokens=tokens,functions=len(fs),cc_sum=sum(f['cc']for f in fs),cc_max=max(f['cc']for f in fs))
 return dict(parser_version=subprocess.check_output(['clang','--version'],text=True).splitlines()[0],preprocessor_version=subprocess.check_output(['m68k-linux-gnu-gcc','--version'],text=True).splitlines()[0],target_struct_alignment=2,method='preprocessed C; CC=1/function + if/for/while/do/case/?:/&&/||; assets/SDK/firmware excluded',frontend=total(True),including_codec_search=total(False),translation_units=units)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path);a=p.parse_args();d=analyze(a.folder);(a.folder/'metrics.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d['frontend']))
