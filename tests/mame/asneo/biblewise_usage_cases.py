"""Source-derived everyday-use and boundary cases for the native Bible reader."""

import re

from biblewise_cases import keys


WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")


def reference(text):
    return ['Find', *keys(text), 'Enter']


def chapter_number(books, book, chapter=1):
    return sum(len(item['chapters']) for item in books[:book]) + chapter - 1


def reading_case(name, actions=None, **expected):
    case = dict(name=name, chapter=0, numbered=1, rich=True, cursor_mode=12)
    if actions is not None:
        case['keys'] = actions
    case.update(expected)
    case['numbered'] = int(case['numbered'])
    return case


def boundary_cases(books):
    """Cross every book seam in both directions, including all singletons."""
    cases = [reading_case('Initial Genesis', verse=1)]
    for name, action in [
        ('Comma at Genesis beginning', ['Comma']),
        ('Left bracket at Genesis beginning', ['Left bracket']),
        ('Option Up at Genesis beginning', [['Left Alt', 'Up']]),
        ('Option Left at Genesis beginning', [['Left Alt', 'Left']]),
    ]:
        cases.append(reading_case(name, action, verse=1, preserve_view=1,
                                  retained_from=1, sidebar_unchanged_from=1))

    for book, current in enumerate(books[:-1]):
        last = len(current['chapters'])
        before = chapter_number(books, book, last)
        after = chapter_number(books, book + 1)
        cases.extend([
            reading_case(f"Last chapter of {current['name']}",
                         reference(f"{current['name']} {last}"), chapter=before, verse=1),
            reading_case(f"Forward {current['name']} to {books[book + 1]['name']}",
                         ['Period'], chapter=after, verse=1),
            reading_case(f"Back {books[book + 1]['name']} to {current['name']}",
                         ['Comma'], chapter=before, verse=1),
        ])

    jude = chapter_number(books, 64)
    revelation = chapter_number(books, 65)
    cases.extend([
        reading_case('Jude last verse', reference('Jude 1:25'), chapter=jude,
                     verse=25, rich_selection='verse'),
        reading_case('From Jude last verse into Revelation', [['Left Alt', 'Right']],
                     chapter=revelation, verse=1),
        reading_case('Back from Revelation into Jude', [['Left Alt', 'Left']],
                     chapter=jude, verse=1),
        reading_case('Back from Jude into 3 John', ['Comma'], chapter=jude - 1, verse=1),
        reading_case('Forward from 3 John into Jude', ['Period'], chapter=jude, verse=1),
        reading_case('Forward from Jude into Revelation again', ['Period'],
                     chapter=revelation, verse=1),
    ])

    final_chapter = chapter_number(books, 65, 22)
    cases.append(reading_case('Final Bible verse', reference('Rev 22:21'),
                              chapter=final_chapter, verse=21, rich_selection='verse'))
    last_view = len(cases)
    for name, action in [
        ('Period after Revelation 22', ['Period']),
        ('Right bracket after Revelation 22', ['Right bracket']),
        ('Option Down after Revelation 22', [['Left Alt', 'Down']]),
        ('Option Right after Revelation 22', [['Left Alt', 'Right']]),
    ]:
        cases.append(reading_case(name, action, chapter=final_chapter, verse=21,
                                  rich_selection='verse', preserve_view=last_view,
                                  retained_from=last_view, sidebar_unchanged_from=last_view))
    return cases


