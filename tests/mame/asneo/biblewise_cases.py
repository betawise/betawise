"""Independent source-based fixtures for native BibleWise acceptance."""
import re


def keys(text):
    special = {"'": 'Quote', '\"': ['Left Shift', 'Quote'], ' ': 'Space', ':': ['Left Shift', 'Semicolon'],
        '*': ['Left Shift', '8'], '?': ['Left Shift', 'Slash']}
    return [special.get(character, character.upper()) for character in text]


def reference(text):
    return ['Find'] + keys(text) + ['Enter']


def reader_cases(books):
    def chapter(book, number):
        return sum(len(item['chapters']) for item in books[:book - 1]) + number - 1

    cases = []
    current_chapter, current_verse = 0, 1
    numbered = 1

    def add(name, actions=None, **expected):
        nonlocal current_chapter, current_verse, numbered
        current_chapter = expected.get('chapter', current_chapter)
        current_verse = expected.get('verse', current_verse)
        numbered = expected.get('numbered', numbered)
        case = dict(name=name, chapter=current_chapter, verse=current_verse, numbered=numbered)
        if actions is not None:
            case['keys'] = actions
        case.update(expected)
        cases.append(case)

    def form(text='', mode=0, options=False, cursor=None):
        return dict(text=text, search_mode=mode, options=options,
            cursor=len(text) if cursor is None else cursor)

    add('Initial Genesis')
    add('Resume typical Genesis chapter', ['Applets', 'Home', 'Enter', 'Applets', 'Down', 'Enter'], resume=True)
    add('Full-screen Find', ['Find'], mode=2, find_form=form())
    add('Reference in Find', keys('John 3:16'), mode=2, find_form=form('john 3:16'))
    john = chapter(43, 3)
    add('Find jumps to John 3:16', ['Enter'], chapter=john, verse=16,
        status=True, status_text='John 3:16')
    add('Location expires', [], wait_frames=95)
    add('Ctrl-G without a query opens Find', [['Left Ctrl', 'G']], mode=2, find_form=form())
    add('Cancel empty repeat Find', ['Escape'])
    add('Cmd-F opens Find', [['Command', 'F']], mode=2, find_form=form())
    add('Cancel Find', ['Escape'])
    corinthians = chapter(46, 13)
    add('Joined 1Cor abbreviation', reference('1Cor 13:4'), chapter=corinthians, verse=4)
    add('Resume selected short chapter', ['Applets', 'Home', 'Enter', 'Applets', 'Down', 'Enter'], resume=True)
    add('Short 1Co abbreviation', reference('1Co 13 5'), verse=5)
    add('Non-prefix Jdg abbreviation', reference('Jdg 1:1'), chapter=chapter(7, 1), verse=1)
    add('Ambiguous reference is rejected', reference('Ph 1'), mode=2,
        find_form=dict(text='ph 1', cursor=4, error=' Invalid or ambiguous reference'))
    add('Dismiss reference error', ['Escape'])
    add('Invalid named verse is rejected', reference('John 3:99'), mode=2,
        find_form=dict(text='john 3:99', cursor=9, error=' Invalid or ambiguous reference'))
    add('Dismiss invalid verse', ['Escape'])
    add('Input editing', ['Find'] + keys('God') + ['Left', 'Backspace', 'L'],
        mode=2, find_form=form('gol', cursor=3))
    add('Backspace clears query', ['End']+['Backspace']*3, mode=2, find_form=form())
    add('Type another query', keys('waters'), mode=2, find_form=form('waters'))
    add('Cancel edited Find', ['Escape'])
    add('Genesis reference', reference('Gen 1'), chapter=0, verse=1)
    add('Prefix reference without spaces', reference('John3:16'), chapter=john, verse=16)
    add('Hide verse numbers', ['V'], numbered=0)
    add('Show verse numbers', ['V'], numbered=1)
    add('Question mark opens Help', keys('?'), mode=3, help=True)
    add('Dismiss Help', ['Escape'])
    add('Next chapter with Option-Down', [['Left Alt', 'Down']], chapter=john + 1, verse=1,
        status=True, status_text='John 4')
    add('Previous chapter with Option-Up', [['Left Alt', 'Up']], chapter=john, verse=1,
        status=True, status_text='John 3')
    add('Chapter Home status', ['Home'], status=True, status_text='John 3')
    add('Up at beginning shows chapter hints', ['Up'], status=True, status_text='John 3')
    add('Chapter End status', ['End'], status=True, status_text='John 3', verse=36)
    add('Down at end shows chapter hints', ['Down'], status=True, status_text='John 3')
    add('Page backward status', [['Command', 'Up']], status=True, status_text='John 3', verse=None)
    add('Psalm 119 last verse', reference('Ps 119:176'), chapter=chapter(19, 119), verse=176)
    add('Reference for selection', reference('John 3:16'), chapter=john, verse=16)
    add('Move past verse number', ['Left','Right','Right','Right'])
    add('Select one native glyph', [['Left Shift', 'Right']], selection=True)
    add('Copy selected verse with citation', [['Left Ctrl', 'C']], status=True, status_text='Copied', message=True,
        clipboard=True, selection=True, clipboard_text='F ...\rJohn 3:16 (KJV)')
    add('Copied expires without input', [], wait_frames=75, selection=True)
    add('Cancel selection', ['Escape', 'Left'])
    add('System font picker', [['Left Ctrl', 'Left Alt', 'Command', 'F'], 'Home', 'Enter'], height=16)
    add('Genesis for word search', reference('Gen 1'), chapter=0, verse=1, height=16)
    add('Find waters', ['Find'] + keys('waters') + ['Enter'], verse=2, match='waters')
    for name, verse, occurrence, backwards in [
        ('Next waters', 6, 0, False), ('Next within same verse', 6, 1, False),
        ('Third occurrence', 6, 2, False), ('Previous occurrence', 6, 1, True),
    ]:
        command = ['Command', 'G']
        if backwards:
            command.insert(0, 'Left Shift')
        add(name, [command], verse=verse, match='waters', occurrence=occurrence)
    add('Empty search', ['Find'] + keys('zzzzunknown') + ['Enter'], selection=True, status=True, status_text='Not found', message=True)
    add('Dismiss empty search', ['Escape'], selection=True)
    add('Largest chapter for resume', reference('Ps 119:176'), chapter=chapter(19, 119), verse=176)
    add('Resume after AlphaWord', ['Applets', 'Home', 'Enter', 'Applets', 'Down', 'Enter'], resume=True)
    return cases


