#!/usr/bin/env python3
"""Exercise original dictionary/provider entry points in disposable Neo MAME RAM."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('output',type=Path)
p.add_argument('--word',default='happy')
p.add_argument('--image',default='Ghidra/Alphasmart Neo/SmartApplets/thesaurus_small_usa.os3kapp')
a=p.parse_args()
out=a.output.resolve()
if out.exists() and any(out.iterdir()):
    p.error('output directory must be new or empty; preserve previous evidence')
try:
    word_bytes=a.word.encode('ascii')
except UnicodeEncodeError:
    p.error('--word must be ASCII for this probe')
if not 3 <= len(word_bytes) <= 50:
    p.error('--word must contain 3–50 bytes for the truncation cases')
out.mkdir(parents=True,exist_ok=True)
image=ROOT/a.image;b=image.read_bytes()
manifest=json.loads((HERE.parent/'abi-audit/vendor-image-inventory.json').read_text())
e=next(e for e in manifest if e['path']==a.image)
assert hashlib.sha256(b).hexdigest()==e['sha256']
ram_size=int.from_bytes(b[8:12],'big');entry=int.from_bytes(b[0x84:0x88],'big')
assert 0x10000+len(b)<=0x6b000 and 0x6b000+ram_size<=0x74000
cases='''add('init',0x18,nil,nil,true)
add('count-before',2,nil,nil)
add('query-lookup',0,function()
 put(wordbuf,@WORD@);m:write_u32(param,wordbuf);m:write_u8(param+4,@WORD_LEN@);m:write_u32(param+6,records);m:write_u16(param+10,16);m:write_u32(param+12,outcount);m:write_u16(outcount,0xa5a5);fill(records,160,0xa5)
end,function()
 local n=m:read_u16(outcount);assert(n<=16);if expected_lookup_count then eq(n,expected_lookup_count)end;eq(m:read_u8(records+160),0xa5)
 print('RECORDS query count='..n..' bytes='..hex(records,10*n))
 for i=0,n-1 do record_text('query-'..i,records+10*i)end
end)
add('count-after',2,nil,nil)
add('entry-zero',1,function()m:write_u16(param,0);m:write_u32(param+2,records+0x100)end,function()print('ENTRY0 '..hex(records+0x100,10))end)
'''
if e['name'].startswith('Thesaurus'):
    cases+='''add('lookup-truncated',0,function()
 put(wordbuf,@WORD@);m:write_u32(param,wordbuf);m:write_u8(param+4,@WORD_LEN@);m:write_u32(param+6,records+0x500);m:write_u16(param+10,0);m:write_u32(param+12,outcount);m:write_u16(outcount,0xa5a5)
end,function()eq(m:read_u32(reply),0);eq(m:read_u16(outcount),0)end)
add('lookup-missing',0,function()
 put(wordbuf,'qzxqzx');m:write_u32(param,wordbuf);m:write_u8(param+4,6);m:write_u32(param+6,records+0x500);m:write_u16(param+10,16);m:write_u32(param+12,outcount);m:write_u16(outcount,0xa5a5)
end,function()eq(m:read_u32(reply),1);eq(m:read_u16(outcount),0)end)
add('lookup-too-long',0,function()
 put(wordbuf,string.rep('x',51));m:write_u32(param,wordbuf);m:write_u8(param+4,51);m:write_u32(param+6,records+0x500);m:write_u16(param+10,16);m:write_u32(param+12,outcount);m:write_u16(outcount,0xa5a5)
end,function()eq(m:read_u32(reply),1);eq(m:read_u16(outcount),0)end)
add('headword-truncated',3,function()
 fill(wordbuf,8,0xa5);m:write_u32(param,records);m:write_u32(param+4,wordbuf);m:write_u8(param+8,3);m:write_u32(param+10,outcount);m:write_u8(outcount,0xa5)
end,function()eq(m:read_u32(reply),0);eq(m:read_u8(outcount),3);eq(m:read_u8(wordbuf+3),0xa5)end)
add('related-truncated',5,function()
 fill(wordbuf,8,0xa5);m:write_u32(param,records);m:write_u32(param+4,wordbuf);m:write_u16(param+8,0);m:write_u32(param+10,outcount);m:write_u8(param+14,0);m:write_u16(outcount,0xa5a5)
end,function()eq(m:read_u32(reply),0);eq(m:read_u16(outcount),0);eq(m:read_u8(wordbuf),0xa5)end)
add('enum-out-of-range',1,function()
 m:write_u16(param,m:read_u16(ram+0x28));m:write_u32(param+2,records+0x600);fill(records+0x600,10,0xa5)
end,function()eq(m:read_u32(reply),0);assert(hex(records+0x600,10)==string.rep('a5',10))end)
add('unsupported',7,nil,function()eq(m:read_u32(reply),0)end)
'''
if e['name'].startswith('SpellCheck'):
    cases='''add('init',0x18,nil,nil,true)
local function spell_request(text,capacity)
 put(wordbuf+0x400,text);fill(wordbuf,256,0xa5);m:write_u32(param,#text);m:write_u32(param+4,wordbuf+0x400);m:write_u32(param+8,capacity);m:write_u32(param+12,0);m:write_u32(param+16,wordbuf)
end
local function spell_result()
 local n=m:read_u32(param+12);assert(n<=256)
 local expected={['spell-enabled']='01',['spell-cat']='00',['spell-nonsense']='ff',['spell-disable']='',['spell-disabled']='00',['spell-interactive-disabled']='0c',['spell-enable']='',['spell-reenabled']='01',['spell-unsupported']=''}
 local label=cases[index].label;assert(hex(wordbuf,n)==expected[label],label..' unexpected result');eq(m:read_u32(reply),label=='spell-unsupported' and 1 or 0);eq(m:read_u8(wordbuf+n),0xa5)
 print('SPELL bytes='..hex(wordbuf,n)..' length='..n)
end
add('spell-enabled',7,function()spell_request('',1)end,spell_result)
add('spell-cat',1,function()spell_request('cat',1)end,spell_result)
add('spell-nonsense',1,function()spell_request('qzxqzx',1)end,spell_result)
add('spell-disable',6,function()spell_request('',0)end,spell_result)
add('spell-disabled',7,function()spell_request('',1)end,spell_result)
add('spell-interactive-disabled',3,function()spell_request('cat',1)end,spell_result)
add('spell-enable',5,function()spell_request('',0)end,spell_result)
add('spell-reenabled',7,function()spell_request('',1)end,spell_result)
add('spell-unsupported',0,function()spell_request('',0)end,spell_result)
'''
if e['name'] in ['CW_Topics','CW_MainDictionary']:
    cases='''add('init',0x18,nil,nil,true)
add('data',1,function()m:write_u32(param,0xa5a5a5a5)end,function()
 eq(m:read_u32(param),image+0x106);eq(m:read_u32(reply),0);eq(m:read_u32(reply+4),image+0x106);eq(m:read_u32(reply+8),0xa5a5a5a5)
 print('DATA pointer='..string.format('%x',m:read_u32(param))..' magic='..hex(image+0x106,10))
end)
add('unsupported',2,function()m:write_u32(param,0x12345678)end,function()eq(m:read_u32(reply),0);eq(m:read_u32(param),0x12345678);eq(m:read_u32(reply+4),0xa5a5a5a5)end)
'''
expect={}
if 'USA' in e['name'] and e['name'].startswith('Thesaurus') and a.word=='happy':expect={'query-0':'pleasant','query-1':'cheerful','query-0-opposite':'disagreeable','query-1-opposite':'dejected'};cases='expected_lookup_count=2\n'+cases
elif e['name'].startswith('Thesaurus Spanish') and a.word=='feliz':expect={'query-0':'feliz'};cases='expected_lookup_count=1\n'+cases
for label,text in expect.items():cases='expected_text['+json.dumps(label)+']='+json.dumps(text.encode().hex())+'\n'+cases
cases=cases.replace('@WORD@',json.dumps(a.word)).replace('@WORD_LEN@',str(len(a.word.encode('ascii'))))
script=(HERE/'probe.lua.in').read_text()
for key,value in {'IMAGE':str(image),'IMAGE_SIZE':len(b),'RAM_SIZE':ram_size,'ENTRY':entry,'CASES':cases,'KIND':e['name']}.items():script=script.replace('@'+key+'@',str(value))
assert '@' not in script
(out/'probe.lua').write_text(script)
romdir=out/'roms/asneo';romdir.mkdir(parents=True,exist_ok=True)
for name in ['os3kneorom.os3kos','smallos3kneorom.os3kos']:
 target=romdir/name
 if not target.exists():target.symlink_to(ROOT/'Ghidra/Alphasmart Neo/SmartApplets'/name)
cmd=[ROOT/'mame/neodiag','asneo','-rompath',out/'roms','-nvram_directory',out/'nvram','-cfg_directory',out/'cfg','-video','none','-sound','none','-nothrottle','-seconds_to_run','40','-autoboot_delay','0','-autoboot_script',out/'probe.lua']
with (out/'mame.log').open('w')as log:
 result=subprocess.run(list(map(str,cmd)),cwd=out,env={**os.environ,'SDL_VIDEODRIVER':'dummy'},stdout=log,stderr=subprocess.STDOUT,timeout=120)
text=(out/'mame.log').read_text(errors='replace')
results=[{'label':m[1],'selector':int(m[2],16),'reply_hex':m[3]}for m in re.finditer(r'^RESULT (\S+) selector=([0-9a-f]+) reply=([0-9a-f]+)',text,re.M)]
(out/'results.json').write_text(json.dumps({'cases':results,'passed':'PASS dictionary API probe' in text and 'FAIL dictionary API' not in text,'log_sha256':hashlib.sha256(text.encode()).hexdigest()},indent=2)+'\n')
(out/'manifest.json').write_text(json.dumps({'image':a.image,'sha256':e['sha256'],'entry':entry,'ram_size':ram_size,'returncode':result.returncode,'word':a.word},indent=2)+'\n')
print('\n'.join(l for l in text.splitlines() if any(l.startswith(s)for s in ['READY','GROUPS','RESULT','TEXT','RELATED','NEXT','SPELL','SUGGEST','DATA','RECORDS','ENTRY0','PASS','FAIL'])))
assert result.returncode==0 and 'PASS dictionary API probe' in text and 'FAIL dictionary API'not in text,text[-1800:]
