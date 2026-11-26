#!/usr/bin/env python3
"""Extend the original-ROM text probe with real read-only/no-gap assertions."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ORIGINAL = ROOT / 'research/syscalls/text'
PREPARED = HERE / 'build/readonly-probe-source'


def main():
    PREPARED.mkdir(parents=True, exist_ok=True)
    text = (ORIGINAL / 'typed-probe.c').read_text()
    marker = '    CHECK(3,TextEditorInit('
    start = text.index(marker)
    text = text[:start] + '''    CHECK(101,TextEditorInit(&editor,1,TEXT_EDITOR_READ_ONLY,1000,0,0,40,4)==0);
    CHECK(102,editor.read_only==1 && editor.gap_start==editor.gap_end);
    CHECK(103,FileQuerySize(1)==3);
#ifdef PROBE_NEO
    CHECK(104,TextEditorSetFonts(&editor,0,0,0,0,false)==TEXT_ERROR_READ_ONLY);
#endif
    OUT[1]=editor.gap_end-editor.gap_start;
    OUT[2]=FileQuerySize(1);
    OUT[3]=TextEditorHandleMessage(&editor,MSG_KEY,KEY_DOWN,0,&status);
    OUT[4]=status;
    CHECK(105,TextEditorSavePosition(&editor)==0 && FileQuerySize(1)==3);
''' + text[start:]
    text += (HERE / 'readonly_navigation.c').read_text()
    (PREPARED / 'typed-probe.c').write_text(text)
    lua = (ORIGINAL / 'probe.lua.in').read_text()
    marker = "add(10000+@typed_probe@,{},function()typed_setup('abc')end,function()eq(m:read_u32(data),0x70617373)end)"
    replacement = "add(10000+@typed_probe@,{},function()typed_setup('abc')end,function()eq(m:read_u32(data),0x70617373);print('READONLY gap='..m:read_u32(data+4)..' length='..m:read_u32(data+8)..' key_consumed='..m:read_u32(data+12)..' key_status='..m:read_u32(data+16))end)"
    assert marker in lua
    lua=lua.replace(marker,replacement)
    marker='local frame,index,phase,failed=0,0,-1,false'
    nav="""local navigation_rows={}
local function capture_navigation(name)
 eq(m:read_u32(data),0x70617373)
 local rows={};for row=0,21 do local values={};for col=0,8 do values[#values+1]=tostring(m:read_u32(data+4+(row*9+col)*4))end;rows[#rows+1]='['..table.concat(values,',')..']'end
 navigation_rows[name]='['..table.concat(rows,',')..']'
 local f=assert(io.open('readonly-navigation.json','w'));f:write('{"readonly":'..(navigation_rows.readonly or 'null')..',"editable":'..(navigation_rows.editable or 'null')..'}');f:close()
 print('PASS '..name..' navigation state capture')
end
add(10000+@typed_readonly_nav@,{},function()typed_setup('One\\rTwo\\rThree\\rFour\\rFive\\rSix\\rSeven\\rEight\\rNine')end,function()capture_navigation('readonly')end)
add(10000+@typed_editable_nav@,{},function()typed_setup('One\\rTwo\\rThree\\rFour\\rFive\\rSix\\rSeven\\rEight\\rNine')end,function()capture_navigation('editable')end)
"""
    lua=lua.replace(marker,nav+marker)
    lua=lua.replace('if phase==4 then', 'if phase==((cases[index][1]==10000+@typed_readonly_nav@ or cases[index][1]==10000+@typed_editable_nav@) and 160 or 4) then')
    (PREPARED / 'probe.lua.in').write_text(lua)
    runner = (ORIGINAL / 'run-probe.py').read_text()
    runner = runner.replace('here=Path(__file__).resolve().parent;repo=here.parents[2];workspace=repo.parent',
        'here=Path('+repr(str(PREPARED))+');repo=Path('+repr(str(ROOT))+');workspace=repo.parent')
    runner = runner.replace("'-u','typed_form_probe',", "'-u','typed_form_probe','-u','typed_readonly_nav','-u','typed_editable_nav',")
    runner = runner.replace("if r['name']=='neo_3_01':continue", "if r['name']!='neo_3_21':continue")
    runner = runner.replace("str(here.parent / 'coverage')", "str(repo / 'research/syscalls/coverage')")
    sys.argv = [str(ORIGINAL / 'run-probe.py'), str(HERE / 'build/readonly-probe')]
    exec(compile(runner, str(ORIGINAL / 'run-probe.py'), 'exec'), {'__name__':'__main__','__file__':str(ORIGINAL / 'run-probe.py')})


if __name__ == '__main__':
    main()