def search_cases(books):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'biblewise'))
    from oracle import oracle
    chapters = [chapter for book in books for chapter in book['chapters']]
    john = sum(len(book['chapters']) for book in books[:42]) + 2
    cases = [dict(name='Initial Genesis', chapter=0, verse=1, numbered=1)]
    current_mode = 0
    for mode, query in [(2, 'faith works'), (1, 'so loved'), (2, 'love* world'), (2, 'be* bel*')]:
        cases.append(dict(name='Reset ' + query, keys=reference('John 3:16'),
            chapter=john, verse=16, numbered=1))
        matches = oracle(chapters, query, mode, include_end=True)
        first = next(hit for hit in matches if hit[:3] >= (john, 16, 0))
        second = next(hit for hit in matches if hit[:3] > first[:3])
        previous = [hit for hit in matches if (hit[0],hit[3],hit[4]) < (second[0],second[3],second[4])][-1]
        actions = ['Find']
        encoded = '"'+query+'"' if mode == 1 else query
        cases.append(dict(name='Search ' + query, keys=actions + keys(encoded) + ['Enter'],
            chapter=first[0], verse=first[1], hit_ordinal=first[2], match='query', numbered=1, expected_end=[first[3],first[4]]))
        cases.append(dict(name='Next ' + query, keys=[['Command', 'G']],
            chapter=second[0], verse=second[1], hit_ordinal=second[2], match='query', numbered=1, expected_end=[second[3],second[4]]))
        cases.append(dict(name='Previous ' + query, keys=[['Command', 'Left Shift', 'G']],
            chapter=previous[0], verse=previous[1], hit_ordinal=previous[2], match='query', numbered=1,
            expected_end=[previous[3],previous[4]]))
        current_mode = mode
    cancel=dict(cases[-1], name='Cancel active phrase scan',
        keys=['Find'] + keys('"Jesus Jesus"') + ['Enter'], cancel_after_frames=30,
        mode=0, cursor_mode=12, selection=True)
    cancel['verse'] = cancel['expected_end'][0]
    cancel.pop('match',None)
    cancel.pop('hit_ordinal',None)
    cases.append(cancel)
    reopen=dict(cancel,name='Find retains cancelled query',keys=['Find'],mode=2,keep_query=True,
        find_form=dict(text='"jesus jesus"'))
    reopen.pop('cancel_after_frames')
    reopen.pop('cursor_mode')
    cases.append(reopen)
    reading=dict(cancel,name='Escape leaves retained query',keys=['Escape'],mode=0)
    reading.pop('cancel_after_frames')
    cases.append(reading)
    last_chapter=len(chapters)-1
    cases.append(dict(name='End of Bible for wrapped search',keys=reference('Rev 22:21'),
        chapter=last_chapter,verse=21,numbered=1))
    hit=oracle(chapters,'so loved',1)[0]
    cases.append(dict(name='Centered search-wrapped notice',keys=['Find']+keys('"so loved"')+['Enter'],
        chapter=last_chapter,verse=21,numbered=1,selection=True,search_notice=2,
        status=True,status_text='Search wrapped',message=True))
    cases.append(dict(name='Wrapped notice restores reading',keys=[],wait_frames=75,
        chapter=hit[0],verse=hit[1],numbered=1,hit_ordinal=hit[2],match='query'))
    return cases


