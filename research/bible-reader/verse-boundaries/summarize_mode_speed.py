#!/usr/bin/env python3
"""Compare validated editable/read-only native CPU work and release footprints."""
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
BUILD = HERE / 'build'
NAMES = ('profile-editable-v2','profile-readonly-v2','profile-editable-retained-v2',
    'profile-editable-pages','profile-readonly-pages','profile-editable-ps119',
    'profile-readonly-ps119','profile-editable-retained-ps119',
    'profile-editable-cached-pages','profile-editable-cached-ps119','profile-editable-cached-selection')
PHASES = {800:'native_key',802:'native_redraw',804:'native_position',806:'native_save',
    808:'readonly_conversion',814:'native_refresh',816:'save_workflow',820:'font_setup'}


def suite(name):
    directory = BUILD / name
    result = json.loads((directory/'results.json').read_text())
    assert result['status']=='passed'
    checks = json.loads((directory/'checks.json').read_text())
    events = json.loads((directory/'timings.json').read_text())
    rows = []
    for index, check in enumerate(checks,1):
        row = dict(name=check['name'])
        for phase,label in PHASES.items():
            stack=[]
            durations=[]
            for event in events:
                if event['check']!=index:
                    continue
                if event['phase']==phase:
                    stack.append(event['time'])
                elif event['phase']==phase+1:
                    assert stack, (name,index,phase)
                    durations.append(1000*(event['time']-stack.pop()))
            assert not stack, (name,index,phase)
            row[label]=dict(calls=len(durations),total_ms=sum(durations),individual_ms=durations)
        row['page_work_ms']=sum(row[key]['total_ms'] for key in ('native_key','native_position','native_redraw'))
        row['focus_return_work_ms']=sum(row[key]['total_ms'] for key in
            ('native_refresh','font_setup','native_position','native_redraw'))
        rows.append(row)
    return dict(name=name,status='passed',checkpoints=result['checkpoints'],rows=rows)


def main():
    suites=[suite(name) for name in NAMES]
    sizes=[]
    for variant in ('direct-binary','readonly-prewrapped','editable-retained','editable-cached'):
        image=BUILD/variant/'app/build/NKJV/BibleWise-NKJV.OS3KApp'
        rom,a5=struct.unpack_from('>II',image.read_bytes(),4)
        sizes.append(dict(variant=variant,rom=rom,application_rom=rom-1419827,a5=a5,
            rom_delta=rom-sizes[0]['rom'] if sizes else 0,
            a5_delta=a5-sizes[0]['a5'] if sizes else 0))
    report=dict(status='passed',suites=suites,release_sizes=sizes,
        exact_checkpoints=sum(item['checkpoints'] for item in suites),
        scope='Neo 3.21, NKJV, 16-pixel reading font. Actual native-operation CPU time from test-only memory taps; excludes keyboard scheduling and small uninstrumented glue. All reported suites pass canonical exact source/font/cursor/LCD checks.',
        timing='Phase pairs in profile_modes.py. save_workflow includes native_save; do not sum them. page_work and focus_return sum nonoverlapping calls. Readonly conversion is extra after the same editable layout, followed by an extra redraw.',
        conclusion='Most redraw/arrow/selection CPU work is unchanged. Large paging/focus gains come from reusing valid existing layout state and avoiding editable layout calls, not from read-only mode itself. Editable-cached obtains nearly the same timings while retaining editable native functionality.',
        limitations='Cached editable focus is tested only with retained chapter and unchanged reading-font metrics. A production path must detect changes and fall back to refresh/reflow. Read-only still lacks complete Home/End, arbitrary verse/search positioning and font/format reflow; its measured ROM overhead is not a complete equivalent replacement. No production changes.',
        memory='Readonly removes 512 stored gap bytes after setup, not the initial editable gap needed for wrapping. Physical allocation reclaim and peak RAM not characterized.')
    (BUILD/'mode-speed-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',report['exact_checkpoints'],'exact checkpoints')
    for item in sizes:
        print(item)


if __name__=='__main__':
    main()