def usage_cases(books, version):
    cases = [reading_case('Initial Genesis', verse=1)]
    for text, book, chapter, verse in [
        ('Genesis 1:1', 0, 1, 1), ('Gen 50:26', 0, 50, 26),
        ('Ex 1:22', 1, 1, 22), ('Jdg 1:1', 6, 1, 1),
        ('Ps 117:2', 18, 117, 2), ('Ps 119:176', 18, 119, 176),
        ('Ps 119:1', 18, 119, 1), ('Ps 119', 18, 119, None),
        ('John3:16', 42, 3, 16), ('Jn 3:16', 42, 3, 16),
        ('1Cor 13:4', 45, 13, 4), ('1Co 13 5', 45, 13, 5),
        ('1 Cor 13:13', 45, 13, 13), ('1Cor 13', 45, 13, None),
        ('2Co 1:1', 46, 1, 1), ('Phlm 1:25', 56, 1, 25),
        ('1Jn 1:1', 61, 1, 1), ('2Jn 1:13', 62, 1, 13),
        ('3Jn 1:14', 63, 1, 14), ('Jude 1:1', 64, 1, 1),
        ('Jude 1:25', 64, 1, 25), ('Jude 1', 64, 1, None),
        ('Rev 22:21', 65, 22, 21), ('Gen 1', 0, 1, None),
    ]:
        expected = dict(chapter=chapter_number(books, book, chapter), verse=verse or 1)
        if verse is not None:
            expected['rich_selection'] = 'verse'
        cases.append(reading_case(f'Lookup {text}', reference(text), **expected))

    # Gray-code walk covers every combination while changing one option at a time.
    walk = [(1, 1, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1),
            (0, 0, 0), (0, 1, 0), (0, 1, 1), (1, 1, 1)]
    psalm = chapter_number(books, 18, 119)
    cases.append(reading_case('Selected Psalm 119 verse before all toggle combinations',
                              reference('Ps 119:119'), chapter=psalm, verse=119,
                              rich_selection='verse'))
    baseline = len(cases)
    state = (1, 1, 1)
    for target in walk:
        key = next(key for old, new, key in zip(state, target, 'VIH') if old != new)
        cases.append(reading_case(f'Selected Psalm options {target}', [key],
                                  chapter=psalm, verse=119, numbered=target[0],
                                  italics=bool(target[1]), headings=bool(target[2]),
                                  rich_selection='verse', retained_from=baseline))
        state = target

    cases.append(reading_case('Page after selected Psalm verse', ['Space'], chapter=psalm))
    baseline = len(cases)
    for target in walk:
        key = next(key for old, new, key in zip(state, target, 'VIH') if old != new)
        cases.append(reading_case(f'Paged Psalm options {target}', [key],
                                  chapter=psalm, numbered=target[0], italics=bool(target[1]),
                                  headings=bool(target[2]), retained_from=baseline))
        state = target
    cases.append(reading_case('Page backward after restoring all options',
                              [['Left Shift', 'Space']], chapter=psalm))

    # Exercise adjacent title/superscription records and small capitals together.
    psalm_three = chapter_number(books, 18, 3)
    cases.append(reading_case('Psalm 3 with adjacent headings', reference('Ps 3:2'),
                              chapter=psalm_three, verse=2, rich_selection='verse'))
    baseline = len(cases)
    for target in walk:
        key = next(key for old, new, key in zip(state, target, 'VIH') if old != new)
        cases.append(reading_case(f'Adjacent-heading options {target}', [key],
                                  chapter=psalm_three, verse=2, numbered=target[0],
                                  italics=bool(target[1]), headings=bool(target[2]),
                                  rich_selection='verse', retained_from=baseline))
        state = target

    cases.append(reading_case('Genesis before search', reference('Gen 1'), verse=1))
    for query in ['God', '"in the beginning"', 'Methus*', 'hypocrite']:
        cases.append(reading_case(f'Reset search origin before {query}', reference('Gen 1'), verse=1))
        word = query.strip('"').split()[0].rstrip('*').lower()
        prefix = query.endswith('*')
        for chapter, verses in enumerate(c for b in books for c in b['chapters']):
            hit = next(((verse, match.group()) for verse, text in enumerate(verses, 1)
                        for match in WORD.finditer(text)
                        if (match.group().lower().startswith(word) if prefix else match.group().lower() == word)), None)
            if hit:
                break
        assert hit is not None
        verse, selected = hit
        if query.startswith('"'):
            selected = 'In the beginning'
        cases.append(reading_case(f'Whole-Bible search {query}', ['Find', *keys(query), 'Enter'],
                                  chapter=chapter, verse=verse, rich_selection=selected))

    cases.extend([
        reading_case('Reset for dense next/previous search', reference('Gen 1'), verse=1),
        reading_case('God first occurrence', ['Find', *keys('God'), 'Enter'],
                     verse=1, rich_selection='God'),
        reading_case('Ctrl Find next God', [['Left Ctrl', 'Find']], verse=2, rich_selection='God'),
        reading_case('Cmd Shift Find previous God', [['Command', 'Left Shift', 'Find']],
                     verse=1, rich_selection='God'),
        reading_case('Find Enter repeats retained query', ['Find', 'Enter'], keep_query=True,
                     verse=2, rich_selection='God'),
        reading_case('Ctrl Shift G previous God', [['Left Ctrl', 'Left Shift', 'G']],
                     verse=1, rich_selection='God'),
        reading_case('Ctrl G next God', [['Left Ctrl', 'G']], verse=2, rich_selection='God'),
    ])

    matthew = chapter_number(books, 39, 7)
    query = 'beam eye' if version == 'KJV' else 'plank eye'
    text = books[39]['chapters'][6][2]
    words = list(WORD.finditer(text))
    terms = set(query.split())
    for first, word in enumerate(words):
        if word.group().replace("’", "'").lower() not in terms:
            continue
        for last in range(first, min(first + 20, len(words))):
            if terms <= {item.group().lower() for item in words[first:last + 1]}:
                selected = ' '.join(text[word.start():words[last].end()].split())
                break
        else:
            continue
        break
    cases.extend([
        reading_case('Reset for nearby search', reference('Matt 7'), chapter=matthew, verse=1),
        reading_case(f'Nearby {query}', ['Find', *keys(query), 'Enter'], chapter=matthew,
                     verse=3, rich_selection=selected),
    ])
    genesis_four = chapter_number(books, 0, 4)
    cases.extend([
        reading_case('Lookup verse with cached wrapping hyphen', reference('Gen 4:17'),
                     chapter=genesis_four, verse=17, rich_selection='verse'),
        reading_case('Copy retains cached wrapping hyphen', [['Left Ctrl', 'C']],
                     chapter=genesis_four, verse=17, rich_selection='verse', clipboard=True,
                     clipboard_text=books[0]['chapters'][3][16]+'\rGenesis 4:17 ('+version+')',
                     status=True, message=True),
    ])
    return cases