def clear_previous_find_queries(checks):
    """Track retained Find input and clear only fixtures requesting a new entry.

    No guest RAM is modified. All editing uses ordinary native TextBox keys.
    """
    draft = ''
    accepted = ''
    modal = False
    shifted = {'Semicolon': ':', 'Quote': '"', '8': '*', 'Slash': '?'}
    for case in checks:
        actions = []
        for action in case.get('keys', []):
            event=action.get('key') if isinstance(action,dict) else action
            opens = event == 'Find' or (isinstance(event,list) and event[-1]=='F' and
                any(key in event for key in ('Command','Left Ctrl')) and 'Left Alt' not in event)
            actions.append(action)
            if opens and not modal:
                modal = True
                if not case.get('keep_query'):
                    actions.extend(['Backspace'] * len(draft))
                    draft = ''
                continue
            if not modal:
                continue
            if event == 'Enter':
                modal = case.get('mode') == 2
                if not modal:
                    if re.match(r'^(?:[1-3] ?)?[a-z]+ ?[0-9]', draft, re.I) or re.match(r'^\d+ \d+',draft):
                        verse_entry = bool(re.search(r':\s*[1-9]\d*$',draft) or re.search(r'\s\d+\s+[1-9]\d*$',draft))
                        draft = ''
                        if verse_entry:
                            case['verse_selection'] = True
                            case['selection'] = True
                        else:
                            case['no_selection'] = True
                    else:
                        accepted = draft
            elif event == 'Escape':
                modal = False
            elif event == 'Backspace':
                draft = draft[:-1]
            elif event == 'Quote':
                draft += "'"
            elif event == 'Space':
                draft += ' '
            elif isinstance(event,str) and len(event)==1:
                draft += event.lower()
            elif isinstance(event,list) and 'Left Shift' in event:
                draft += shifted.get(event[-1],'')
        if case.get('match'):
            case['query_text'] = accepted
        if 'keys' in case:
            case['keys'] = actions
        if case.get('find_form'):
            assert draft == case['find_form']['text'], (case['name'],draft,case['find_form'])
            modal = True


def annotate_match_selection(checks, books):
    """Derive complete selected spans independently from source word strings."""
    chapters = [chapter for book in books for chapter in book['chapters']]
    pattern = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
    for case in checks:
        if not case.get('match'):
            continue
        verse = case['verse']
        text = chapters[case['chapter']][verse - 1]
        words = list(pattern.finditer(text))
        if 'hit_ordinal' in case:
            first = case['hit_ordinal']
        else:
            first = [i for i, word in enumerate(words) if (word.group().replace("’", "'").lower().startswith(case['match']) if case['query_text'].endswith('*') else word.group().replace("’", "'").lower() == case['match'])][case.get('occurrence', 0)]
        query = case['query_text']
        terms = [(m.group().lower(), query[m.end():m.end()+1] == '*') for m in pattern.finditer(query)]
        if case.get('expected_end'):
            end_verse, last = case['expected_end']
        elif query.startswith('"'):
            end_verse, last = verse, first + len(terms) - 1
        else:
            reachable = {0}
            end_verse, last = verse, first
            for vi in range(verse, len(chapters[case['chapter']]) + 1):
                done = False
                for wi, word in enumerate(pattern.finditer(chapters[case['chapter']][vi-1])):
                    if vi == verse and wi < first:
                        continue
                    matches = [i for i,(term,prefix) in enumerate(terms) if (word.group().replace("’", "'").lower().startswith(term) if prefix else word.group().replace("’", "'").lower()==term)]
                    reachable |= {mask | (1 << i) for mask in list(reachable) for i in matches if not mask & (1 << i)}
                    if (1 << len(terms))-1 in reachable:
                        end_verse, last = vi, wi
                        done = True
                        break
                if done:
                    break
            assert done, case['name']
        case.update(selection=True, match_verse=verse, match_first=first,
            match_end_verse=end_verse, match_last=last, verse=end_verse)


