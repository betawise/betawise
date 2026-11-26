#!/usr/bin/env python3
"""Production native BibleWise: disposable MAME state and exact local assertions."""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import struct
import subprocess
from pathlib import Path

from PIL import ImageChops
from bible_layout import captured_font, render, system_font, typeset
from biblewise_cases import annotate_match_selection, clear_previous_find_queries, keys, reader_cases, search_cases
from check import HERE, ROOT, prepare_session
from neo_reader import lcd_frames
from screen_bitmap import compare

APP = ROOT / 'betawise/applets/BibleWise'
spec = importlib.util.spec_from_file_location('repl_checks', HERE / 'check-repl.py')
repl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repl)
from bible_fonts import FONT_FILES, FONT_HEIGHTS, MENU_FONTS, font_image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', choices=['KJV', 'NKJV'], default='KJV')
    parser.add_argument('--case', choices=['reader', 'search', 'feedback', 'native', 'cancel', 'selection', 'fonts', 'controls', 'overlap', 'ui', 'notices', 'formatting', 'formatting-copy', 'formatting-page', 'heading-search', 'options', 'local-ui', 'viewport', 'toggle-page', 'toggle-long', 'boundaries', 'usage', 'usage-feedback', 'wrap-regression', 'mixed-usage', 'typography', 'default-font', 'family-picker', 'memory', 'memory-control', 'memory-rebuild', 'italic-rewrite', 'italic-interactions', 'italic-comparison'], default='formatting')
    parser.add_argument('--italics-prototype', choices=['alias','metadata','rom-index','offsets','marker','rebuild','integrated'], default='alias')
    parser.add_argument('--vendor-font', choices=list(FONT_HEIGHTS))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--format-smoke', action='store_true', help='Capture opening and small-cap sample pages')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    if args.verify_only:
        verify(output)
        return
    output.mkdir(parents=True, exist_ok=False)
    firmware = ROOT / 'Ghidra/Alphasmart Neo/SmartApplets'
    vendor_font = None
    if args.vendor_font in FONT_FILES:
        vendor_font = font_image(args.vendor_font)
    elif args.vendor_font in ('terminal','terminal_small'):
        base = 'BetaWiseTerminal-' + ('Small' if args.vendor_font == 'terminal_small' else 'Medium')
        vendor_font = ROOT / 'betawise/fonts/build' / base / (base + '.OS3KApp')
    elif args.vendor_font:
        vendor_font = (ROOT / 'betawise/fonts/build/BetaWiseTerminal-Tiny/BetaWiseTerminal-Tiny.OS3KApp' if args.vendor_font == 'tiny'
            else firmware / f'neofont{args.vendor_font}.os3kapp')
    font_id = int.from_bytes(vendor_font.read_bytes()[20:22], 'big') if vendor_font else None
    if args.case == 'default-font': font_id = None
    command = ['make', '-C', str(APP), f'VERSION={args.version}', 'TESTING=1', f'ITALICS_PROTOTYPE={args.italics_prototype}']
    if args.case == 'default-font' and args.vendor_font:
        command.append('TEST_SYSTEM_FONT_PICKER=1')
    if font_id:
        command.append(f'TEST_FONT_ID={font_id:#x}')
    with (output / 'build.log').open('w') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)

    stem = 'BibleWise' + ('' if args.version == 'KJV' else '-' + args.version)
    build = APP / 'build' / (args.version + '-test' + (f'-{font_id:#x}' if font_id else '') + ('-system-picker' if args.case=='default-font' and args.vendor_font else ''))
    if args.italics_prototype != 'alias': build = build.with_name(build.name+'-italics-'+args.italics_prototype)
    emulator = ROOT / 'mame/neodiag'
    prepare_session(output, firmware, 'extra', emulator)
    flash = bytearray((output / 'nvram/asneo/flashnv').read_bytes())
    flash[0x70000:] = b'\xff' * (len(flash) - 0x70000)
    offset = 0x70000
    images = [firmware / 'alphawordplus.os3kapp', build / (stem + '.OS3KApp')]
    if args.case in ('fonts','local-ui','family-picker'):
        images += sorted(firmware.glob('neofont*.os3kapp'))
        images += ([font_image(key) for key in FONT_FILES if '_' in key] + [ROOT/'betawise/fonts/build/BetaWiseTerminal-Medium/BetaWiseTerminal-Medium.OS3KApp'] if args.case=='family-picker' else [font_image(key)for key in MENU_FONTS])
    elif args.case == 'default-font' and not vendor_font:
        images += [font_image(key)for key in FONT_FILES if '_' in key]
    elif vendor_font:
        images.append(vendor_font)
    (output / 'artifacts').mkdir()
    for image in images:
        contents = image.read_bytes()
        assert offset + len(contents) <= len(flash)
        flash[offset:offset + len(contents)] = contents
        offset += len(contents)
        shutil.copyfile(image, output / 'artifacts' / image.name)
    (output / 'nvram/asneo/flashnv').write_bytes(flash)
    nm_output = subprocess.check_output(['m68k-linux-gnu-nm', '-n', str(build / (stem + '.elf'))], text=True)
    symbols = {fields[2]: int(fields[0], 16) for line in nm_output.splitlines()
        if len(fields := line.split()) == 3}
    (output / 'symbols.json').write_text(json.dumps(symbols, indent=2))
    data = APP / 'build/data' / args.version.lower()
    shutil.copyfile(data / 'source.json', output / 'source.json')
    books = json.loads((data / 'source.json').read_bytes())
    checks = reader_cases(books) if args.case != 'search' else search_cases(books)
    if args.case == 'cancel':
        query='"the the the the the the the"'
        checks=[dict(name='Initial page',chapter=0,verse=1,numbered=1,cursor_mode=12),
            dict(name='Escape returns to reading',keys=['Find']+keys(query)+['Enter'],
                chapter=0,verse=1,numbered=1,cancel_after_frames=420,cursor_mode=12),
            dict(name='Find opens empty after cancellation',keys=['Find'],chapter=0,verse=1,numbered=1,
                mode=2,keep_query=True,find_form=dict(text=query)),
            dict(name='Escape leaves Find',keys=['Escape'],chapter=0,verse=1,numbered=1,cursor_mode=12)]
    if args.case == 'fonts':
        from biblewise_cases import reference
        cor=sum(len(b['chapters'])for b in books[:45])+12
        ps=sum(len(b['chapters'])for b in books[:18])+118
        checks=[dict(name='Initial font page',chapter=0,verse=1,numbered=1,cursor_mode=12),
            dict(name='Six-row Corinthians',keys=reference('1 Cor 13:1'),chapter=cor,verse=1,numbered=1),
            dict(name='Largest chapter in font',keys=reference('Ps 119:176'),chapter=ps,verse=176,numbered=1),
            dict(name='Back to first Psalm verse',keys=['Home'],chapter=ps,verse=1,numbered=1),
            dict(name='Native page down',keys=[['Command','Down']],chapter=ps,verse=None,numbered=1,cursor_mode=12),
            dict(name='Native page up',keys=[['Command','Up']],chapter=ps,verse=None,numbered=1,cursor_mode=12),
            dict(name='Hide verse numbers',keys=['V'],chapter=ps,verse=None,numbered=0),
            dict(name='Restore verse numbers',keys=['V'],chapter=ps,verse=None,numbered=1),
            dict(name='Native Find in font',keys=['Find'],chapter=ps,verse=None,numbered=1,mode=2,
                find_form=dict(text='')),
            dict(name='Exit Find in font',keys=['Escape'],chapter=ps,verse=None,numbered=1,cursor_mode=12)]
    if args.case == 'selection':
        from biblewise_cases import reference
        john=sum(len(b['chapters'])for b in books[:42])+2
        verse=books[42]['chapters'][2][15]
        loved=verse.index('loved')
        remainder='... '+ ' '.join([verse[loved:]]+books[42]['chapters'][2][16:])+'\rJohn 3:16-36 (KJV)'
        checks=[dict(name='Initial page',chapter=0,verse=1,numbered=1),
            dict(name='Find text to select',keys=['Find']+keys('"so loved"')+['Enter'],chapter=john,verse=16,numbered=1),
            dict(name='Select loved',keys=['Right']*3+[['Left Shift','Right']]*5,chapter=john,verse=16,numbered=1,selection=True),
            dict(name='Copy excerpt with both ellipses',keys=[['Left Ctrl','C']],chapter=john,verse=16,numbered=1,
                selection=True,status=True,status_text='Copied',message=True,clipboard=True,
                clipboard_text='... loved ...\rJohn 3:16 (KJV)'),
            dict(name='Copy restores selection',keys=[],wait_frames=130,chapter=john,verse=16,numbered=1,selection=True),
            dict(name='Reset excerpt origin',keys=reference('John 3:16'),chapter=john,verse=16,numbered=1),
            dict(name='Whole verse fallback',keys=[['Left Ctrl','C']],chapter=john,verse=16,numbered=1,
                status=True,status_text='Copied',message=True,clipboard=True),
            dict(name='Find cross-verse excerpt',keys=['Find']+keys('loved')+['Enter'],chapter=john,verse=16,numbered=1),
            dict(name='Copy across verse boundaries',keys=[['Left Shift','End'],['Left Ctrl','C'],dict(key='Find',wait_status=True)]+keys('John 3:36')+['Enter'],
                chapter=john,verse=36,numbered=1,clipboard=True,clipboard_text=remainder)]
    if args.case == 'feedback':
        checks = [dict(name='Initial page', chapter=0, verse=1, numbered=1),
            dict(name='Copy current verse', keys=[['Left Ctrl', 'C']], chapter=0, verse=1,
                numbered=1, status=True, status_text='Copied', message=True, clipboard=True),
            dict(name='Copied expires', keys=[], wait_frames=130, chapter=0, verse=1, numbered=1),
            dict(name='Copy again', keys=[['Left Ctrl', 'C']], chapter=0, verse=1,
                numbered=1, status=True, status_text='Copied', message=True, clipboard=True),
            dict(name='Dismiss and navigate', keys=['Right'], chapter=0, verse=1, numbered=1)]
    if args.case == 'controls':
        checks = [dict(name='Initial page', chapter=0, verse=1, numbered=1)]
        def add(name, actions, verse=1, **extra):
            checks.append(dict(name=name, keys=actions, chapter=0, verse=verse, numbered=1, **extra))
        add('Jump reference', ['Find'] + keys('Gen 1:1') + ['Enter'])
        add('Verse entry cleared', ['Find'], mode=2, keep_query=True, find_form=dict(text=''))
        add('Search waters', keys('waters') + ['Enter'], verse=2, match='waters')
        add('Word query retained', ['Find'], verse=2, mode=2, keep_query=True, find_form=dict(text='waters'))
        add('Unchanged Enter finds next', ['Enter'], verse=6, match='waters', occurrence=0)
        add('Cmd Find advances', [['Command','Find']], verse=6, match='waters', occurrence=1)
        add('Ctrl Find advances', [['Left Ctrl','Find']], verse=6, match='waters', occurrence=2)
        add('Cmd Shift Find reverses', [['Command','Left Shift','Find']], verse=6, match='waters', occurrence=1)
        add('Ctrl Shift Find reverses', [['Left Ctrl','Left Shift','Find']], verse=6, match='waters', occurrence=0)
        add('Ctrl G advances', [['Left Ctrl','G']], verse=6, match='waters', occurrence=1)
        add('Ctrl Shift G reverses', [['Left Ctrl','Left Shift','G']], verse=6, match='waters', occurrence=0)
        add('Cmd G advances', [['Command','G']], verse=6, match='waters', occurrence=1)
        add('Cmd Shift G reverses', [['Command','Left Shift','G']], verse=6, match='waters', occurrence=0)
        add('Copy selected match', [['Left Ctrl','C']], verse=6, selection=True, status=True,
            message=True, status_text='Copied', clipboard=True, clipboard_text='... waters ...\rGenesis 1:6 (KJV)')
        add('Copied selection restored', [], verse=6, selection=True, wait_frames=130)
        add('Ctrl F retained query', [['Left Ctrl','F']], verse=6, mode=2, keep_query=True, find_form=dict(text='waters'))
        add('Edited query starts new search', ['Backspace']*6 + keys('light') + ['Enter'], verse=15, match='light')
    if args.case == 'overlap':
        checks=[dict(name='Initial page',chapter=0,verse=1,numbered=1)]
        for mode, query in [('Phrase','"holy holy"'),('Nearby','holy holy')]:
            checks.append(dict(name=mode+' reference',keys=['Find']+keys('Isa 6:3')+['Enter'],chapter=684,verse=3,numbered=1))
            checks.append(dict(name=mode+' first overlapping span',keys=['Find']+keys(query)+['Enter'],chapter=684,verse=3,numbered=1,hit_ordinal=7,match='query'))
            for name, action, ordinal in [('next overlapping', ['Command','Find'],8),
                    ('previous overlapping',['Left Ctrl','Left Shift','Find'],7),
                    ('forward again',['Left Ctrl','G'],8),
                    ('backward again',['Command','Left Shift','G'],7)]:
                checks.append(dict(name=mode+' '+name,keys=[action],chapter=684,verse=3,numbered=1,hit_ordinal=ordinal,match='query'))
        checks.append(dict(name='Unique reference',keys=['Find']+keys('Matt 5:22')+['Enter'],chapter=933,verse=22,numbered=1))
        checks.append(dict(name='Unique word selected',keys=['Find']+keys('raca')+['Enter'],chapter=933,verse=22,numbered=1,hit_ordinal=29,match='query'))
        for direction, action in [('next',['Command','Find']),('previous',['Left Ctrl','Left Shift','Find'])]:
            checks.append(dict(name='Unique '+direction+' excludes current after wrap',keys=[action],chapter=933,verse=22,numbered=1,selection=True,status=True,message=True,status_text='Not found'))
            checks.append(dict(name='Dismiss unique '+direction+' notice',keys=['Escape'],chapter=933,verse=22,numbered=1,selection=True))
        # The applet now always writes native formatting records. Validate these
        # cases with the rich source/pixel oracle instead of the retired plain
        # chapter layout, including exact overlapping selection endpoints.
        chapters = [chapter for book in books for chapter in book['chapters']]
        for check in checks:
            check.update(rich=True, cursor_mode=12)
            if check['name'].endswith('reference'):
                check['rich_selection'] = 'verse'
            elif check.get('match'):
                text = chapters[check['chapter']][check['verse'] - 1]
                words = list(re.finditer(r"[A-Za-z]+(?:['’][A-Za-z]+)*", text))
                first = check['hit_ordinal']
                last = first + (1 if check['chapter'] == 684 else 0)
                check['rich_selection'] = text[words[first].start():words[last].end()]
            elif check.get('selection'):
                check['rich_selection'] = 'Raca'
            if check.get('status_text') == 'Not found':
                check.update(notice_text='Not found', search_notice=1)
    if args.case == 'ui':
        john=sum(len(b['chapters'])for b in books[:42])+2
        esther=sum(len(b['chapters'])for b in books[:16])+7
        checks=[dict(name='Initial page',chapter=0,verse=1,numbered=1),
            dict(name='Short verse selected from start',keys=['Find']+keys('Gen 1:3')+['Enter'],chapter=0,verse=3,numbered=1,whole_verse_visible=True),
            dict(name='Copy complete lookup verse',keys=[['Left Ctrl','C']],chapter=0,verse=3,numbered=1,selection=True,status=True,message=True,status_text='Copied',clipboard=True),
            dict(name='Copied lookup selection restored',keys=[],wait_frames=130,chapter=0,verse=3,numbered=1,selection=True),
            dict(name='Jump to chapter end',keys=['End'],chapter=0,verse=31,numbered=1),
            dict(name='Lookup back from chapter end',keys=['Find']+keys('Gen 1:3')+['Enter'],chapter=0,verse=3,numbered=1,whole_verse_visible=True),
            dict(name='Multiline verse wholly visible',keys=['Find']+keys('John 3:16')+['Enter'],chapter=john,verse=16,numbered=1,whole_verse_visible=True),
            dict(name='Long lookup opens at beginning',keys=['Find']+keys('Esth 8:9')+['Enter'],chapter=esther,verse=9,numbered=1,long_verse=True),
            dict(name='Busy search cancelled to selected verse',keys=['Find']+keys('"the the the the the the the"')+['Enter'],chapter=esther,verse=9,numbered=1,selection=True,cancel_after_frames=420),
            dict(name='Lookup resets after busy cancellation',keys=['Find']+keys('John 3:16')+['Enter'],chapter=john,verse=16,numbered=1,whole_verse_visible=True)]
    if args.case == 'notices':
        import sys
        sys.path.insert(0,str(ROOT/'betawise/tests/biblewise'))
        from biblewise_cases import reference
        from oracle import oracle
        chapters=[chapter for book in books for chapter in book['chapters']]
        john=sum(len(b['chapters'])for b in books[:42])+2
        ps=sum(len(b['chapters'])for b in books[:18])+118
        last=len(chapters)-1
        hit=oracle(chapters,'so loved',1)[0]
        checks=[dict(name='Initial page',chapter=0,verse=1,numbered=1),
            dict(name='Lookup for search animation',keys=reference('John 3:16'),chapter=john,verse=16,numbered=1),
            dict(name='Searching label and lightening',keys=['Find']+keys('"the the the the the the the"')+['Enter'],chapter=john,verse=16,numbered=1,selection=True,cancel_after_frames=420),
            dict(name='Psalm last verse selected',keys=reference('Ps 119:176'),chapter=ps,verse=176,numbered=1),
            dict(name='Chapter-only reference has no selection',keys=reference('Ps 119'),chapter=ps,verse=1,numbered=1,top_line=0,no_selection=True),
            dict(name='Explicit verse zero is rejected',keys=reference('Ps 119:0'),chapter=ps,verse=1,numbered=1,mode=2,no_selection=True,find_form=dict(text='ps 119:0',error=' Invalid or ambiguous reference')),
            dict(name='Dismiss invalid verse zero',keys=['Escape'],chapter=ps,verse=1,numbered=1,no_selection=True),
            dict(name='Not found replaces Searching without redraw',keys=['Find']+keys('zzzzunknown')+['Enter'],chapter=ps,verse=1,numbered=1,no_selection=True,status=True,message=True,status_text='Not found',search_notice=1),
            dict(name='Not found expires to reading',keys=[],wait_frames=130,chapter=ps,verse=1,numbered=1,no_selection=True),
            dict(name='End of Bible for wrap',keys=reference('Rev 22:21'),chapter=last,verse=21,numbered=1),
            dict(name='Wrapped replaces Searching before navigation',keys=['Find']+keys('"so loved"')+['Enter'],chapter=last,verse=21,numbered=1,selection=True,status=True,message=True,status_text='Search wrapped',search_notice=2),
            dict(name='Wrapped notice expires into selected result',keys=[],wait_frames=130,chapter=hit[0],verse=hit[1],numbered=1,match='query',hit_ordinal=hit[2]),
            dict(name='Repeat end reference',keys=reference('Rev 22:21'),chapter=last,verse=21,numbered=1),
            dict(name='Wrapped notice before copy',keys=['Find']+keys('"so loved"')+['Enter'],chapter=last,verse=21,numbered=1,selection=True,status=True,message=True,status_text='Search wrapped',search_notice=2),
            dict(name='Copy commits deferred selected result',keys=[['Left Ctrl','C']],chapter=hit[0],verse=hit[1],numbered=1,selection=True,status=True,message=True,status_text='Copied',clipboard=True,clipboard_text='... so loved ...\rJohn 3:16 (KJV)')]
    if args.case == 'native':
        checks=[dict(name='Initial page',chapter=0,verse=1,numbered=1,cursor_mode=12)]
        def form(name,actions,text='',error=None):
            checks.append(dict(name=name,keys=actions,chapter=0,verse=1,numbered=1,mode=2,
                find_form=dict(text=text,error=error)))
        form('Native TextBox empty', ['Find'])
        form('Empty query stays editable', ['Enter'], error=' Enter words or a verse reference')
        form('Quoted wildcard validation',keys('"so loved*"')+['Enter'],'"so loved*"', ' Use * only outside quoted phrases')
        form('Native backspace', ['Backspace'], '"so loved*', ' Use * only outside quoted phrases')
        form('Native Left does not move insertion', ['Left','X'], '"so loved*x', ' Use * only outside quoted phrases')
        form('Remove appended character', ['Backspace'], '"so loved*', ' Use * only outside quoted phrases')
        checks.append(dict(name='Cancel native TextBox',keys=['Escape'],chapter=0,verse=1,numbered=1,cursor_mode=12))
        form('Reopen retains query',['Find'],'"so loved*')
        checks.append(dict(name='Return to reading',keys=['Escape'],chapter=0,verse=1,numbered=1,cursor_mode=12))
        checks.append(dict(name='Arrow exposes caret',keys=['Right'],chapter=0,verse=1,numbered=1,cursor_mode=15))
        checks.append(dict(name='Space pages without caret',keys=['Space'],chapter=0,verse=None,numbered=1,cursor_mode=12))
        checks.append(dict(name='Shift-Space pages without caret',keys=[['Left Shift','Space']],chapter=0,verse=None,numbered=1,cursor_mode=12))
        checks.append(dict(name='Neo page down hides caret',keys=[['Command','Down']],chapter=0,verse=None,numbered=1,cursor_mode=12))
        checks.append(dict(name='Neo page up hides caret',keys=[['Command','Up']],chapter=0,verse=None,numbered=1,cursor_mode=12))
        checks.append(dict(name='Down exposes caret',keys=['Down'],chapter=0,verse=None,numbered=1,cursor_mode=15))
        checks.append(dict(name='Native input before applet switch',keys=['Find'],chapter=0,verse=None,numbered=1,
            mode=2,find_form=dict(text='"so loved*')))
        checks.append(dict(name='Resume after leaving native input',keys=['Applets','Home','Enter','Applets','Down','Enter'],
            chapter=0,verse=None,numbered=1,resume=True,cursor_mode=12))
        checks.append(dict(name='Question mark opens Help',keys=[['Left Shift','Slash']],chapter=0,verse=None,numbered=1,mode=3,help=True))
        checks.append(dict(name='H opens same Help',keys=['Escape','H'],chapter=0,verse=None,numbered=1,mode=3,help=True))
        checks.append(dict(name='Leave Help',keys=['Escape'],chapter=0,verse=None,numbered=1,cursor_mode=12))
    if args.case in ('formatting', 'formatting-copy', 'formatting-page', 'heading-search', 'options', 'local-ui', 'viewport', 'toggle-page', 'toggle-long', 'boundaries', 'usage', 'usage-feedback', 'wrap-regression', 'mixed-usage', 'typography', 'family-picker', 'memory', 'memory-control', 'memory-rebuild', 'italic-rewrite', 'italic-interactions', 'italic-comparison'):
        def reference(text): return ['Find']+keys(text)+['Enter']
        ps=sum(len(b['chapters']) for b in books[:18])
        john=sum(len(b['chapters']) for b in books[:42])
        cor=sum(len(b['chapters']) for b in books[:45])
        checks=[dict(name='Genesis heading',chapter=0,verse=1,numbered=1),
            dict(name='Psalm 23 heading and small caps',keys=reference('Ps 23'),chapter=ps+22,verse=1,numbered=1),
            dict(name='Psalm 119 headings and poetry',keys=reference('Ps 119'),chapter=ps+118,verse=1,numbered=1),
            dict(name='John 3 headings and paragraphs',keys=reference('John 3'),chapter=john+2,verse=1,numbered=1),
            dict(name='1 Corinthians 13 italics',keys=reference('1 Cor 13'),chapter=cor+12,verse=1,numbered=1),
            dict(name='Hide verse numbers with formatting',keys=['V'],chapter=cor+12,verse=1,numbered=0),
            dict(name='Restore verse numbers',keys=['V'],chapter=cor+12,verse=1,numbered=1)]
        hypocrite=next((ci,vi)for ci,ch in enumerate(c for b in books for c in b['chapters'])
            for vi,text in enumerate(ch,1)if 'hypocrite' in re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)*",text.lower()))
        checks += [dict(name='Verse lookup selects formatted verse',keys=reference('John 3:16'),chapter=john+2,verse=16,numbered=1,rich_selection='verse'),
            dict(name='Copy selected verse without heading or controls',keys=[['Left Ctrl','C']],chapter=john+2,verse=16,numbered=1,rich_selection='verse',clipboard=True,clipboard_text=books[42]['chapters'][2][15]+'\rJohn 3:16 ('+args.version+')',status=True,message=True,status_text='Copied'),
            dict(name='Return to Genesis',keys=reference('Gen 1'),chapter=0,verse=1,numbered=1),
            dict(name='Find phrase through rich offsets',keys=['Find']+keys('"so loved"')+['Enter'],chapter=john+2,verse=16,numbered=1,rich_selection='so loved'),
            dict(name='Copy phrase through rich offsets',keys=[['Left Ctrl','C']],chapter=john+2,verse=16,numbered=1,rich_selection='so loved',clipboard=True,clipboard_text='... so loved ...\rJohn 3:16 ('+args.version+')',status=True,message=True,status_text='Copied'),
            dict(name='Return to Genesis before hypocrite',keys=reference('Gen 1'),chapter=0,verse=1,numbered=1),
            dict(name='Find hypocrite',keys=['Find']+keys('hypocrite')+['Enter'],chapter=hypocrite[0],verse=hypocrite[1],numbered=1,rich_selection='hypocrite')]
        if args.version=='NKJV':
            exodus=len(books[0]['chapters'])
            matt=sum(len(b['chapters'])for b in books[:39])
            checks += [dict(name='Centered inscription',keys=reference('Ex 28:36'),chapter=exodus+27,verse=36,numbered=1,rich_selection='verse'),
                dict(name='Right aligned Selah',keys=reference('Ps 3:2'),chapter=ps+2,verse=2,numbered=1,rich_selection='verse'),
                dict(name='Bold small capitals',keys=reference('Matt 3:3'),chapter=matt+2,verse=3,numbered=1,rich_selection='verse')]
        for check in checks: check['rich']=True;check['cursor_mode']=12
        if args.format_smoke: checks=checks[:2]
        if args.case=='formatting-page':
            checks=[checks[0],dict(name='Space advances a page past heading',keys=['Space'],chapter=0,numbered=1,rich=True,cursor_mode=12,page_number=1),
                dict(name='Command Down advances another page',keys=[['Command','Down']],chapter=0,numbered=1,rich=True,cursor_mode=12,page_number=2),
                dict(name='Command Up returns one page',keys=[['Command','Up']],chapter=0,numbered=1,rich=True,cursor_mode=12,page_number=1),
                dict(name='Shift Space returns to opening page',keys=[['Left Shift','Space']],chapter=0,numbered=1,rich=True,cursor_mode=12,page_number=0)]
        if args.case=='formatting-page':
            for check in checks[1:]:check['sidebar_unchanged_from']=1
        if args.case=='local-ui':
            checks=[checks[0],dict(name='Two-column Help',keys=[['Left Shift','Slash']],chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12,mode=3,help=True),
                dict(name='Escape restores reader',keys=['Escape'],chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12),
                dict(name='Period next chapter',keys=['Period'],chapter=1,verse=1,numbered=1,rich=True,cursor_mode=12),
                dict(name='Comma previous chapter',keys=['Comma'],chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12),
                dict(name='Greater-than chapter alias',keys=[['Left Shift','Period']],chapter=1,verse=1,numbered=1,rich=True,cursor_mode=12),
                dict(name='Less-than chapter alias',keys=[['Left Shift','Comma']],chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12),
                dict(name='Right bracket next chapter',keys=['Right bracket'],chapter=1,verse=1,numbered=1,rich=True,cursor_mode=12),
                dict(name='Left bracket previous chapter',keys=['Left bracket'],chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12),
                dict(name='F selects local Times font',keys=['F','End','Enter'],chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12,font_vendor='times',expected_height=11),
                dict(name='Resume chosen Times font after AlphaWord',keys=['Applets','Home','Enter','Applets','Down','Enter'],chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12,font_vendor='times',expected_height=11,resume=True),
                dict(name='System shortcut selects local Large font',keys=[['Left Ctrl','Left Alt','Command','F'],'Home','Down','Enter'],chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12,font_vendor='large',expected_height=16),
                dict(name='F returns to local System font',keys=['F','End','Enter'],chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12,font_vendor='system',expected_height=16)]
            for check in checks:check['rich']=True;check['cursor_mode']=12;check['local_ui']=True
        if args.case in ('boundaries', 'usage', 'usage-feedback', 'mixed-usage'):
            from biblewise_usage_cases import boundary_cases, feedback_cases, mixed_cases, usage_cases
            if args.case == 'boundaries':
                checks = boundary_cases(books)
            elif args.case == 'usage-feedback':
                checks = feedback_cases(books)
            elif args.case == 'mixed-usage':
                checks = mixed_cases(books, args.version)
            else:
                checks = usage_cases(books, args.version)
        if args.case=='wrap-regression':
            checks=[checks[0],
                dict(name='Leviticus small-cap line-wrap regression',keys=reference('Lev 1'),chapter=90,verse=1,numbered=1,rich=True,cursor_mode=12),
                dict(name='Leviticus small-cap verse selection',keys=reference('Lev 1:11'),chapter=90,verse=11,numbered=1,rich=True,cursor_mode=12,rich_selection='verse'),
                dict(name='Cached-hyphen verse',keys=reference('Gen 4:17'),chapter=3,verse=17,numbered=1,rich=True,cursor_mode=12,rich_selection='verse'),
                dict(name='Copy wrapping hyphen',keys=[['Left Ctrl','C']],chapter=3,verse=17,numbered=1,rich=True,cursor_mode=12,rich_selection='verse',clipboard=True,clipboard_text=books[0]['chapters'][3][16]+'\rGenesis 4:17 ('+args.version+')',status=True,message=True)]
        if args.case=='memory-control':
            ci = john + 2
            checks = [dict(name='Initial',chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12),
                dict(name='Selected verse before search',keys=reference('John 3:16'),chapter=ci,verse=16,numbered=1,rich=True,cursor_mode=12,rich_selection='verse'),
                dict(name='Cancel stack search',keys=['Find']+keys('"Jesus Jesus"')+['Enter'],chapter=ci,verse=16,numbered=1,rich=True,cursor_mode=12,rich_selection='verse',cancel_after_frames=30),
                dict(name='Retain cancelled query',keys=['Find'],keep_query=True,chapter=ci,verse=16,numbered=1,rich=True,cursor_mode=15,mode=2,find_form=dict(text='"jesus jesus"')),
                dict(name='Close cancelled query',keys=['Escape'],chapter=ci,verse=16,numbered=1,rich=True,cursor_mode=12,rich_selection='verse'),
                dict(name='Switch applets during stack search',keys=['Find','Enter','Applets','Escape'],keep_query=True,chapter=ci,verse=16,numbered=1,rich=True,cursor_mode=12,rich_selection='verse')]
        if args.case in ('memory','memory-rebuild'):
            ps = sum(len(b['chapters']) for b in books[:18]) + 118
            checks = [dict(name='Memory initial', chapter=0, verse=1, numbered=1, rich=True, cursor_mode=12)]
            def memory_case(name, actions, chapter=0, verse=1, **kwargs):
                checks.append(dict(name=name, keys=actions, chapter=chapter, verse=verse,
                    numbered=1, rich=True, cursor_mode=12, **kwargs))
            memory_case('God new', ['Find']+keys('God')+['Enter'], rich_selection='God')
            memory_case('God next', [['Left Ctrl','Find']], verse=2, rich_selection='God')
            memory_case('God previous', [['Left Ctrl','Left Shift','Find']], rich_selection='God')
            hit = next((ci, vi, word.group()) for ci, chapter in enumerate(c for b in books for c in b['chapters'])
                for vi, text in enumerate(chapter, 1) for word in re.finditer(r'[A-Za-z]+', text)
                if word.group().lower().startswith('methus'))
            memory_case('Rare prefix', ['Find']+keys('Methus*')+['Enter'], chapter=hit[0], verse=hit[1], rich_selection=hit[2])
            memory_case('Phrase origin', reference('Gen 1'))
            memory_case('Phrase new', ['Find']+keys('"so loved"')+['Enter'], chapter=john+2, verse=16, rich_selection='so loved')
            memory_case('Nearby origin', reference('Matt 7:1'), chapter=935, rich_selection='verse')
            query = 'beam eye' if args.version=='KJV' else 'plank eye'
            text = books[39]['chapters'][6][2]
            words = list(re.finditer(r'[A-Za-z]+', text))
            terms = set(query.split())
            first, last = next((i, j) for i in range(len(words)) for j in range(i, min(i+20, len(words)))
                if words[i].group().lower() in terms and terms <= {w.group().lower() for w in words[i:j+1]})
            start, end = words[first].start(), words[last].end()
            memory_case('Nearby new', ['Find']+keys(query)+['Enter'], chapter=935, verse=3, rich_selection=text[start:end])
            for label, ref, chapter, verse in [('Genesis', 'Gen 1:2',0,2),
                    ('Psalm start','Ps 119:1',ps,1),('Psalm late','Ps 119:119',ps,119),
                    ('Psalm end','Ps 119:176',ps,176)]:
                memory_case(label+' origin', reference(ref), chapter=chapter, verse=verse, rich_selection='verse')
                origin = len(checks)
                memory_case(label+' italics off', ['I'], chapter=chapter, verse=verse,
                    rich_selection='verse', italics=False, retained_from=origin, profile_offsets=True)
                memory_case(label+' italics on', ['I'], chapter=chapter, verse=verse,
                    rich_selection='verse', retained_from=origin, profile_offsets=True)
        if args.case == 'italic-comparison':
            checks=[dict(name='Initial',chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12)]
            samples=[('Gen 1',0,2),('Exod 33',82,9),('Ps 119',596,176),('Ps 3',480,8)]
            for ref,chapter,verse in samples:
                base=dict(chapter=chapter,verse=verse,numbered=1,rich=True,cursor_mode=12)
                checks.append(dict(base,name=ref+' selected',keys=reference(ref+':'+str(verse)),rich_selection='verse'))
                origin=len(checks)
                for enabled in (False,True):
                    checks.append(dict(base,name=ref+' selected '+('on'if enabled else'off'),keys=['I'],
                        rich_selection='verse',italics=enabled,preserve_view=origin,retained_from=origin))
                # Exercise a line-scrolled viewport with a normal visible caret.
                base.pop('verse')
                checks.append(dict(base,name=ref+' chapter',keys=reference(ref)))
                checks.append(dict(base,name=ref+' scrolled',keys=['Down']*8,cursor_mode=15))
                origin=len(checks)
                for enabled in (False,True):
                    checks.append(dict(base,name=ref+' scrolled '+('on'if enabled else'off'),keys=['I'],
                        cursor_mode=15,italics=enabled,preserve_view=origin,retained_from=origin,
                        allow_caret_reflow=ref=='Ps 3'))
        if args.case == 'italic-interactions':
            chapter=82 if args.version=='NKJV' else 0
            verse=9 if args.version=='NKJV' else 2
            ref='Exod 33:9' if args.version=='NKJV' else 'Gen 1:2'
            bindex=1 if args.version=='NKJV' else 0
            local=32 if args.version=='NKJV' else 0
            citation='Exodus 33:9' if args.version=='NKJV' else 'Genesis 1:2'
            base=dict(chapter=chapter,verse=verse,numbered=1,rich=True,cursor_mode=12,rich_selection='verse')
            checks=[dict(name='Initial',chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12),
                dict(base,name='Origin',keys=reference(ref)),
                dict(base,name='Italics off',keys=['I'],italics=False,retained_from=2),
                dict(base,name='Hide numbers',keys=['V'],italics=False,retained_from=2),
                dict(base,name='Hide headings',keys=['H'],italics=False,headings=False,retained_from=2),
                dict(base,name='Italics on hidden regions',keys=['I'],headings=False,retained_from=2),
                dict(base,name='Restore numbers',keys=['V'],headings=False,retained_from=2),
                dict(base,name='Restore headings',keys=['H'],retained_from=2),
                dict(base,name='Copy canonical text',keys=[['Left Ctrl','C']],clipboard=True,
                    clipboard_text=books[bindex]['chapters'][local][verse-1]+'\r'+citation+' ('+args.version+')',
                    message=True,status=True,status_text='Copied'),
                dict(base,name='Clear copied notice',keys=['Escape'])]
            for idx in (3,4,5): checks[idx]['numbered']=0
            partial=dict(chapter=john+2,verse=16,numbered=1,rich=True,cursor_mode=12,rich_selection='so loved')
            checks.append(dict(partial,name='Selected phrase',keys=['Find']+keys('"so loved"')+['Enter']))
            origin=len(checks)
            checks.append(dict(partial,name='Phrase italics off',keys=['I'],italics=False,preserve_view=origin,retained_from=origin))
            checks.append(dict(partial,name='Copy selected phrase with italics off',keys=[['Left Ctrl','C']],italics=False,
                clipboard=True,clipboard_text='... so loved ...\rJohn 3:16 ('+args.version+')',message=True,status=True,status_text='Copied'))
            checks.append(dict(partial,name='Phrase italics on',keys=['I'],preserve_view=origin,retained_from=origin))
        if args.case == 'italic-rewrite':
            checks = [dict(name='Initial', chapter=0, verse=1, numbered=1, rich=True, cursor_mode=12)]
            samples = [('Exod 33:9',82,9),('Num 23:15',139,15),('1 Sam 3:17',238,17),('1 Sam 16:7',251,7),('1 Kings 13:22',303,22),('2 Chron 3:1',369,1),('2 Chron 18:21',384,21)]
            if args.version == 'KJV': samples = [('Gen 1:2',0,2),('Ps 119:176',596,176)]
            for ref, chapter, verse in samples:
                base=dict(chapter=chapter,verse=verse,numbered=1,rich=True,cursor_mode=12,rich_selection='verse')
                checks.append(dict(base,name=ref+' origin',keys=reference(ref)))
                origin=len(checks)
                checks.append(dict(base,name=ref+' off',keys=['I'],italics=False,retained_from=origin))
                checks.append(dict(base,name=ref+' on',keys=['I'],retained_from=origin))
            # Load another affected chapter while italics are already disabled.
            ref, chapter, verse=samples[0]
            checks.append(dict(base,name='Disable before load',keys=['I'],italics=False))
            base=dict(chapter=chapter,verse=verse,numbered=1,rich=True,cursor_mode=12,rich_selection='verse')
            checks.append(dict(base,name='Load with italics off',keys=reference(ref),italics=False))
            checks.append(dict(base,name='Restore after load',keys=['I']))
            checks.append(dict(base,name='Copy source casing',keys=[['Left Ctrl','C']],copy=True))
        if args.case=='memory-rebuild':
            chosen = [0] + list(range(9, len(checks)))
            mapping = {old+1: new+1 for new, old in enumerate(chosen)}
            checks = [checks[index] for index in chosen]
            for check in checks:
                if 'retained_from' in check:
                    check['retained_from'] = mapping[check['retained_from']]
        if args.case=='family-picker':
            checks = [checks[0]]
            def picker(name, key, family, expected_id, target=5):
                checks.append(dict(name=name, keys=[key], chapter=0, numbered=1,
                    rich=True, mode=4, cursor_mode=12, family_picker=dict(
                        family=family,id=expected_id,target=target,font=9)))
            picker('Open branded picker','F',0,0xAFFA)
            picker('Mono keeps five lines','Down',1,0xAFFE)
            picker('Sans keeps five lines','Down',2,0xAFF6)
            picker('Serif keeps five lines','Down',3,0xAFF2)
            picker('BetaWise Terminal preserves preferred height','Down',4,0xA1F0)
            picker('Neo Font restores five lines','Down',5,0xAF75)
            picker('System four lines','Down',6,0)
            picker('System small seven lines','Right',6,0x10000,7)
            picker('Neo closest to seven','Up',5,0xAF00,7)
            picker('Terminal closest to seven','Up',4,0xA1F0,7)
            picker('Serif closest to seven','Up',3,0xAFF3,7)
            picker('Home selects branded Book','Home',0,0xAFFB,7)
            picker('Book five-line preference','Left',0,0xAFFA,5)
            picker('Book four-line preference','Left',0,0xAFF9,4)
            picker('Mono four-line preference','Down',1,0xAFFD,4)
            picker('Home preserves four-line preference','Home',0,0xAFF9,4)
            checks.append(dict(name='Use local Book Medium',keys=['Enter'],chapter=0,
                numbered=1,rich=True,cursor_mode=12,font_vendor='book_medium',expected_height=16))
            picker('Reopen current selection','F',0,0xAFF9,4)
            picker('System four at End','End',6,0,4)
            picker('System seven-line option','Right',6,0x10000,7)
            checks.append(dict(name='Use System small',keys=['Enter'],chapter=0,numbered=1,
                rich=True,cursor_mode=12,font_vendor='system_small',expected_height=9,expected_reader_font=0x10000))
            picker('Reopen System small','F',6,0x10000,7)
            picker('Browse System four','Left',6,0,4)
            checks.append(dict(name='Cancel keeps System small',keys=['Escape'],chapter=0,
                numbered=1,rich=True,cursor_mode=12,font_vendor='system_small',expected_height=9,expected_reader_font=0x10000))
            checks.append(dict(name='System small survives AlphaWord round trip',
                keys=['Applets','Home','Enter','Applets','Down','Enter'],chapter=0,verse=1,
                numbered=1,rich=True,cursor_mode=12,font_vendor='system_small',
                expected_height=9,expected_reader_font=0x10000,resume=True))
            current = 'book_small'
            for check in checks:
                if check['name']=='Use local Book Medium':current='book_medium'
                if check['name']=='Use System small':current='system_small'
                check.update(local_ui=True,font_vendor=current,expected_height=9 if current=='system_small' else FONT_HEIGHTS[current])
                if current=='system_small':check['expected_reader_font']=0x10000
        if args.case=='toggle-long':
            checks=[checks[0],
                dict(name='Three-digit verse in longest chapter',keys=reference('Ps 119:119'),chapter=ps+118,verse=119,numbered=1,rich=True,cursor_mode=12,rich_selection='verse'),
                dict(name='Hide three-digit numbers without decoding',keys=['V'],chapter=ps+118,verse=119,numbered=0,rich=True,cursor_mode=12,rich_selection='verse',retained_from=2),
                dict(name='Restore three-digit numbers without decoding',keys=['V'],chapter=ps+118,verse=119,numbered=1,rich=True,cursor_mode=12,rich_selection='verse',retained_from=2)]
        if args.case=='toggle-page':
            checks=[checks[0],
                dict(name='Genesis Space page',keys=['Space'],chapter=0,numbered=1,rich=True,cursor_mode=12,page_number=1),
                dict(name='I after Space',keys=['I'],chapter=0,numbered=1,rich=True,cursor_mode=12,italics=False,preserve_view=2,retained_from=2,no_intermediate_draw=True),
                dict(name='I restores after Space',keys=['I'],chapter=0,numbered=1,rich=True,cursor_mode=12,preserve_view=2,retained_from=2,no_intermediate_draw=True),
                dict(name='V hides digits in place',keys=['V'],chapter=0,numbered=0,rich=True,cursor_mode=12,retained_from=2),
                dict(name='V restores digits in place',keys=['V'],chapter=0,numbered=1,rich=True,cursor_mode=12,retained_from=2),
                dict(name='Select verse before V',keys=reference('Gen 1:2'),chapter=0,verse=2,numbered=1,rich=True,cursor_mode=12,rich_selection='verse'),
                dict(name='V retains verse selection while hiding numbers',keys=['V'],chapter=0,verse=2,numbered=0,rich=True,cursor_mode=12,rich_selection='verse',retained_from=7),
                dict(name='V restores numbers and verse selection',keys=['V'],chapter=0,verse=2,numbered=1,rich=True,cursor_mode=12,rich_selection='verse',retained_from=7)]
        if args.case=='viewport':
            checks=[checks[0],
                dict(name='Genesis after eight down arrows',keys=['Down']*8,chapter=0,numbered=1,rich=True,cursor_mode=15),
                dict(name='Disable italics without moving view',keys=['I'],chapter=0,numbered=1,rich=True,cursor_mode=15,italics=False,preserve_view=2,retained_from=2),
                dict(name='Restore italics without moving view',keys=['I'],chapter=0,numbered=1,rich=True,cursor_mode=15,preserve_view=2,retained_from=2),
                dict(name='Select verse before italics toggle',keys=reference('Gen 1:2'),chapter=0,verse=2,numbered=1,rich=True,cursor_mode=12,rich_selection='verse'),
                dict(name='Selection survives disabling italics',keys=['I'],chapter=0,verse=2,numbered=1,rich=True,cursor_mode=12,rich_selection='verse',italics=False,preserve_view=5,retained_from=5),
                dict(name='Selection survives restoring italics',keys=[['Left Ctrl','I']],chapter=0,verse=2,numbered=1,rich=True,cursor_mode=12,rich_selection='verse',preserve_view=5,retained_from=5),
                dict(name='Return to Genesis for heading visibility',keys=reference('Gen 1'),chapter=0,numbered=1,rich=True,cursor_mode=12),
                dict(name='Hide heading and its line break in place',keys=['H'],chapter=0,numbered=1,rich=True,cursor_mode=12,headings=False,retained_from=8,first_line_contains='In the beginning'),
                dict(name='Restore heading records in place',keys=[['Left Ctrl','H']],chapter=0,numbered=1,rich=True,cursor_mode=12,retained_from=8)]
        if args.case=='options':
            checks=[checks[0],dict(name='Italics chapter',keys=reference('1 Cor 13'),chapter=cor+12,verse=1,numbered=1,rich=True,cursor_mode=12),
                dict(name='I hides italics',keys=['I'],chapter=cor+12,verse=1,numbered=1,rich=True,cursor_mode=12,italics=False),
                dict(name='Ctrl I restores italics',keys=[['Left Ctrl','I']],chapter=cor+12,verse=1,numbered=1,rich=True,cursor_mode=12),
                dict(name='H hides headings',keys=['H'],chapter=cor+12,verse=1,numbered=1,rich=True,cursor_mode=12,headings=False),
                dict(name='Ctrl H restores headings',keys=[['Left Ctrl','H']],chapter=cor+12,verse=1,numbered=1,rich=True,cursor_mode=12),
                dict(name='Genesis before hiding heading',keys=reference('Gen 1'),chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12),
                dict(name='Search origin with hidden heading',keys=[['Left Ctrl','H']],chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12,headings=False),
                dict(name='Hide numbers as well as heading',keys=['V'],chapter=0,verse=1,numbered=0,rich=True,cursor_mode=12,headings=False),
                dict(name='Body search offsets include hidden heading',keys=['Find']+keys('"in the beginning"')+['Enter'],chapter=0,verse=1,numbered=0,rich=True,cursor_mode=12,headings=False,rich_selection='In the beginning'),
                dict(name='Restore numbers after search',keys=['V'],chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12,headings=False,rich_selection='In the beginning',retained_from=10),
                dict(name='Restore heading after search',keys=['H'],chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12,rich_selection='In the beginning',retained_from=10)]
        if args.case=='heading-search':
            checks=[checks[0],dict(name='Search heading word',keys=['Find']+keys('history')+['Enter'],chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12,rich_selection='History'),
                dict(name='Psalm 119 for heading search',keys=reference('Ps 119'),chapter=ps+118,verse=1,numbered=1,rich=True,cursor_mode=12),
                dict(name='Beth heading is searchable',keys=['Find']+keys('beth')+['Enter'],chapter=ps+118,verse=9,numbered=1,rich=True,cursor_mode=12,rich_selection='Beth'),
                dict(name='Reset for phrase',keys=reference('Ps 119'),chapter=ps+118,verse=1,numbered=1,rich=True,cursor_mode=12),
                dict(name='Phrase crosses heading into verse',keys=['Find']+keys('"beth how"')+['Enter'],chapter=ps+118,verse=9,numbered=1,rich=True,cursor_mode=12,rich_selection='Beth How'),
                dict(name='Reset for nearby',keys=reference('Ps 119'),chapter=ps+118,verse=1,numbered=1,rich=True,cursor_mode=12),
                dict(name='Nearby includes intervening heading',keys=['Find']+keys('utterly how')+['Enter'],chapter=ps+118,verse=9,numbered=1,rich=True,cursor_mode=12,rich_selection='utterly! Beth How')]
        if args.case=='typography':
            checks=[checks[0],
                dict(name='Genesis 3 LORD God separator',keys=reference('Gen 3'),chapter=2,verse=1,numbered=1,rich=True,cursor_mode=12,private_letters_only=True),
                dict(name='Select quoted verse',keys=reference('Gen 3:1'),chapter=2,verse=1,numbered=1,rich=True,cursor_mode=12,rich_selection='verse',private_letters_only=True),
                dict(name='Copy quoted verse with native punctuation',keys=[['Left Ctrl','C']],chapter=2,verse=1,numbered=1,rich=True,cursor_mode=12,rich_selection='verse',clipboard=True,clipboard_text=books[0]['chapters'][2][0]+'\rGenesis 3:1 ('+args.version+')',status=True,message=True,status_text='Copied'),
                dict(name='Genesis 9 for apostrophe search',keys=reference('Gen 9'),chapter=8,verse=1,numbered=1,rich=True,cursor_mode=12),
                dict(name='Straight apostrophe finds curly apostrophe',keys=['Find']+keys('"man\'s"')+['Enter'],chapter=8,verse=5,numbered=1,rich=True,cursor_mode=12,rich_selection='man’s' if args.version=='NKJV' else "man's")]
        if args.case=='formatting-copy':
            ps=sum(len(b['chapters'])for b in books[:18])
            verse=books[18]['chapters'][2][1]
            checks=[checks[0],dict(name='Select poetry and Selah',keys=reference('Ps 3:2'),chapter=ps+2,verse=2,numbered=1,rich=True,rich_selection='verse',cursor_mode=12),
                dict(name='Copy poetry as canonical plain text',keys=[['Left Ctrl','C']],chapter=ps+2,verse=2,numbered=1,rich=True,rich_selection='verse',cursor_mode=12,clipboard=True,clipboard_text=verse+'\rPsalm 3:2 ('+args.version+')',status=True,message=True,status_text='Copied')]
    if args.case == 'local-ui' and not args.vendor_font:
        for check in checks:
            if 'font_vendor' not in check:
                check.update(font_vendor='schoolbook',expected_height=11)
    if args.case == 'default-font':
        chosen='system' if args.vendor_font else 'book_small'
        checks=[dict(name='First-run reading font',chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12,local_ui=True,font_vendor=chosen,expected_height=16 if chosen=='system' else FONT_HEIGHTS[chosen]),
            dict(name='Explicit System overrides automatic font',keys=['F','End','Enter'],chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12,local_ui=True,font_vendor='system',expected_height=16),
            dict(name='Explicit System survives focus changes',keys=['Applets','Home','Enter','Applets','Down','Enter'],chapter=0,verse=1,numbered=1,rich=True,cursor_mode=12,local_ui=True,font_vendor='system',expected_height=16,resume=True)]
    if args.case != 'native': clear_previous_find_queries(checks)
    annotate_match_selection(checks, books)
    for case in checks:
        if case.get('status') and not case.get('message'):
            case.pop('status')
            case.pop('status_text')
    height = FONT_HEIGHTS[args.vendor_font] if vendor_font else 16
    for case in checks:
        if case['name'] == 'System font picker':
            height = 16
        if 'expected_height' in case:height=case['expected_height']
        case['height'] = height
    if vendor_font and args.case != 'default-font':
        for check in checks: check['font_vendor'] = args.vendor_font
    for case in checks:
        if case.get('local_ui'):
            chosen = case.get('font_vendor', 'system')
            if chosen == 'system':
                case['expected_reader_font'] = 0
            elif chosen in FONT_FILES:
                case['expected_reader_font'] = int.from_bytes(font_image(chosen).read_bytes()[20:22], 'big')
            elif chosen in ('small', 'medium', 'large', 'vlarge', 'xlarge'):
                case['expected_reader_font'] = int.from_bytes((firmware/f'neofont{chosen}.os3kapp').read_bytes()[20:22], 'big')
    for case in checks: case['italics_prototype'] = args.italics_prototype
    (output / 'checks.json').write_text(json.dumps(checks, indent=2))
    (output / 'source-version.json').write_text(json.dumps(dict(version=args.version, italics_prototype=args.italics_prototype)))
    configuration = dict(
        startup_system_font=args.case=='default-font' and bool(args.vendor_font),
        lcd_module=str(HERE / 'NeoLCD.lua'), capture_directory=str(output), checks=checks,
        reader_offset=symbols['g_reader'] - 0x80000000,
        saved_offset=symbols['g_saved'] - 0x80000000,
        editor_offset=symbols['g_editor'] - 0x80000000,
        settings_offset=symbols['g_settings'] - 0x80000000,
        status_offset=symbols['g_status_visible'] - 0x80000000,
        search_notice_offset=symbols['g_search_notice'] - 0x80000000,
        sidebar_font_address=0x44d592,
        input_offset=symbols['g_input'] - 0x80000000,
        chapter_offset=symbols['g_current_chapter'] - 0x80000000,
        busy_offset=symbols['g_busy_visible'] - 0x80000000,
        busy_dots_offset=symbols['g_busy_dots'] - 0x80000000,
        picker_offset=symbols.get('g_font_picker', 0x80000000) - 0x80000000,
    )
    script = ''.join(f'local {name}={repl.lua(value)}\n' for name, value in configuration.items())
    (output / 'run.lua').write_text(script + (HERE / 'BibleWiseHarness.lua').read_text())
    manifest_paths = images + [APP / name for name in ['BibleWise.c', 'Decoder.c', 'Search.c', 'Formatting.c', 'Makefile', 'convert_source.py']]
    manifest_paths += [HERE / name for name in ['BibleWiseHarness.lua', 'BibleWiseProbe.h', 'biblewise_cases.py', 'biblewise_usage_cases.py', 'bible_rich.py', 'bible_layout.py', 'check-biblewise.py', 'NeoLCD.lua', 'screen_bitmap.py', 'neo_reader.py']]
    manifest_paths += [ROOT/'betawise/research/bible-reader/offset-rebuild-probe.h']
    if args.italics_prototype!='alias':
        manifest_paths += [ROOT/'betawise/research/bible-reader/smallcaps-italics/rewrite.h', ROOT/'betawise/research/bible-reader/smallcaps-italics/build_ranges.py', data/'ItalicResearch.h', ROOT/'betawise/research/bible-reader/smallcaps-italics/rebuild-view.h']
    manifest_paths += [ROOT/'betawise/os3k/charsets/neo-smallcaps.h',ROOT/'betawise/os3k/charsets/neo-smallcaps.json',HERE/'bible_fonts.py']
    manifest_paths += [emulator, APP / 'upstream/data' / args.version.lower() / (args.version.lower()+'.json')]
    (output / 'manifest.json').write_text(json.dumps([
        dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in manifest_paths], indent=2))
    with (output / 'mame.log').open('w') as log:
        result = subprocess.run([str(emulator), 'asneo', '-rompath', str(output / 'roms'),
            '-nvram_directory', str(output / 'nvram'), '-cfg_directory', str(output / 'cfg'),
            '-video', 'none', '-sound', 'none', '-nothrottle', '-autoboot_delay', '0',
            '-autoboot_script', str(output / 'run.lua'), '-seconds_to_run', '1000'],
            stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ, SDL_VIDEODRIVER='dummy'), timeout=600)
    log_text = (output / 'mame.log').read_text()
    assert result.returncode == 0 and 'PASS BibleWise suite' in log_text and 'FAIL BibleWise' not in log_text, log_text[-2000:]
    verify(output)

