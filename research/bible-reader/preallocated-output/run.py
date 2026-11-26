#!/usr/bin/env python3
"""Run canonical deterministic MAME oracles against isolated variants."""
import argparse
from pathlib import Path
import sys
from prepare import prepare, ROOT, HERE


def benchmark_cases(books, version):
    from biblewise_cases import reference
    from bible_rich import source_expected
    def chapter(book, number): return sum(len(b['chapters'])for b in books[:book])+number-1
    def row(name, actions=None, **kw):
        d=dict(name=name,chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12)
        if actions is not None:d['keys']=actions
        d.update(kw);return d
    cor=chapter(45,13);john=chapter(42,3);ps=chapter(18,119)
    selected=' '.join(word for word,_ in source_expected(version.lower(),'Psalm',119)[0])
    body=' '.join(books[18]['chapters'][118])
    short=books[45]['chapters'][12][3]
    return [row('Load Genesis 1'),
        row('Load 1 Corinthians 13',reference('1 Cor 13'),chapter=cor),
        row('Select short verse',reference('1 Cor 13:4'),chapter=cor,verse=4,rich_selection='verse'),
        row('Copy short verse',[['Left Ctrl','C']],chapter=cor,verse=4,rich_selection='verse',clipboard=True,
            clipboard_text=short+'\r1 Corinthians 13:4 ('+version+')',status=True,message=True,status_text='Copied'),
        row('Load John 3',reference('John 3'),chapter=john),
        row('Load Psalm 119',reference('Ps 119'),chapter=ps),
        row('Select whole Psalm',[['Left Shift','End']],chapter=ps,verse=176,rich_selection=selected),
        row('Copy whole Psalm',[['Left Ctrl','C']],chapter=ps,verse=176,rich_selection=selected,clipboard=True,
            clipboard_text=selected+'\rPsalm 119:1-176 ('+version+')',status=True,message=True,status_text='Copied'),
        row('Hide headings',['H'],chapter=ps,verse=176,headings=False,rich_selection=selected),
        row('Copy body only',[['Left Ctrl','C']],chapter=ps,verse=176,headings=False,rich_selection=selected,clipboard=True,
            clipboard_text=body+'\rPsalm 119:1-176 ('+version+')',status=True,message=True,status_text='Copied'),
        row('Restore headings',['H'],chapter=ps,verse=176,rich_selection=selected),
        row('Seek after copy',reference('Ps 119:2'),chapter=ps,verse=2,rich_selection='verse'),
        row('Resume reconstructed Psalm',['Applets','Home','Enter','Applets','Down','Enter'],chapter=ps,verse=2,
            rich_selection='verse',resume=True),
        row('Reload Genesis',reference('Gen 1'))]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('variant',choices=('baseline','fresh-file','direct-decode','native-copy','combined'))
    p.add_argument('--bench',action='store_true')
    args,remaining=p.parse_known_args()
    app=prepare(args.variant)
    script=ROOT/'tests/mame/asneo/check-biblewise.py'
    source=script.read_text().replace("APP = ROOT / 'betawise/applets/BibleWise'", 'APP = Path('+repr(str(app))+')')
    if args.variant in ('native-copy','combined'):
        marker="    if args.case != 'native': clear_previous_find_queries(checks)"
        adjustment="""    # One-shot native copy can reuse the first raw allocation on the second
    # copy. Require the first relocation; verify subsequent reuse separately.
    for check in checks:
        if check['name'] == 'Copy only visible text with headings hidden':
            check.pop('clipboard_relocation', None)
            check['native_copy_reuse'] = True
"""
        source=source.replace(marker,adjustment+marker)
    if args.bench:
        marker="    if args.case != 'native': clear_previous_find_queries(checks)"
        assert marker in source
        source=source.replace(marker,'    checks = benchmark_cases(books, args.version)\n'+marker)
    harness=(script.parent/'BibleWiseHarness.lua').read_text()
    marker="  dump(string.format('chapter-%02d.bin',index),ptr,n)"
    assert marker in harness
    harness=harness.replace(marker,marker+"\n  dump(string.format('chapter-allocation-%02d.bin',index),record,24)")
    allocations = r"""
local allocation_events={}
local allocation_tap
local function allocation_snapshot(event)
 local record=memory:read_u32(0x34d2)
 local clip=memory:read_u32(0x34da)
 local n,cap,res=0,0,0
 if record>=0x1000 and record<0x80000 and memory:read_u16(record+0x44)==1 then
  n=memory:read_u32(record+4);cap=memory:read_u32(record+12);res=memory:read_u32(record+16)
 end
 allocation_events[#allocation_events+1]={check=index,event=event,time=machine.time:as_double(),length=n,capacity=cap,reservation=res,
  clip_length=memory:read_u32(clip+4),clip_capacity=memory:read_u32(clip+12),clip_reservation=memory:read_u32(clip+16)}
end
"""
    harness=harness.replace('local function save_timings()',allocations+'\nlocal function save_timings()')
    marker=" local f=assert(io.open(capture_directory..'/timings.json','w'))"
    allocation_save=r""" local af=assert(io.open(capture_directory..'/allocations.json','w'));af:write('[')
 for i,a in ipairs(allocation_events)do
  if i>1 then af:write(',')end
  af:write(string.format('{"check":%d,"event":"%s","time":%.12f,"length":%d,"capacity":%d,"reservation":%d,"clip_length":%d,"clip_capacity":%d,"clip_reservation":%d}',a.check,a.event,a.time,a.length,a.capacity,a.reservation,a.clip_length,a.clip_capacity,a.clip_reservation))
 end
 af:write(']');af:close()
"""
    harness=harness.replace(marker,allocation_save+marker)
    marker="    timing_tap=memory:install_write_tap"
    tap=r"""    if copy_probe_offset and copy_probe_offset>0 then
     local address=ram+copy_probe_offset
     allocation_tap=memory:install_write_tap(address,address+3,'copy_allocations',function(offset,data,mask)
      if offset==address+2 and(mask&65535)~=0 and data>0 then allocation_snapshot('copy-'..data)end
     end)
    end
"""
    harness=harness.replace(marker,tap+marker)
    marker="     if offset==bench+10 and(mask&65535)~=0 then"
    harness=harness.replace(marker,marker+"\n      if data==3 or data==2 or data==900 or data==901 then allocation_snapshot('phase-'..data)end")
    source=source.replace("(HERE / 'BibleWiseHarness.lua').read_text()",repr(harness))
    sys.path.insert(0,str(script.parent))
    sys.argv=[str(script),*remaining]
    exec(compile(source,str(script),'exec'),{'__name__':'__main__','__file__':str(script),'benchmark_cases':benchmark_cases})
    import json, struct
    if '--output' in remaining:
        output=Path(remaining[remaining.index('--output')+1])
        for i, check in enumerate(json.loads((output/'checks.json').read_text()),1):
            if check.get('native_copy_reuse'):
                writes,moves,*_=struct.unpack('>8I',(output/f'copy-relocation-{i:02}.bin').read_bytes())
                assert writes==3 and moves==0, 'second native copy reuses its existing allocation'



if __name__=='__main__':main()