def feedback_cases(books):
    cases = [reading_case('Initial Genesis', verse=1)]
    invalid = [
        ('Gen 0:1', ' Invalid or ambiguous reference'),
        ('Ps 119:0', ' Invalid or ambiguous reference'),
        ('John 3:99', ' Invalid or ambiguous reference'),
        ('Rev 23', ' Invalid or ambiguous reference'),
        ('Ph 1', ' Invalid or ambiguous reference'),
        ('', ' Enter words or a verse reference'),
        ('"so loved', ' Close the phrase with a double quote'),
        ('"love* world"', ' Use * only outside quoted phrases'),
        ('love "world"', ' Put quotes around the whole phrase'),
        ('*love', ' Use 1-8 words; * only at word endings'),
    ]
    for text, error in invalid:
        cases.append(reading_case(f'Reject {text!r}', reference(text), verse=1, mode=2,
                                  find_form=dict(text=text.lower(), error=error)))
        cases.append(reading_case(f'Cancel {text!r}', ['Escape'], verse=1, preserve_view=1))

    cases.extend([
        reading_case('Draft nearby query', ['Find', *keys('love* world')], verse=1,
                     mode=2, find_form=dict(text='love* world')),
        reading_case('Cancel draft', ['Escape'], verse=1, preserve_view=1),
        reading_case('Reopen retained draft', ['Find'], verse=1, mode=2,
                     keep_query=True, find_form=dict(text='love* world')),
        reading_case('Cancel retained draft', ['Escape'], verse=1, preserve_view=1),
        reading_case('No-match notice', ['Find', *keys('zzzxqv'), 'Enter'], verse=1,
                     status=True, message=True, search_notice=1, notice_text='Not found'),
        reading_case('Dismiss no-match notice', ['Escape'], verse=1, preserve_view=1),
    ])
    last = chapter_number(books, 65, 22)
    cases.extend([
        reading_case('Final verse before forward wrap', reference('Rev 22:21'),
                     chapter=last, verse=21, rich_selection='verse'),
        reading_case('Forward search wraps without changing old chapter yet',
                     ['Find', *keys('God'), 'Enter'], chapter=last, verse=21,
                     rich_selection='verse', status=True, message=True,
                     search_notice=2, notice_text='Search wrapped'),
        reading_case('Dismiss forward wrap opens Genesis match', ['Escape'], verse=1,
                     rich_selection='God'),
        reading_case('Previous search wraps backward from Genesis',
                     [['Left Ctrl', 'Left Shift', 'Find']], verse=1, rich_selection='God',
                     status=True, message=True, search_notice=2, notice_text='Search wrapped'),
        reading_case('Dismiss backward wrap opens final matching verse', ['Escape'],
                     chapter=last, verse=19, rich_selection='God'),
    ])
    return cases


