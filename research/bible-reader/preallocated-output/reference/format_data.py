"""Selected production formatting codec: sparse Huffman spans and inline headings."""
from collections import Counter, defaultdict
import hashlib
import json
import re
import struct
from convert_source import convert_text, read_corpus, STYLE_MARKER, encode_native, decode_native
from compress_text import huffman_lengths, pack_symbols
STYLE = 'ibsr'
LAYOUT = 'plndcge'
WORD = re.compile("[A-Za-z]+(?:['’][A-Za-z]+)*")

def digest(data):
    return hashlib.sha256(data).hexdigest()

def uvarint(value):
    out = bytearray()
    while value >= 128:
        out.append(value & 127 | 128)
        value >>= 7
    out.append(value)
    return bytes(out)

def read_varint(data, offset):
    value = shift = 0
    while True:
        byte = data[offset]
        offset += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return (value, offset)
        shift += 7

class Bits:

    def __init__(self, data):
        self.data = data
        self.position = 0

    def get(self, width):
        value = 0
        for _ in range(width):
            value = value << 1 | self.data[self.position // 8] >> 7 - (self.position & 7) & 1
            self.position += 1
        return value

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

def encode_style_runs(chapters, projection):
    attributes = [bit for bit in range(4) if projection & 1 << bit and any((atom['style'] & 1 << bit for ch in chapters for atom in ch))]
    chunks = []
    for chapter in chapters:
        payload = bytearray()
        groups = []
        for bit in attributes:
            spans = []
            start = None
            for i in range(len(chapter) + 1):
                active = i < len(chapter) and chapter[i]['style'] & 1 << bit
                if active and start is None:
                    start = i
                if not active and start is not None:
                    spans.append((start, i))
                    start = None
            if spans:
                groups.append((bit, spans))
        if not groups:
            chunks.append(b'')
            continue
        payload.append(sum((1 << bit for bit, _ in groups)))
        expected = [atom['style'] & projection for atom in chapter]
        decoded = [0] * len(chapter)
        for bit, spans in groups:
            payload.extend(uvarint(len(spans)))
            previous = 0
            for start, end in spans:
                length = end - start
                payload.extend(uvarint(start - previous << 1 | (length > 1)))
                if length > 1:
                    payload.extend(uvarint(length - 2))
                previous = end
        pos = 1
        for bit in attributes:
            if not payload[0] & 1 << bit:
                continue
            count, pos = read_varint(payload, pos)
            previous = 0
            for _ in range(count):
                tag, pos = read_varint(payload, pos)
                start = previous + (tag >> 1)
                length = 1
                if tag & 1:
                    length, pos = read_varint(payload, pos)
                    length += 2
                for i in range(start, start + length):
                    decoded[i] |= 1 << bit
                previous = start + length
        assert pos == len(payload) and decoded == expected
        chunks.append(bytes(payload))
    return (bytes([projection]), chunks)

def build_word_defaults(data, scope, minimum_gain):
    vocabulary = sorted({w.replace('’', "'").lower() for raw in inline_headings(data) for w in WORD.findall(decode_native(raw))})
    ids = {w: i for i, w in enumerate(vocabulary)}
    books = {book: i for i, book in enumerate(dict.fromkeys(data['chapter_books']))}
    groups = 1 if scope == 'global' else 66
    bitmap_size = (groups + 7) // 8
    counts = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0]))
    keys = []
    for book, ch in zip(data['chapter_books'], data['atoms']):
        group = 0 if scope == 'global' else books[book]
        row = []
        for a in ch:
            words = WORD.findall(a['text'].replace('’', "'").lower())
            key = words[0] if len(words) == 1 else None
            row.append(key)
            if key:
                count = counts[key][group]
                count[0] += 1
                for bit in range(3):
                    count[bit + 1] += bool(a['style'] & 1 << bit)
        keys.append(row)
    selected = {}
    for word, by_group in counts.items():
        attributes = {}
        for bit in range(3):
            gain = sum((max(0, 2 * c[bit + 1] - c[0]) for c in by_group.values()))
            if gain < minimum_gain:
                continue
            bitmap = bytearray(bitmap_size)
            for group, c in by_group.items():
                if 2 * c[bit + 1] > c[0]:
                    bitmap[group // 8] |= 1 << group % 8
            if any(bitmap):
                attributes[bit] = bytes(bitmap)
        if attributes:
            selected[word] = attributes
    header = bytearray(b'WDP2' + bytes([scope == 'book']) + struct.pack('>H', groups) + uvarint(len(selected)))
    previous = 0
    for word, attributes in sorted(selected.items()):
        header.extend(uvarint(ids[word] - previous))
        previous = ids[word]
        header.append(sum((1 << bit for bit in attributes)))
        for bit in range(3):
            if bit in attributes:
                header.extend(attributes[bit])
    decoded = {}
    count, pos = read_varint(header, 7)
    previous = 0
    for _ in range(count):
        delta, pos = read_varint(header, pos)
        previous += delta
        mask = header[pos]
        pos += 1
        attributes = {}
        for bit in range(3):
            if mask & 1 << bit:
                attributes[bit] = bytes(header[pos:pos + bitmap_size])
                pos += bitmap_size
        decoded[vocabulary[previous]] = attributes
    assert pos == len(header) and decoded == selected
    residual = []
    for book, ch, row in zip(data['chapter_books'], data['atoms'], keys):
        group = 0 if scope == 'global' else books[book]
        chapter = []
        for a, key in zip(ch, row):
            default = sum(((bitmap[group // 8] >> group % 8 & 1) << bit for bit, bitmap in decoded.get(key, {}).items()))
            value = a['style'] ^ default
            assert value ^ default == a['style']
            chapter.append(dict(a, style=value))
        residual.append(chapter)
    return (bytes(header), residual, dict(words=len(selected), profile_bytes=len(header), predicted_attributes={str(bit): sum((bit in attrs for attrs in selected.values())) for bit in range(3)}))

def build_small_huffman_model(chunks):
    counts = Counter((byte for chunk in chunks for byte in chunk))
    lengths = huffman_lengths(counts) if len(counts) > 1 else {next(iter(counts), 0): 1}
    ordered = sorted(lengths, key=lambda symbol: (lengths[symbol], symbol))
    maximum = max(lengths.values())
    histogram = [sum((lengths[symbol] == length for symbol in ordered)) for length in range(1, maximum + 1)]
    raw = bytes([maximum]) + struct.pack('>' + 'H' * maximum, *histogram) + bytes(ordered)
    codes = {}
    code = previous = 0
    for symbol in ordered:
        length = lengths[symbol]
        code <<= length - previous
        codes[symbol] = (code, length)
        code += 1
        previous = length
    return (raw, codes)

def decode(blob, model_bytes, count):
    maximum = model_bytes[0]
    counts = struct.unpack_from('>' + 'H' * maximum, model_bytes, 1)
    symbols = model_bytes[1 + 2 * maximum:]
    assert len(symbols) == sum(counts)
    reader = Bits(blob)
    out = bytearray()
    for _ in range(count):
        code = first = index = 0
        for n in counts:
            code = code << 1 | reader.get(1)
            if 0 <= code - first < n:
                out.append(symbols[index + code - first])
                break
            index += n
            first = first + n << 1
        else:
            raise ValueError('invalid code')
    return bytes(out)

def compress_sidecar_chunks(chunks):
    table, codes = build_small_huffman_model(chunks)
    encoded = []
    for raw in chunks:
        if not raw:
            encoded.append(b'')
            continue
        payload = pack_symbols(raw, codes)
        assert decode(payload, table, len(raw)) == raw
        encoded.append(uvarint(len(raw)) + payload)
    return (table, encoded)

def pack_sidecar(data, header, chunks, component):
    """BWF2 singleton resource: sparse chapter bitmap and two-byte offsets."""
    bitmap = bytearray((len(chunks) + 7) // 8)
    offsets = [0]
    payload = bytearray()
    for chapter, chunk in enumerate(chunks):
        if chunk:
            bitmap[chapter // 8] |= 1 << chapter % 8
            payload.extend(chunk)
            offsets.append(len(payload))
    width = 2 if len(payload) < 65536 else 3
    prefix = b'BWF2' + struct.pack('>HBBHH', len(chunks), width, data['default_layout'], len(header), 0) + header + bytes([component])
    return prefix + bitmap + b''.join((x.to_bytes(width, 'big') for x in offsets)) + payload

def build_sidecars(data):
    profile, residual, stats = build_word_defaults(data, 'book', 32)
    assert stats['words'] <= 32, 'Formatting profile exceeds C decoder capacity'
    assert max((len(a['text']) for ch in data['atoms'] for a in ch), default=0) <= 64
    assert max((len(t) for ch in data['headings'] for _, _, t in ch), default=0) <= 256
    header, chunks = encode_style_runs(residual, 7)
    assert max(map(len, chunks), default=0) <= 512, 'Style scratch capacity exceeded'
    table, chunks = compress_sidecar_chunks(chunks)
    styles = pack_sidecar(data, profile + header + table, chunks, 1)
    events = data['layout']
    alphabet = sorted({0} | {value for chapter in events for _, value in chapter})
    width = (len(alphabet) - 1).bit_length()
    ids = {value: i for i, value in enumerate(alphabet)}
    chunks = []
    for chapter in events:
        raw = bytearray(uvarint(len(chapter)))
        previous = 0
        for atom, value in chapter:
            raw.extend(uvarint(atom - previous << width | ids[value]))
            previous = atom
        chunks.append(bytes(raw) if chapter else b'')
    table, chunks = compress_sidecar_chunks(chunks)
    header = bytes([0, 1, data['default_layout'], width, len(alphabet), 0]) + bytes(alphabet) + table
    layouts = pack_sidecar(data, header, chunks, 2)
    return (styles, layouts)

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
