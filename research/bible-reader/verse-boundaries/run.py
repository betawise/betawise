#!/usr/bin/env python3
"""Run the canonical MAME verifier against an isolated boundary-table applet."""
import argparse
from pathlib import Path
import sys
import fcntl
import subprocess
from prepare import ROOT, prepare


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant',choices=['baseline','one','sparse','none','file','fast','file-nocache','binary','marker','marker-bmh','linear','lean','compact-binary','tiny-binary','small-binary','direct-linear','direct-binary','end-gap','eof-linear','eof-binary','readonly-view','readonly-prewrapped','eof-fast-linear','eof-fast-binary','editable-retained','editable-cached','cached-direct-binary','cached-direct-marker','cached-direct-bmh'],required=True)
    parser.add_argument('--boundary-bench',action='store_true')
    parser.add_argument('--first-checks',type=int)
    parser.add_argument('--focus-smoke',action='store_true')
    parser.add_argument('--selection-focus-smoke',action='store_true')
    parser.add_argument('--navigation-profile',action='store_true')
    parser.add_argument('--page-profile',action='store_true')
    parser.add_argument('--long-profile',action='store_true')
    parser.add_argument('--relocation-profile',action='store_true')
    args,remaining=parser.parse_known_args()
    version=remaining[remaining.index('--version')+1] if '--version' in remaining else 'KJV'
    app=prepare(args.variant, '-KJV' if version=='KJV' else '', relocation=args.relocation_profile)
    with (Path(__file__).parent/'build/sdk.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        subprocess.run(['make','-s','-C',str(ROOT/'os3k')],check=True)
    script=ROOT/'tests/mame/asneo/check-biblewise.py'
    source=script.read_text().replace("APP = ROOT / 'betawise/applets/BibleWise'",'APP = Path('+repr(str(app))+')')
    if args.boundary_bench:
        first=source.index("        if args.case == 'italic-retention':")
        last=source.index("        if args.case == 'italic-interactions':",first)
        body="""        if args.case == 'italic-retention':
            checks=[dict(name='Initial',chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12)]
            samples=[('Gen 1:1',0,1),('Gen 1:16',0,16),('Gen 1:17',0,17),('Gen 1:31',0,31),
                ('Ps 119:1',596,1),('Ps 119:16',596,16),('Ps 119:17',596,17),
                ('Ps 119:32',596,32),('Ps 119:33',596,33),('Ps 119:160',596,160),
                ('Ps 119:161',596,161),('Ps 119:175',596,175),('Ps 119:176',596,176)]
            for ref,chapter,verse in samples:
                base=dict(chapter=chapter,verse=verse,numbered=1,rich=True,cursor_mode=12,rich_selection='verse')
                checks.append(dict(base,name=ref+' cold',keys=reference(ref)))
                if verse in (16,17,176):checks.append(dict(base,name=ref+' repeated',keys=reference(ref)))
                if verse in (16,176):
                    book_index=0 if chapter==0 else 18
                    local=0 if chapter==0 else 118
                    citation=books[book_index]['name']+' '+str(local+1)+':'+str(verse)
                    checks.append(dict(base,name=ref+' copy',keys=[['Left Ctrl','C']],clipboard=True,
                        clipboard_text=books[book_index]['chapters'][local][verse-1]+'\\r'+citation+' ('+args.version+')',
                        message=True,status=True,status_text='Copied'))
"""
        source=source[:first]+body+source[last:]
    if args.variant in ('none','file','fast','file-nocache','binary','marker','marker-bmh','linear','lean','compact-binary','tiny-binary','small-binary','direct-linear','direct-binary','end-gap','eof-linear','eof-binary','readonly-view','readonly-prewrapped','eof-fast-linear','eof-fast-binary','editable-retained','editable-cached','cached-direct-binary','cached-direct-marker','cached-direct-bmh'):
        marker="        if args.case == 'italic-source-flags':"
        extra="""        if args.case == 'italic-interactions':
            origin=len(checks)
            checks.append(dict(partial,name='Retain file and selection across AlphaWord',
                keys=['Applets','Home','Enter','Applets','Down','Enter'],resume=True,
                preserve_view=origin,retained_from=origin))
            first=dict(chapter=john+2,verse=1,numbered=1,rich=True,cursor_mode=12,rich_selection='verse')
            checks.append(dict(first,name='Cold lookup after file gap moved',keys=reference('John 3:1')))
            checks.append(dict(first,name='Copy after focus and gap move',keys=[['Left Ctrl','C']],
                clipboard=True,clipboard_text=books[42]['chapters'][2][0]+'\\rJohn 3:1 ('+args.version+')',
                message=True,status=True,status_text='Copied'))
"""
        assert marker in source
        source=source.replace(marker,extra+marker)
    if args.page_profile:
        marker="    (output / 'checks.json').write_text"
        extra="""    checks=checks[:1]
    base=dict(checks[0]);base.pop('verse',None)
    checks.append(dict(base,name='Native page forward',keys=['Space'],page_number=1,cursor_mode=12))
    checks.append(dict(base,name='Native page back',keys=[['Left Shift','Space']],page_number=0,cursor_mode=12))
"""
        source=source.replace(marker,extra+marker)
    if args.navigation_profile:
        marker="    (output / 'checks.json').write_text"
        extra="""    checks=checks[:2]
    checks.append(dict(checks[1],name='Native selection expand',keys=[['Left Shift','Right'],['Left Shift','Right']],rich_selection='th',cursor_mode=15))
    checks.append(dict(checks[1],name='Native selection shrink',keys=[['Left Shift','Left']],rich_selection='t',cursor_mode=15))
    checks.append(dict(checks[1],name='Native selection collapse',keys=['Left'],cursor_mode=15))
    checks.append(dict(checks[1],name='Profile focus return',keys=['Applets','Home','Enter','Applets','Down','Enter'],resume=True,preserve_view=5,retained_from=5,cursor_mode=12))
"""
        source=source.replace(marker,extra+marker)
    if args.focus_smoke or args.selection_focus_smoke:
        marker="    (output / 'checks.json').write_text"
        extra="""    checks=checks[:2]
    checks.append(dict(checks[1],name='Read-only focus return',keys=['Applets','Home','Enter','Applets','Down','Enter'],resume=True,preserve_view=2,retained_from=2,cursor_mode=12))
"""
        if args.selection_focus_smoke:
            extra="""    checks=checks[:2]
    checks.append(dict(checks[1],name='Read-only native selection',keys=[['Left Shift','Right'],['Left Shift','Right']],rich_selection='th',cursor_mode=15))
    checks.append(dict(checks[2],name='Read-only selection after focus',keys=['Applets','Home','Enter','Applets','Down','Enter'],resume=True,preserve_view=3,retained_from=3,cursor_mode=12))
"""
        source=source.replace(marker,extra+marker)
    if args.long_profile:
        marker="    (output / 'checks.json').write_text"
        extra="""    initial=checks[0]
    base=dict(initial);base.pop('verse',None)
    base.update(chapter=sum(len(book['chapters']) for book in books[:18])+118,cursor_mode=12)
    checks=[initial,dict(base,name='Psalm 119 origin',keys=reference('Ps 119')),
        dict(base,name='Psalm page forward',keys=['Space'],page_number=1),
        dict(base,name='Psalm page back',keys=[['Left Shift','Space']],page_number=0),
        dict(base,name='Psalm focus return',keys=['Applets','Home','Enter','Applets','Down','Enter'],resume=True,preserve_view=4,retained_from=4)]
"""
        source=source.replace(marker,extra+marker)
    if args.relocation_profile:
        marker="    (output / 'checks.json').write_text"
        extra="""    checks=checks[:2]
    checks.append(dict(checks[1],name='Cached layout after AlphaWord allocation',keys=['Z','Applets','Home','Enter',['Left Ctrl','V'],dict(key='Applets',wait_paste=True),'Down','Enter'],resume=True,handoff_key_index=4,preserve_view=2,retained_from=2,cursor_mode=12))
"""
        source=source.replace(marker,extra+marker)
    if args.relocation_profile:
        harness=(script.parent/'BibleWiseHarness.lua').read_text()
        harness='local relocation_idle_pc\n'+harness
        dump_marker=" dump(string.format('editor-%02d.bin',index),editor,94)"
        assert dump_marker in harness
        harness=harness.replace(dump_marker," dump(string.format('file-relocation-%02d.bin',index),bench+64,8)\n"+dump_marker)
        marker=" if type(entry)=='table'and entry.key then"
        guard=""" if type(entry)=='table' and entry.wait_paste then
  local pc=cpu.state.PC.value
  if not relocation_idle_pc or pc<0x420000 or pc>=0x428000 or stable<3 then phase='key-wait';return end
 end
"""
        assert marker in harness
        harness=harness.replace(marker,guard+marker)
        marker=" mods={};for i=1,#entry-1 do"
        harness=harness.replace(marker," if entry[#entry]=='V' then relocation_idle_pc=cpu.state.PC.value end\n"+marker)

        marker="  assert(memory:read_u32(bench+12)==0,"
        trace="""  if frame%60==0 then
   local f=assert(io.open(capture_directory..'/relocation-live.json','w'))
   f:write(string.format('{"frame":%d,"check":%d,"stage":"%s","key":%d,"pc":%d,"reader_phase":%d,"error":%d}',frame,index,phase,key_index or 0,cpu.state.PC.value,memory:read_u32(bench+8),memory:read_u32(bench+12)));f:close()
  end
"""
        assert marker in harness
        harness=harness.replace(marker,trace+marker)
        needle="(HERE / 'BibleWiseHarness.lua').read_text()"
        assert needle in source
        source=source.replace(needle,repr(harness))
    if args.first_checks:
        marker="    (output / 'checks.json').write_text"
        assert marker in source
        source=source.replace(marker, f"    checks=checks[:{args.first_checks}]\n"+marker)
    source=source.replace("    subprocess.run(['make', '-s', '-C', str(ROOT/'betawise/os3k')], check=True)\n",'')
    # The generic renderer and source oracle remain the canonical production ones.
    sys.path.insert(0,str(script.parent))
    if args.variant in ('file','file-nocache'):
        from file_oracle import install
        install()
    sys.argv=[str(script),*remaining]
    exec(compile(source,str(script),'exec'),{'__name__':'__main__','__file__':str(script)})


if __name__=='__main__':main()
