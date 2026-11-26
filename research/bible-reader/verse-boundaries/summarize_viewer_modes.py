#!/usr/bin/env python3
"""Summarize EOF-gap timing, read-only font/layout and navigation experiments."""
import json
from pathlib import Path
import re
import struct
from summarize import scan_timings

HERE = Path(__file__).resolve().parent
BUILD = HERE / 'build'
KEYS = ['Right','Down','Left','Up','CmdDown','CmdUp','ShiftRight','ShiftRight',
    'ShiftLeft','Right','ShiftDown','ShiftDown','ShiftUp','Left','Home','End',
    'CmdLeft','CmdRight','ShiftHome','ShiftEnd','ShiftCmdDown','ShiftCmdUp']


def main():
    suites = []
    for name in ('eof-linear-bench','eof-binary-bench','eof-fast-linear-bench','eof-fast-binary-bench',
        'readonly-prewrapped-first-two','readonly-prewrapped-focus-v2','readonly-prewrapped-selection-focus'):
        directory = BUILD / name
        result = json.loads((directory / 'results.json').read_text())
        assert result['status'] == 'passed'
        checks = json.loads((directory / 'checks.json').read_text())
        gaps = []
        for index in range(1, len(checks)+1):
            editor = (directory / f'editor-{index:02}.bin').read_bytes()
            a, b = struct.unpack_from('>II', editor, 40)
            raw = (directory / f'chapter-{index:02}.bin').stat().st_size
            gaps.append(dict(start=a,end=b,raw_bytes=raw))
            if name.startswith('eof-'):
                assert b-a == 512 and b==raw
            else:
                assert a==b
        suites.append(dict(name=name,checkpoints=result['checkpoints'],status='passed',
            timings=scan_timings(directory),gaps=gaps))
    nav = json.loads((BUILD / 'readonly-probe/readonly-navigation.json').read_text())
    differences = []
    for index, (readonly, editable) in enumerate(zip(nav['readonly'],nav['editable'])):
        assert readonly[6]==0 and editable[6]==512
        assert readonly[7:]==editable[7:]==[0,1]
        if readonly[:6]!=editable[:6]:
            differences.append(dict(index=index,key=KEYS[index],readonly=readonly,editable=editable))
    assert [row['index'] for row in differences]==[14,15,18,19]
    log = (BUILD / 'readonly-probe/neo_3_21/mame.log').read_text()
    assert 'FAIL text' not in log
    count = int(re.search(r'PASS text probe (\d+) cases',log).group(1))
    sizes = []
    for name in ('eof-linear','eof-binary','eof-fast-linear','eof-fast-binary','readonly-prewrapped'):
        image = BUILD / name / 'app/build/NKJV/BibleWise-NKJV.OS3KApp'
        rom,a5 = struct.unpack_from('>II',image.read_bytes(),4)
        sizes.append(dict(variant=name,rom=rom,application_rom=rom-1419827,a5=a5))
    result = dict(status='passed',suites=suites,
        exact_ui_checkpoints=sum(suite['checkpoints'] for suite in suites),
        native_navigation=dict(keys=KEYS,records=nav,nonmatching=differences,
            scope='14 sequential actions and 8 independent shortcut trials from the same location. State/geometry/status assertions, not an LCD oracle for these 44 actions.'),
        syscall_probe_cases=count,release_sizes=sizes,
        fonts='Direct assignment of four documented Neo descriptor font pointers works with prewrapped text; 2/3/4-check suites verify exact custom-face pixels/cursor and focus/selection. No fixed ROM calls.',
        layout='Read-only init does not create wrap points. Bare field assignment fails exact LCD check (1343 differing initial pixels); a separate bare prototype fails a later verse lookup. Successful prototype first uses editable native layout, deletes gap, initializes true read-only, installs font pointers, and restores mapped descriptor state.',
        position='Existing retained editor/A5 preserves viewport/caret/selection. FileSeek stores viewport position without native TextEditorSavePosition. Focus roundtrip exact checks passed; no additional persistent record.',
        limitations='Font/format reflow, programmatic verse/search positioning and Home/End require further integration. Not production-ready. Deleting gap lowers file length by 512; immediate physical allocation reclaim/peak RAM was not measured.',
        production_changed=False)
    (BUILD / 'viewer-modes-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS',result['exact_ui_checkpoints'],'exact UI checkpoints;',count,'native probe cases; 44 navigation actions')


if __name__ == '__main__':
    main()
