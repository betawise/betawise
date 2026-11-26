"""Source typography and layout, stored as controls in the text Huffman stream."""
from collections import Counter, defaultdict
from itertools import groupby
import hashlib
import json
import re
from convert_source import convert_text, read_corpus, STYLE_MARKER, encode_native, decode_native
from compress_text import TOKEN

STYLE = 'ibsr'
LAYOUT = 'plndcge'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def parse_atom(token):
    markers = re.findall('\\*([a-z]+)', token)
    assert len(markers) <= 1, token
    flags = markers[0] if markers else ''
    assert set(flags) <= set(STYLE + LAYOUT), token
    return (convert_text(STYLE_MARKER.sub('', token)), flags)


def read_formatting(version, repository):
    corpus, path = read_corpus(repository, version)
    chapters = [chapter for book in corpus for chapter in book['chapters']]
    keys = [(book['name'], chapter) for book in corpus for chapter in range(1, len(book['chapters']) + 1)]
    chapter_ids = {key: i for i, key in enumerate(keys)}
    atoms = [[] for _ in chapters]
    headings = [[] for _ in chapters]
    first_flags = []
    flags_count = Counter()
    header_levels = Counter()
    generated_titles = 0
    mapped_acrostic_headings = 0
    raw = path.read_bytes()
    body_parts = defaultdict(list)
    for row in json.loads(raw):
        _, book, chapter, verse = row['r'].split(':')
        ci = chapter_ids[book, int(chapter)]
        if 'h' in row:
            header_levels[str(row['h'])] += 1
            if row['h'] == 1 and row['t'] == f'{book} {chapter}':
                generated_titles += 1
            else:
                title = re.sub('[\\u0590-\\u05ff]+\\s*(?=[A-Za-z])', '', row['t'])
                mapped_acrostic_headings += title != row['t']
                headings[ci].append((len(atoms[ci]), int(row['h'] * 2), convert_text(title)))
            continue
        part = convert_text(STYLE_MARKER.sub('', row['t']))
        body_parts[ci, int(verse)].append(part)
        for index, token in enumerate(row['t'].split()):
            spelling, flags = parse_atom(token)
            flags_count.update(flags)
            style = sum((1 << STYLE.index(flag) for flag in flags if flag in STYLE))
            layout = sum((1 << LAYOUT.index(flag) for flag in flags if flag in LAYOUT))
            for j, atom in enumerate(spelling.split()):
                first = not atoms[ci] or atoms[ci][-1]['verse'] != int(verse)
                actual_layout = layout if j == 0 else 0
                atoms[ci].append(dict(text=atom, verse=int(verse), style=style, layout=actual_layout, first=first))
                if first:
                    first_flags.append(actual_layout)
    blocks = []
    for ci, verses in enumerate(chapters):
        for vi, text in enumerate(verses, 1):
            assert ' '.join(body_parts[ci, vi]) == text, (version, ci, vi)
        block = encode_native('\n'.join(verses) + '\n')
        matches = list(re.finditer(b'\\S+', block))
        assert [decode_native(m.group()) for m in matches] == [a['text'] for a in atoms[ci]]
        for atom, match in zip(atoms[ci], matches):
            atom['byte'] = match.start()
        blocks.append(block)
    default = Counter(first_flags).most_common(1)[0][0]
    layout = [[(i, atom['layout']) for i, atom in enumerate(ch) if atom['layout'] != (default if atom['first'] else 0)] for ch in atoms]
    return dict(version=version, source_sha256=digest(raw), atoms=atoms, headings=headings, blocks=blocks, layout=layout, default_layout=default, chapter_books=[key[0] for key in keys], flags=dict(flags_count), header_levels=dict(header_levels), generated_titles=generated_titles, verses=sum((len(ch) for ch in chapters)), mapped_acrostic_headings=mapped_acrostic_headings)