def annotate_reader_formatting(checks, books):
    """Keep the legacy reader scenarios, using source-backed native formatting.

    References and match annotations determine selection text; no LCD or guest
    selection pixels are used to construct expected output.
    """
    chapters = [chapter for book in books for chapter in book['chapters']]
    pattern = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
    selected = None
    modal = False
    for case in checks:
        case['rich'] = True
        # Navigation exposes the caret; paging, lookup and notices hide it.
        visible_caret = case['name'] in (
            'Up at beginning shows chapter hints', 'Chapter End status',
            'Down at end shows chapter hints', 'Move past verse number',
            'Select one native glyph', 'Copied expires without input',
            'Cancel selection', 'System font picker')
        case['cursor_mode'] = 15 if visible_caret else 12
        actions = case.get('keys', [])
        if case.get('verse_selection'):
            selected = chapters[case['chapter']][case['verse'] - 1]
        elif case.get('match'):
            parts = []
            for verse in range(case['match_verse'], case['match_end_verse'] + 1):
                text = chapters[case['chapter']][verse - 1]
                words = list(pattern.finditer(text))
                first = words[case['match_first']].start() if verse == case['match_verse'] else 0
                last = words[case['match_last']].end() if verse == case['match_end_verse'] else len(text)
                parts.append(text[first:last])
            selected = ' '.join(parts)
        elif case['name'] == 'Select one native glyph':
            selected = 'F'
        elif case.get('no_selection') or case['name'] in (
                'Move past verse number', 'Cancel selection', 'System font picker') or any(
                key in ('Home', 'End') or isinstance(key, list) and 'Left Alt' in key
                for key in actions if not modal and not case.get('resume')):
            selected = None
        modal = case.get('mode') == 2
        if selected:
            case['rich_selection'] = selected
        if case['name'] == 'Empty search':
            case['search_notice'] = 1
        if case.get('message') and not case.get('clipboard'):
            case['notice_text'] = case['status_text']