def sidebar_reference(books, chapter, height, font):
    from PIL import Image
    names=[]
    labels=('Gen Ex Lev Num Deut Josh Judg Ruth|1 Sam|2 Sam|1 Kgs|2 Kgs|1 Chr|2 Chr|Ezra Neh Esth Job Ps Prov Eccl Song Isa Jer Lam Ezek Dan Hos Joel Amos Obad Jonah Mic Nah Hab Zeph Hag Zech Mal Matt Mark Luke John Acts Rom|1 Cor|2 Cor|Gal Eph Phil Col|1 Thess|2 Thess|1 Tim|2 Tim|Titus Phlm Heb Jas|1 Pet|2 Pet|1 John|2 John|3 John|Jude Rev')
    for group in labels.split('|'):
        names.extend([group]if group[0].isdigit()else group.split())
    assert len(names)==66
    first=0
    for bi,book in enumerate(books):
        if chapter<first+len(book['chapters']):break
        first+=len(book['chapters'])
    label=names[bi]+' '+str(chapter-first+1)
    side_height=65
    image=Image.new('1',(11,65),1)
    image.paste(0,(0,side_height,11,65))
    y=(side_height-sum(font['widths'][ord(c)]for c in label))//2
    assert y>=0
    for c in label:
        width=font['widths'][ord(c)];glyph=font['glyphs'][ord(c)]
        for dx in range(width):
            for dy in range(9):
                if glyph[dy//8*width+dx]>>(dy%8)&1:image.putpixel((9-dy,y+dx),0)
        y+=width
    return image

def verify(out):
    if json.loads((out/'checks.json').read_text())[0].get('rich'):
        from bible_rich import verify_rich
        return verify_rich(out, sidebar_reference)
    checks = json.loads((out / 'checks.json').read_text())
    books = json.loads((out / 'source.json').read_bytes())
    chapters = [c for b in books for c in b['chapters']]
    from PIL import Image
    busy_reports = []
    for capture in sorted(out.glob('busy-*.lcd.json')):
        meta_file = out / ('busy-meta-'+capture.name.split('-')[1].split('.')[0]+'.json')
        meta = json.loads((meta_file if meta_file.exists() else out/'busy-meta.json').read_text())
        expected_bar = Image.new('1', (11, 65), 1)
        body_height=checks[meta['index']-1]['height']
        side_height=65
        expected_bar.paste(0,(0,side_height,11,65))
        phase=meta['dots']
        center=phase-1 if phase<=5 else 9-phase
        for dot in range(5):
            distance=abs(dot-center)
            radius=1 if distance<=1 else 0
            cy=8+dot*12
            for dy in range(-radius,radius+1):
                for dx in range(-radius,radius+1):
                    if distance==1 and abs(dx)+abs(dy)>1:continue
                    expected_bar.putpixel((5+dx,cy+dy),0)
        notice = Image.new('1',(112,20),1)
        label='Searching'
        glyphs=system_font()
        for i,character in enumerate(label):
            for dy in range(16):
                for dx in range(6):
                    if glyphs[ord(character)*12+dy//8*6+dx]>>(dy%8)&1:
                        notice.putpixel(((112-len(label)*6)//2+i*6+dx,2+dy),0)
        notice_reference=out/'searching-reference.png'
        ImageChops.invert(notice.convert('L')).save(notice_reference)
        compare([capture],notice_reference,out/f"searching-comparison-{phase}",region=(70,22,112,20),screen_size=(264,65))
        for sample in lcd_frames(capture,height=65):
            assert all(not sample[y*264+x] for y in range(65) for x in range(252)
                if (x+y)%2==0 and not (70<=x<182 and 22<=y<42)), 'search lightening mask'
        reference = out / f"busy-reference-{meta['dots']}.png"
        ImageChops.invert(expected_bar.convert('L')).save(reference)
        busy_reports.append(compare([capture], reference, out / f"busy-comparison-{meta['dots']}",
            region=(253, 0, 11, 65), screen_size=(264, 65)))
    timing_rows=json.loads((out/'timings.json').read_text())
    transitions=[]
    for index,row in enumerate(timing_rows):
        if row['phase']==50:
            assert index and timing_rows[index-1]['phase']==12, 'no repaint between search completion and notice'
            assert row['lcd_writes']==timing_rows[index-1]['lcd_writes'], 'no LCD writes before replacing Searching'
            end=timing_rows[index+1]
            assert end['phase']==51 and 0<end['lcd_writes']-row['lcd_writes']<2000, 'notice updates only its rectangle'
            transitions.append(dict(check=row['check'],lcd_writes=end['lcd_writes']-row['lcd_writes']))
    (out/'notice-transition-results.json').write_text(json.dumps(transitions,indent=2))
    (out / 'busy-results.json').write_text(json.dumps(busy_reports, indent=2))
    if (out/'loading.lcd.json').exists():
        meta=json.loads((out/'loading-meta.json').read_text())
        check=checks[meta['index']-1]
        assert meta['chapter']==check['chapter'], 'loading names its destination chapter'
        font=captured_font(out,meta['index'],'sidebarfont')
        image=sidebar_reference(books,check['chapter'],check['height'],font)
        reference=out/'loading-reference.png'
        ImageChops.invert(image.convert('L')).save(reference)
        report=compare([out/'loading.lcd.json'],reference,out/'loading-comparison',region=(253,0,11,65),screen_size=(264,65))
        for sample in lcd_frames(out/'loading.lcd.json',height=65):
            assert all(not sample[y*264+x]for y in range(65)for x in range(252)if (x+y)%2==0), 'loading checker mask'
        (out/'loading-results.json').write_text(json.dumps(report,indent=2))
    reports = []
    for i, c in enumerate(checks, 1):
        path = out / f'checkpoint-{i:02}.lcd.json'
        lcd_frames(path)
        e = (out / f'editor-{i:02}.bin').read_bytes()
        m = struct.unpack('>12I', (out / f'metrics-{i:02}.bin').read_bytes())
        cursor = json.loads((out / f'cursor-{i:02}.json').read_text())
        assert m[0] == 1112687698 and m[2] == 4 and (m[3] == 0) and (m[4] == c['chapter'])
        assert m[11] == c['numbered']
        assert 0 <= cursor['x'] < 264 and 0 <= cursor['y'] < 64
        if 'cursor_mode' in c: assert cursor['mode']==c['cursor_mode'], (c['name'],cursor)
        profile = captured_font(out, i)
        lines, positions, line_starts, verse_starts = typeset(chapters[c['chapter']], bool(c['numbered']), profile['widths'] if profile else None, screen_width=252)
        gap_start, gap_end = struct.unpack_from('>II', e, 40)

        def logical(offset):
            return offset - (gap_end - gap_start) if offset >= gap_end else min(offset, gap_start)
        base = 0
        viewport = base + logical(struct.unpack_from('>I', e, 24)[0])
        caret = base + logical(struct.unpack_from('>I', e, 36)[0])

        def position(offset):
            if offset in positions:
                return positions[offset]
            prior = max((p for p in positions if p <= offset))
            return positions[prior]
        top, x = position(viewport)
        row, cx = position(caret)
        if 'caret_line' in c:
            assert row == c['caret_line'], (c['name'], 'expected source caret row', row, c['caret_line'])
        if 'top_line' in c:
            assert top == c['top_line'], (c['name'], 'expected scroll extent', top, c['top_line'])
        assert x == 0, (c['name'], 'viewport not at line start', viewport, top, x)
        height = profile['height'] if profile else c.get('height', 8)
        if 'height' in c:
            assert height == c['height'], (c['name'], 'selected font height', height, c['height'])
        if c['name'] == 'System font picker':
            assert struct.unpack_from('>I', e, 78)[0] == 4501390 and (not profile['proportional']), 'system font actually selected'
        if i == 1 and c.get('font_vendor'):
            assert height == FONT_HEIGHTS[c['font_vendor']], ('vendor primary font', height)
        assert 0 <= row - top < (6 if height == 11 else 65 // height), (c['name'], 'caret not visible', row, top)
        full_dialog = c.get('mode') == 2 or (c.get('mode') == 3 and not c.get('clipboard'))
        assert (cursor['x'], cursor['y']) == ((54+6*len(c['find_form']['text']),0) if c.get('mode')==2 else (0,0) if full_dialog else (cx, (row - top) * height)), (c['name'], 'source cursor geometry', cursor, (cx, (row - top) * height))
        assert struct.unpack_from('>HH', e, 20) == ((66 if height == 11 else 65 // height * height),) * 2, (c['name'], 'whole-row viewport')
        expected = render(lines[top:top + (6 if height == 11 else 65 // height)], height, system_font() if height == 16 and profile is None else None, profile)
        selection_state = struct.unpack_from('>H', e, 54)[0]
        if c.get('no_selection'):
            assert selection_state==0, (c['name'],'chapter reference must not select text')
        if c.get('selection'):
            assert selection_state, (c['name'], 'expected native selection')
        if selection_state:
            anchor = base + logical(struct.unpack_from('>I', e, 56)[0])
            state = struct.unpack_from('>H', e, 54)[0]
            assert state != 0 and anchor != caret, (c['name'], 'native selection')
            ar, ax = position(anchor)
            cr, cx2 = position(caret)
            for line in range(max(top, min(ar,cr)), min(top + (6 if height == 11 else 65 // height), max(ar,cr)+1)):
                left = ax if line == ar else 0
                right = cx2 if line == cr else 252
                if ar > cr:
                    left = cx2 if line == cr else 0
                    right = ax if line == ar else 252
                box = (left, (line-top)*height, right, min(65,(line-top+1)*height))
                selected = expected.crop(box)
                expected.paste(ImageChops.invert(selected.convert('L')).convert('1'), box)
        def system_text(x, y, text):
            glyphs = system_font()
            for character in text:
                for dy in range(16):
                    for dx in range(6):
                        if x + dx < 264:
                            expected.putpixel((x + dx, y + dy),
                                (glyphs[ord(character) * 12 + dy // 8 * 6 + dx] >> (dy % 8)) & 1)
                x += 6

        def invert(box):
            expected.paste(ImageChops.invert(expected.crop(box).convert('L')).convert('1'), box)

        if 'find_form' in c:
            form = c['find_form']
            raw = (out / f'find-{i:02}.bin').read_bytes()
            assert raw.split(b'\0', 1)[0].decode('ascii') == form['text'], (c['name'],raw)
            expected.paste(0,(0,0,264,65))
            system_text(12,0,' Find:[                                ]')
            system_text(54,0,form['text'])
            system_text(12,16,'  exact: "so loved"      search: Enter')
            system_text(12,32,' nearby: love* world       exit: Esc')
            system_text(12,48,form.get('error') or '  verse: John 3:16    next: Cmd/Ctrl-Find')
            assert cursor['mode']==15
        if c.get('mode') == 3:
            expected.paste(0,(0,0,264,65))
            if c.get('help'):
                for row,label in enumerate(['  Find: words or John 3:16   V: numbers',
                    '  Cmd/Ctrl-Find: next   +Shift: previous',
                    '  Option-Up/Down: chapter  Ctrl-C: copy',
                    '  ?: help   H: headings   I: italics']):system_text(0,row*16,label)
            else:
                system_text(12,0,c.get('notice','Invalid or ambiguous reference'))
                system_text(0,32,'  Find: words or a verse reference')
                system_text(0,48,'  Press esc to return.')
        if c.get('status'):
            # Apply the independently specified checker mask to the pre-notice
            # source rendering, including any native selection inversion.
            for y in range(65):
                for x in range(252):
                    if (x+y)%2==0:expected.putpixel((x,y),0)
            label=c['status_text']
            width=len(label)*6
            x=(252-width)//2
            expected.paste(1,(70,22,182,42))
            system_text(x,24,label)
            invert((x,24,x+width,40))
            assert cursor['mode']==12
        if not full_dialog:
            sidebar_font=captured_font(out,i,'sidebarfont')
            assert sidebar_font['height']==9
            abbreviations = ('Gen Ex Lev Num Deut Josh Judg Ruth|1 Sam|2 Sam|1 Kgs|2 Kgs|1 Chr|2 Chr|Ezra Neh Esth Job Ps Prov Eccl Song Isa Jer Lam Ezek Dan Hos Joel Amos Obad Jonah Mic Nah Hab Zeph Hag Zech Mal Matt Mark Luke John Acts Rom|1 Cor|2 Cor|Gal Eph Phil Col|1 Thess|2 Thess|1 Tim|2 Tim|Titus Phlm Heb Jas|1 Pet|2 Pet|1 John|2 John|3 John|Jude Rev')
            names=[]
            for group in abbreviations.split('|'):
                names.extend([group] if group[0].isdigit() else group.split())
            assert len(names)==66
            ci=c['chapter'];first=0
            for bi,book in enumerate(books):
                if ci<first+len(book['chapters']):break
                first+=len(book['chapters'])
            label=names[bi]+' '+str(ci-first+1)
            expected.paste(0,(252,0,253,65))
            side_height=65
            expected.paste(1,(253,0,264,side_height))
            expected.paste(0,(253,side_height,264,65))
            start=(side_height-sum(sidebar_font['widths'][ord(ch)]for ch in label))//2
            for ch in label:
                width=sidebar_font['widths'][ord(ch)];glyph=sidebar_font['glyphs'][ord(ch)]
                for dx in range(width):
                    for dy in range(9):
                        if glyph[dy//8*width+dx]>>(dy%8)&1:
                            expected.putpixel((262-dy,start+dx),0)
                start+=width
            assert struct.unpack_from('>H',e,18)[0]==252, 'native text viewport width'
        notice_path=out/f'search-notice-{i:02}.json'
        if c.get('search_notice'):
            assert notice_path.exists(), (c['name'],'deferred search notice')
        if notice_path.exists():
            notice_meta=json.loads(notice_path.read_text())
            if c.get('search_notice'):
                assert notice_meta['notice']==c['search_notice']
            expected.paste(1,(253,0,264,65))
            phase=notice_meta['dots']
            center=phase-1 if phase<=5 else 9-phase
            for dot in range(5):
                distance=abs(dot-center)
                radius=1 if distance<=1 else 0
                for dy in range(-radius,radius+1):
                    for dx in range(-radius,radius+1):
                        if distance==1 and dx and dy:continue
                        expected.putpixel((258+dx,8+dot*12+dy),0)
        reference_file = out / f'expected-{i:02}.png'
        ImageChops.invert(expected.convert('L')).save(reference_file)
        comparison = compare([path], reference_file, out / f'comparison-{i:02}', screen_size=(264, 65))
        record = json.loads(path.read_text())
        for sample in record['samples']:
            for controller in sample['controllers']:
                for flag, value in dict(m_start_line=0, m_display_on=1, m_adc=0, m_com_reverse=0, m_reverse=0, m_all_points=0, m_reset=0).items():
                    assert controller[flag] == value, (c['name'], flag)
        if 'match' in c:
            start_words = list(re.finditer("[A-Za-z]+(?:['’][A-Za-z]+)*", chapters[c['chapter']][c['match_verse']-1]))
            end_words = list(re.finditer("[A-Za-z]+(?:['’][A-Za-z]+)*", chapters[c['chapter']][c['match_end_verse']-1]))
            def verse_text_start(v):
                return verse_starts[v-1] + (6+len(str(v)) if c['numbered'] else 0)
            raw_start = verse_text_start(c['match_verse']) + start_words[c['match_first']].start()
            raw_end = verse_text_start(c['match_end_verse']) + end_words[c['match_last']].end()
            anchor = base + logical(struct.unpack_from('>I',e,56)[0])
            assert (anchor,caret)==(raw_start,raw_end), (c['name'],'complete selected match',anchor,caret,raw_start,raw_end)
            assert cursor['mode']==12, (c['name'],'search result caret remains hidden')
        if c.get('verse_selection'):
            v=c['verse']
            anchor=base+logical(struct.unpack_from('>I',e,56)[0])
            verse_end=verse_starts[v] - 1 if v<len(verse_starts) else max(positions)
            assert caret==verse_starts[v-1] and anchor==verse_end, (c['name'],'reverse whole-verse selection',caret,anchor,verse_starts[v-1],verse_end)
            if c.get('whole_verse_visible'):
                last_row=position(anchor-1)[0]
                assert top<=row and last_row-top < (6 if height==11 else 65//height), (c['name'],'complete verse visible',top,row,last_row)
            if c.get('long_verse'):
                assert position(anchor-1)[0]-top >= (6 if height==11 else 65//height), (c['name'],'fixture must exceed one screen')
        if c.get('verse') is not None:
            assert caret >= verse_starts[c['verse'] - 1] and (c['verse'] == len(verse_starts) or caret < verse_starts[c['verse']]), (c['name'], 'source verse anchor')
        if c.get('resume'):
            calls, status, saved_position, saved_chapter, saved_numbers = struct.unpack('>5I', (out / f'saved-{i:02}.bin').read_bytes())
            assert calls >= 1 and status == 0 and (saved_chapter == c['chapter']) and (saved_numbers == c['numbered']), (c['name'], 'native saved state')
            assert saved_position == struct.unpack_from('>I', e, 24)[0], (c['name'], 'saved native viewport', saved_position, viewport)
            assert reports[-1]['logical_viewport'] == viewport and reports[-1]['logical_caret'] == caret, (c['name'], 'A5 caret and viewport retained')
        if c.get('clipboard'):
            b = next((b for b in reversed(range(66)) if sum((len(x['chapters']) for x in books[:b])) <= c['chapter']))
            local = c['chapter'] - sum((len(x['chapters']) for x in books[:b]))
            verse = c['verse']
            expected = chapters[c['chapter']][verse - 1] + '\r' + books[b]['name'] + f' {local + 1}:{verse} (' + (json.loads((out / 'source-version.json').read_text())['version'] if (out / 'source-version.json').exists() else 'KJV') + ')'
            expected=c.get('clipboard_text',expected)
            assert (out / f'clipboard-{i:02}.bin').read_bytes() == expected.encode('cp1252'), (c['name'],(out / f'clipboard-{i:02}.bin').read_bytes(),expected)
        reports.append(dict(logical_viewport=viewport, logical_caret=caret, name=c['name'], chapter=m[4], verse=m[5], cursor=cursor, viewport=struct.unpack_from('>I', e, 24)[0], caret=struct.unpack_from('>I', e, 36)[0], gap=struct.unpack_from('>II', e, 40), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bitmap=comparison, font_height=height, proportional=profile['proportional'] if profile else False))
    (out / 'results.json').write_text(json.dumps(dict(status='passed', results=reports), indent=2) + '\n')
    print(json.dumps(reports, indent=2))


if __name__ == '__main__':
    main()