def native_chapter_capacities(formatting):
    """Bound HUF04 native output without depending on installed font widths.

    This budgets maximum control-record sizes rather than reproducing exact C
    output. The writer checks every byte against the stored bound. Alignment
    reserves at most the 252-pixel viewport width in spaces, even at width zero.
    """
    capacities = []
    for atoms, headings, raw in zip(formatting['atoms'], formatting['headings'], formatting['blocks']):
        verse_count = raw.count(b'\n')
        capacity = sum(12 + len(str(verse)) for verse in range(1, verse_count + 1))
        for atom in atoms:
            text = encode_native(atom['text'])
            if any(not (32 <= byte <= 126 or 0x91 <= byte <= 0x94) for byte in text):
                raise ValueError(f"Unsupported body byte in capacity model: {atom['text']}")
            style, layout = atom['style'], atom['layout']
            capacity += len(text) + 1 + bool(layout)
            capacity += 4 if layout & 8 else 2 if layout & 4 else 0
            if style & 4:
                face_runs = sum(1 for _ in groupby(97 <= byte <= 122 for byte in text))
                capacity += 6 * face_runs
            elif style & 3:
                capacity += 6
            if layout & (16 | 32):
                capacity += 252
        for _, _, heading in headings:
            capacity += len(encode_native(heading)) + 14
        if not 0 < capacity <= 65500:
            raise ValueError(f"Native chapter capacity is out of range: {capacity}")
        capacities.append(capacity)
    return capacities


def inline_headings(data):
    blocks = []
    for atoms, raw, headings in zip(data['atoms'], data['blocks'], data['headings']):
        output = bytearray()
        previous = 0
        for atom, level, title in headings:
            position = atoms[atom]['byte'] if atom < len(atoms) else len(raw)
            output.extend(raw[previous:position])
            output.extend(bytes([3, 16 | level]) + encode_native(title) + b'\x04')
            previous = position
        output.extend(raw[previous:])
        blocks.append(bytes(output))
    return blocks


def searchable_chapters(blocks):
    """A plain host oracle of the indexed heading/body word stream per verse."""
    chapters = []
    for raw in blocks:
        plain = re.sub(rb'\x03[\x10-\x1f](.*?)\x04', lambda m: b' ' + m[1] + b' ', raw)
        assert plain.endswith(b'\n')
        chapters.append(decode_native(plain[:-1]).split('\n'))
    return chapters


def inline_formatting(data):
    """Encode combined source style/next-atom layout as atomic three-byte tokens.

    Controls precede separators so the dictionary retains its leading-space
    words. State bytes are nonzero, allowing ordinary front-dictionary storage.
    Removing controls reconstructs the exact searchable heading/body stream.
    """
    blocks = []
    chapters = []
    original = inline_headings(data)
    for atoms, headings, plain in zip(data['atoms'], data['headings'], original):
        titles = defaultdict(list)
        for position, level, title in headings:
            titles[position].append((level, title))
        tokens = []
        style = 0
        for index, atom in enumerate(atoms):
            separator = ('\n' if atom['first'] else ' ') if index else ''
            if index in titles:
                tokens.extend(TOKEN.findall(separator))
                separator = ''
                for level, title in titles[index]:
                    tokens.extend(TOKEN.findall(chr(3) + chr(16 | level) + title + chr(4)))
            source_style = atom['style'] & 7
            layout = atom['layout']
            default = data['default_layout'] if atom['first'] else 0
            if source_style != style or layout != default:
                if not 0 <= layout <= 126:
                    raise ValueError('Layout exceeds inline control range')
                tokens.append(chr(2) + chr(16 | source_style) + chr(layout + 1))
            style = source_style
            tokens.extend(TOKEN.findall(separator + atom['text']))
        tokens.append('\n')
        for level, title in titles[len(atoms)]:
            tokens.extend(TOKEN.findall(chr(3) + chr(16 | level) + title + chr(4)))
        if encode_native(''.join(t for t in tokens if not t.startswith(chr(2)))) != plain:
            raise ValueError('Inline controls changed the searchable source')
        chapters.append(tokens)
        blocks.append(encode_native(''.join(tokens)))
    return blocks, chapters