def mixed_cases(books, version):
    cases = [reading_case('Initial Genesis', verse=1)]
    state = dict(numbered=1, italics=True, headings=True)

    def add(name, actions, **expected):
        cases.append(reading_case(name, actions, **(state | expected)))

    for key, option in [('I', 'italics'), ('H', 'headings'), ('V', 'numbered')]:
        state[option] = False
        add(f'Disable {option} before cross-book navigation', [key], verse=1, retained_from=1)
    jude = chapter_number(books, 64)
    for name, actions, chapter, verse, selected in [
        ('3 John with all display options off', reference('3Jn 1'), jude - 1, 1, False),
        ('3 John into Jude with options off', ['Period'], jude, 1, False),
        ('Jude into Revelation with options off', ['Period'], jude + 1, 1, False),
        ('Revelation back into Jude with options off', ['Comma'], jude, 1, False),
        ('Jude back into 3 John with options off', ['Comma'], jude - 1, 1, False),
        ('Obadiah final verse with options off', reference('Obad 1:21'), chapter_number(books, 30), 21, True),
        ('Obadiah into Jonah with options off', ['Period'], chapter_number(books, 31), 1, False),
        ('Jonah back into Obadiah with options off', ['Comma'], chapter_number(books, 30), 1, False),
        ('Philemon final verse with options off', reference('Phlm 1:25'), chapter_number(books, 56), 25, True),
        ('Philemon into Hebrews with options off', ['Period'], chapter_number(books, 57), 1, False),
        ('Hebrews back into Philemon with options off', ['Comma'], chapter_number(books, 56), 1, False),
        ('Genesis with options off', reference('Gen 1'), 0, 1, False),
    ]:
        expected = dict(chapter=chapter, verse=verse)
        if selected:
            expected['rich_selection'] = 'verse'
        add(name, actions, **expected)
    baseline = len(cases)
    add('No backward chapter past Genesis with options off', ['Comma'], verse=1,
        preserve_view=baseline, retained_from=baseline, sidebar_unchanged_from=baseline)
    add('Search with all display options off', ['Find', *keys('God'), 'Enter'],
        verse=1, rich_selection='God')
    add('Next match with all display options off', [['Left Ctrl', 'Find']],
        verse=2, rich_selection='God')
    add('Previous match with all display options off', [['Left Ctrl', 'Left Shift', 'Find']],
        verse=1, rich_selection='God')
    add('Copy with headings, italics and verse numbers disabled', [['Left Ctrl', 'C']],
        verse=1, rich_selection='God', clipboard=True, status=True, message=True,
        clipboard_text='... God ...\rGenesis 1:1 ('+version+')')
    # Dismiss the copy notice and retain the native saved viewport on focus changes.
    add('Dismiss copied notice before focus change', ['Escape'], verse=1, rich_selection='God')
    baseline = len(cases)
    add('Resume local-font reader after AlphaWord',
        ['Applets', 'Home', 'Enter', 'Applets', 'Down', 'Enter'], verse=1,
        rich_selection='God', resume=True, preserve_view=baseline, retained_from=baseline)
    last = chapter_number(books, 65, 22)
    add('Final chapter with options off', reference('Rev 22'), chapter=last, verse=1)
    baseline = len(cases)
    add('No forward chapter past Revelation with options off', ['Period'],
        chapter=last, verse=1, preserve_view=baseline, retained_from=baseline,
        sidebar_unchanged_from=baseline)
    for key, option in [('V', 'numbered'), ('H', 'headings'), ('I', 'italics')]:
        state[option] = True
        add(f'Restore {option} in Revelation without decoding', [key], chapter=last,
            retained_from=baseline)
    return cases
