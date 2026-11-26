#!/usr/bin/env python3
"""Measure local non-Adobe native caps and encoded Unicode small-cap coverage."""
import json
from pathlib import Path
import sys
import unicodedata
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'fonts'))
import fontgen
OUT=Path(__file__).with_name('build')/'smallcaps'


def record(path,family,style,pixels):
    small={u:unicodedata.name(chr(u),'') for u in list(range(0x3000))+list(range(0xa000,0xac00))
           if unicodedata.name(chr(u),'').startswith('LATIN LETTER SMALL CAPITAL ')}
    _,glyphs=fontgen.read_unicode_source(path,tuple(sorted(set(small)|{72})))
    if 72 not in glyphs or not glyphs[72]['points']:return None
    def h(points):return max(y for x,y in points)-min(y for x,y in points)+1
    western=tuple(ord(bytes([c]).decode('cp1252')) for c in list(range(32,127))+[i for i in range(128,256) if i not in (129,141,143,144,157)])
    _,full=fontgen.read_unicode_source(path,western)
    return dict(path=str(path),family=family,style=style,pixels=int(pixels),H_height=h(glyphs[72]['points']),
                missing_cp1252=[f'U+{c:04X}' for c in western if c not in full],
                unicode_smallcaps=[dict(code=f'U+{c:04X}',name=small[c],height=h(glyphs[c]['points']))
                                   for c in small if c in glyphs and glyphs[c]['points']])


def main():
    records=[]
    for directory in ('75dpi','100dpi','misc'):
        index=Path('/usr/share/fonts/X11')/directory/'fonts.dir'
        for line in index.read_text().splitlines()[1:]:
            filename,xlfd=line.split(' ',1);fields=xlfd.split('-')
            if len(fields)<15 or fields[13:]!=['iso10646','1']:continue
            # All Adobe strikes for actual small-cap encoding coverage, and
            # all small non-Adobe strikes for useful alternative cap heights.
            if fields[1]!='adobe' and int(fields[7])>14:continue
            item=record(index.parent/filename,' '.join(fields[1:3]),' '.join(fields[3:5]),fields[7])
            if item:records.append(item)
    bdfroot=ROOT.parent/'.research-work/u8g2-review/upstream/tools/font/bdf'
    if bdfroot.is_dir():
        for path in sorted(bdfroot.glob('t0-*-uni.bdf')):
            if int(path.name.split('-')[1].rstrip('b'))>14:continue
            records.append(record(path,'ttyp0','bold' if 'b-' in path.name else 'regular',path.name.split('-')[1].rstrip('b')))
        for filename in ('spleen-5x8.bdf','spleen-6x12.bdf'):
            path=bdfroot/filename
            if path.exists():records.append(record(path,'spleen','regular',filename.split('x')[1].split('.')[0]))
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'alternative-sources.json').write_text(json.dumps(dict(unicode_version=unicodedata.unidata_version,fonts=records),indent=2)+'\n')
    grouped={}
    for r in records:
        if r['family'].startswith('adobe '):continue
        key=(r['family'],r['H_height'])
        row=grouped.setdefault(key,dict(styles=set(),sizes=set(),smallcaps=set(),full=True))
        row['styles'].add(r['style']);row['sizes'].add(r['pixels']);row['smallcaps'].update(s['name'] for s in r['unicode_smallcaps']);row['full'] &= not r['missing_cp1252']
    for (family,height),r in sorted(grouped.items()):
        if height<=8:print(family,'H',height,'pixels',sorted(r['sizes']),'styles',sorted(r['styles']),'Unicode SC',len(r['smallcaps']),'full CP1252',r['full'])
    adobe=[r for r in records if r['family'].startswith('adobe ')]
    print('Adobe strikes checked',len(adobe),'with small-cap glyphs',sum(bool(r['unicode_smallcaps']) for r in adobe))


if __name__=='__main__':main()