def clipboard_relocation_cases(books):
    """Copy a large real selection, then navigate and reformat the moved file."""
    psalm = sum(len(book['chapters']) for book in books[:18]) + 118
    chapter = books[18]['chapters'][118]
    from bible_rich import source_expected
    selected = ' '.join(word for word, _ in source_expected('kjv', 'Psalm', 119)[0])
    base = dict(chapter=psalm, verse=176, numbered=1, rich=True, cursor_mode=12)
    cases = [
        dict(name='Initial Genesis', chapter=0, verse=1, numbered=1, rich=True, cursor_mode=12),
        dict(base, name='Open Psalm 119 for a large copy', keys=reference('Ps 119'), verse=1),
        dict(base, name='Select the full Psalm', keys=[['Left Shift', 'End']], rich_selection=selected),
        dict(base, name='Clipboard growth relocates chapter during copy', keys=[['Left Ctrl', 'C']],
             rich_selection=selected, clipboard=True, clipboard_relocation=True,
             clipboard_text=selected+'\rPsalm 119:1-176 (KJV)', status=True, message=True, status_text='Copied'),
        dict(base, name='Dismiss copied notice after relocation', keys=['Escape'], rich_selection=selected),
        dict(base, name='Hide numbers in relocated selection', keys=['V'], numbered=0, rich_selection=selected),
        dict(base, name='Restore numbers in relocated selection', keys=['V'], rich_selection=selected),
        dict(base, name='Hide italics in relocated selection', keys=['I'], italics=False, rich_selection=selected),
        dict(base, name='Restore italics in relocated selection', keys=['I'], rich_selection=selected),
        dict(base, name='Hide headings in relocated selection', keys=['H'], headings=False, rich_selection=selected),
        dict(base, name='Copy only visible text with headings hidden', keys=[['Left Ctrl', 'C']],
             headings=False, rich_selection=selected, clipboard=True, clipboard_reuse=True,
             clipboard_text=' '.join(chapter)+'\rPsalm 119:1-176 (KJV)',
             status=True, message=True, status_text='Copied'),
        dict(base, name='Restore headings after repeated relocation', keys=['H'], rich_selection=selected),
        dict(base, name='Seek within relocated chapter', keys=reference('Ps 119:2'), verse=2, rich_selection='verse'),
        dict(base, name='Copy a short verse after the large copy', keys=[['Left Ctrl', 'C']], verse=2,
             rich_selection='verse', clipboard=True, clipboard_text=chapter[1]+'\rPsalm 119:2 (KJV)',
             status=True, message=True, status_text='Copied'),
        dict(base, name='Reopen after clipboard allocation and deletion',
             keys=['Applets', 'Home', 'Enter', 'Applets', 'Down', 'Enter'], verse=2,
             rich_selection='verse', resume=True),
    ]
    song_chapter = sum(len(book['chapters']) for book in books[:21]) + 7
    song_verse = books[21]['chapters'][7][13]
    cases.extend([
        dict(base, name='Lookup longest book name', keys=reference('Song 8:14'),
             chapter=song_chapter, verse=14, rich_selection='verse'),
        dict(base, name='Copy full longest book name in citation', keys=[['Left Ctrl', 'C']],
             chapter=song_chapter, verse=14, rich_selection='verse', clipboard=True,
             clipboard_text=song_verse+'\rSong of Solomon 8:14 (KJV)',
             status=True, message=True, status_text='Copied'),
    ])
    return cases


def partial_clipboard_cases(books):
    """Odd/even-length partial selections must be safe on the 68000."""
    john = sum(len(book['chapters']) for book in books[:42]) + 2
    base = dict(chapter=john, verse=16, numbered=1, rich=True, cursor_mode=12)
    checks = [dict(name='Initial Genesis', chapter=0, verse=1, numbered=1, rich=True, cursor_mode=12),
        dict(base, name='Reference for one character', keys=reference('John 3:16'), rich_selection='verse'),
        dict(base, name='Move to first body character', keys=['Left', 'Right', 'Right', 'Right'], cursor_mode=15),
        dict(base, name='Select first character', keys=[['Left Shift', 'Right']], cursor_mode=15, rich_selection='F'),
        dict(base, name='Copy first character', keys=[['Left Ctrl', 'C']], rich_selection='F', clipboard=True,
            clipboard_text='F ...\rJohn 3:16 (KJV)', status=True, message=True, status_text='Copied'),
        dict(base, name='Dismiss first copy', keys=['Escape'], cursor_mode=15, rich_selection='F'),
        dict(base, name='Select two leading characters', keys=[['Left Shift', 'Right']], cursor_mode=15, rich_selection='Fo'),
        dict(base, name='Copy two leading characters', keys=[['Left Ctrl', 'C']], rich_selection='Fo', clipboard=True,
            clipboard_text='Fo ...\rJohn 3:16 (KJV)', status=True, message=True, status_text='Copied'),
        dict(base, name='Select one interior character', keys=reference('John 3:16') + ['Left', 'Right', 'Right', 'Right', 'Right', ['Left Shift', 'Right']], cursor_mode=15, rich_selection='r'),
        dict(base, name='Copy one interior character', keys=[['Left Ctrl', 'C']], rich_selection='r', clipboard=True,
            clipboard_text='... r ...\rJohn 3:16 (KJV)', status=True, message=True, status_text='Copied'),
        dict(base, name='Extend selection through following space', keys=['Escape', ['Left Shift', 'Right']], cursor_mode=15, rich_selection='r'),
        dict(base, name='Copy selection with trailing space', keys=[['Left Ctrl', 'C']], rich_selection='r', clipboard=True,
            clipboard_text='... r ...\rJohn 3:16 (KJV)', status=True, message=True, status_text='Copied')]

    return checks
