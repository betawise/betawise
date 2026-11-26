#!/usr/bin/env python3
"""Exercise the production built-in system-font retained view on focus return."""
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
SCRIPT=HERE.parents[2]/'tests/mame/asneo/check-biblewise.py'


def main():
    source=SCRIPT.read_text()
    marker="    (output / 'checks.json').write_text"
    extra="""    initial=checks[0]
    system=dict(chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12,local_ui=True,
        font_vendor='system',expected_height=16,expected_reader_font=0)
    checks=[initial,
        dict(system,name='Choose shared System font',keys=['F','End','Left','Enter']),
        dict(system,name='System-font cached focus return',keys=['Applets','Home','Enter','Applets','Down','Enter'],resume=True,preserve_view=2,retained_from=2)]
"""
    assert marker in source
    source=source.replace(marker,extra+marker)
    sys.path.insert(0,str(SCRIPT.parent))
    sys.argv=[str(SCRIPT),'--version','NKJV','--case','family-picker','--output',str(HERE/'build/cached-prod-system-focus')]
    exec(compile(source,str(SCRIPT),'exec'),{'__name__':'__main__','__file__':str(SCRIPT)})


if __name__=='__main__':
    main()
