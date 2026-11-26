#!/usr/bin/env python3
"""Production cached paging regression, including a selection spanning pages."""
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SCRIPT=ROOT/'tests/mame/asneo/check-biblewise.py'


def main():
    source=SCRIPT.read_text()
    marker="    (output / 'checks.json').write_text"
    scenario="""    initial=checks[0]
    base=dict(initial);base.pop('verse',None)
    # Page from the current viewport, not a distant selection anchor.
    checks=[initial,
        dict(base,name='Page from long forward selection',keys=[['Left Shift','Command','Down']]*3+['Space'],cursor_mode=12),
        dict(base,name='Page back after long selection',keys=[['Left Shift','Space']],cursor_mode=12)]
"""
    assert marker in source
    source=source.replace(marker,scenario+marker)
    sys.path.insert(0,str(SCRIPT.parent))
    verify_only='--verify-only' in sys.argv
    sys.argv=[str(SCRIPT),'--version','NKJV','--case','viewport','--output',str(HERE/'build/cached-prod-long-selection-v4')]+(['--verify-only'] if verify_only else [])
    exec(compile(source,str(SCRIPT),'exec'),{'__name__':'__main__','__file__':str(SCRIPT)})
    import json
    import struct
    from bible_layout import captured_font
    from bible_rich import private_font, render_native, FONT_FILES
    output=HERE/'build/cached-prod-long-selection-v4'
    checks=json.loads((output/'checks.json').read_text())
    trace=json.loads((output/'timings.json').read_text())
    assertions=[]
    for index,direction in [(2,1),(3,-1)]:
        editor=(output/f'editor-{index:02}.bin').read_bytes()
        start,end=struct.unpack_from('>II',editor,40)
        raw=(output/f'chapter-{index:02}.bin').read_bytes()
        raw=raw[:start]+raw[end:]
        def logical(offset): return offset-(end-start) if offset>=end else min(offset,start)
        profiles=[captured_font(output,index,name) for name in ['font','boldfont','italicfont']]
        profiles.append(private_font(output,index,profiles,checks[index-1],checks[index-1].get('font_vendor') in FONT_FILES or checks[index-1].get('rich_font',False)))
        viewport=logical(struct.unpack_from('>I',editor,24)[0])
        _,lines,top,positions=render_native(raw,profiles,viewport)
        before=[event for event in trace if event['check']==index and event['phase']==824]
        assert len(before)==1
        old_top=positions[logical(before[0]['viewport'])][0]
        rows=6 if profiles[0]['height']==11 else 65//profiles[0]['height']
        expected=max(0,old_top+direction*rows)
        assert top==expected, ('page from original viewport',index,old_top,top,expected)
        assert positions[logical(struct.unpack_from('>I',editor,36)[0])]==(top,0)
        assertions.append(dict(check=index,before=old_top,after=top,expected=expected))
    (output/'paging-origin-results.json').write_text(json.dumps(assertions,indent=2)+'\n')
    print('PASS paging retains viewport when collapsing a distant selection')



if __name__=='__main__':
    main()
