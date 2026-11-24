#!/usr/bin/env python3
"""Host-only formatting sidecars; never rewrite Bible text or search resources."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
APP = ROOT / 'betawise/applets/BibleWise'
sys.path.insert(0, str(APP))
from convert_source import convert_ascii, read_corpus, STYLE_MARKER
from compress_text import build_huffman_model, front_dictionary, pack_symbols, unpack_symbols, TOKEN

STYLE = 'ibsr'
LAYOUT = 'plndcge'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def uvarint(value):
    out = bytearray()
    while value >= 128:
        out.append((value & 127) | 128)
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
            return value, offset
        shift += 7


class Bits:
    def __init__(self, data=None):
        self.data = bytearray() if data is None else data
        self.position = 0

    def put(self, value, width):
        for bit in range(width - 1, -1, -1):
            if not self.position & 7:
                self.data.append(0)
            self.data[-1] |= ((value >> bit) & 1) << (7 - (self.position & 7))
            self.position += 1

    def get(self, width):
        value = 0
        for _ in range(width):
            value = (value << 1) | ((self.data[self.position // 8] >> (7 - (self.position & 7))) & 1)
            self.position += 1
        return value

    def gamma(self, value):
        width = value.bit_length()
        self.put(0, width - 1)
        self.put(value, width)

    def read_gamma(self):
        width = 0
        while not self.get(1):
            width += 1
        return (1 << width) | self.get(width)


def parse_atom(token):
    markers = re.findall(r'\*([a-z]+)', token)
    assert len(markers) <= 1, token
    flags = markers[0] if markers else ''
    assert set(flags) <= set(STYLE + LAYOUT), token
    return convert_ascii(STYLE_MARKER.sub('', token)), flags


def read_formatting(version):
    repository = APP / 'upstream'
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
                title = re.sub(r'[\u0590-\u05ff]+\s*(?=[A-Za-z])', '', row['t'])
                mapped_acrostic_headings += title != row['t']
                headings[ci].append((len(atoms[ci]), int(row['h'] * 2), convert_ascii(title)))
            continue
        part = convert_ascii(STYLE_MARKER.sub('', row['t']))
        body_parts[ci, int(verse)].append(part)
        for index, token in enumerate(row['t'].split()):
            spelling, flags = parse_atom(token)
            flags_count.update(flags)
            style = sum(1 << STYLE.index(flag) for flag in flags if flag in STYLE)
            layout = sum(1 << LAYOUT.index(flag) for flag in flags if flag in LAYOUT)
            for j, atom in enumerate(spelling.split()):
                first = not atoms[ci] or atoms[ci][-1]['verse'] != int(verse)
                # A fraction conversion may split one source atom. Layout applies once.
                actual_layout = layout if j == 0 else 0
                atoms[ci].append(dict(text=atom, verse=int(verse), style=style,
                    layout=actual_layout, first=first))
                if first:
                    first_flags.append(actual_layout)
    blocks = []
    for ci, verses in enumerate(chapters):
        for vi, text in enumerate(verses, 1):
            assert ' '.join(body_parts[ci, vi]) == text, (version, ci, vi)
        block = ('\n'.join(verses) + '\n').encode('ascii')
        matches = list(re.finditer(rb'\S+', block))
        assert [m.group().decode() for m in matches] == [a['text'] for a in atoms[ci]]
        for atom, match in zip(atoms[ci], matches):
            atom['byte'] = match.start()
        blocks.append(block)
    default = Counter(first_flags).most_common(1)[0][0]
    layout = [[(i, atom['layout']) for i, atom in enumerate(ch)
        if atom['layout'] != (default if atom['first'] else 0)] for ch in atoms]
    return dict(version=version, source_sha256=digest(raw), atoms=atoms, headings=headings,
        blocks=blocks, layout=layout, default_layout=default, chapter_books=[key[0] for key in keys], flags=dict(flags_count),
        header_levels=dict(header_levels), generated_titles=generated_titles,
        verses=sum(len(ch) for ch in chapters), mapped_acrostic_headings=mapped_acrostic_headings)


def style_events(chapters, projection):
    result = []
    for chapter in chapters:
        state = 0
        events = []
        for index, atom in enumerate(chapter):
            value = atom['style'] & projection
            if value != state:
                events.append((index, value))
                state = value
        result.append(events)
    return result


def deltas(events, chapter, coordinate):
    previous = 0
    out = []
    for atom, value in events:
        position = atom if coordinate == 'atoms' else chapter[atom]['byte']
        out.append((position - previous, value))
        previous = position
    return out


def sparse_styles(chapters, events, codec, coordinate):
    alphabet = sorted({0} | {value for chapter in events for _, value in chapter})
    ids = {value: i for i, value in enumerate(alphabet)}
    width = (len(alphabet) - 1).bit_length()
    pairs = [deltas(e, ch, coordinate) for e, ch in zip(events, chapters)]
    rice_k = min(range(16), key=lambda k: sum((delta >> k) + 1 + k for ch in pairs for delta, _ in ch))
    chunks = []
    for chapter_pairs in pairs:
        if not chapter_pairs:
            chunks.append(b'')
            continue
        payload = bytearray()
        bits = Bits()
        for delta, state in chapter_pairs:
            if codec == 'varint_state':
                payload.extend(uvarint(delta) + bytes([state]))
            elif codec == 'packed_varint':
                payload.extend(uvarint((delta << width) | ids[state]))
            elif codec == 'gamma':
                bits.gamma(delta + 1)
                bits.put(ids[state], width)
            elif codec == 'rice':
                bits.put(0, delta >> rice_k)
                bits.put(1, 1)
                bits.put(delta & ((1 << rice_k) - 1), rice_k)
                bits.put(ids[state], width)
        raw = bytes(payload if codec in ('varint_state', 'packed_varint') else bits.data)
        chunk = uvarint(len(chapter_pairs)) + raw
        # Decode the actual bytes, not the encoder's event list.
        count, pos = read_varint(chunk, 0)
        decoded = []
        reader = Bits(chunk[pos:])
        for _ in range(count):
            if codec == 'varint_state':
                delta, pos = read_varint(chunk, pos)
                state = chunk[pos]
                pos += 1
            elif codec == 'packed_varint':
                value, pos = read_varint(chunk, pos)
                delta, state = value >> width, alphabet[value & ((1 << width) - 1)]
            elif codec == 'gamma':
                delta = reader.read_gamma() - 1
                state = alphabet[reader.get(width)]
            else:
                quotient = 0
                while not reader.get(1):
                    quotient += 1
                delta = (quotient << rice_k) | reader.get(rice_k)
                state = alphabet[reader.get(width)]
            decoded.append((delta, state))
        assert decoded == chapter_pairs, (codec, coordinate, decoded[:5], chapter_pairs[:5])
        chunks.append(chunk)
    header = bytes([width, len(alphabet), rice_k if codec == 'rice' else 0]) + bytes(alphabet)
    return header, chunks


def singleton_runs(chapters, projection):
    attributes = [bit for bit in range(4) if projection & (1 << bit) and
        any(atom['style'] & (1 << bit) for ch in chapters for atom in ch)]
    chunks = []
    for chapter in chapters:
        payload = bytearray()
        groups = []
        for bit in attributes:
            spans = []
            start = None
            for i in range(len(chapter) + 1):
                active = i < len(chapter) and chapter[i]['style'] & (1 << bit)
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
        payload.append(sum(1 << bit for bit, _ in groups))
        expected = [atom['style'] & projection for atom in chapter]
        decoded = [0] * len(chapter)
        for bit, spans in groups:
            payload.extend(uvarint(len(spans)))
            previous = 0
            for start, end in spans:
                length = end - start
                payload.extend(uvarint(((start - previous) << 1) | (length > 1)))
                if length > 1:
                    payload.extend(uvarint(length - 2))
                previous = end
        pos = 1
        for bit in attributes:
            if not payload[0] & (1 << bit):
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
    return bytes([projection]), chunks


def layout_chunks(data):
    chunks = []
    for events in data['layout']:
        if not events:
            chunks.append(b'')
            continue
        raw = bytearray(uvarint(len(events)))
        previous = 0
        for index, mask in events:
            raw.extend(uvarint(index - previous) + bytes([mask]))
            previous = index
        count, pos = read_varint(raw, 0)
        current = 0
        decoded = []
        for _ in range(count):
            delta, pos = read_varint(raw, pos)
            current += delta
            decoded.append((current, raw[pos]))
            pos += 1
        assert decoded == events and pos == len(raw)
        chunks.append(bytes(raw))
    # Verify default + exceptions reconstruct every layout marker.
    for chapter, events in zip(data['atoms'], data['layout']):
        overrides = dict(events)
        assert [overrides.get(i, data['default_layout'] if a['first'] else 0)
            for i, a in enumerate(chapter)] == [a['layout'] for a in chapter]
    return chunks


def front_pool(strings):
    words = sorted(set(strings))
    raw = front_dictionary(words) if words else b''
    count = len(words)
    pos = 4 * ((count + 15) // 16)
    previous = ''
    decoded = []
    for i in range(count):
        if not i % 16:
            previous = ''
        prefix = raw[pos]
        end = raw.index(0, pos + 1)
        previous = previous[:prefix] + raw[pos + 1:end].decode('ascii')
        decoded.append(previous)
        pos = end + 1
    assert decoded == words and pos == len(raw)
    return raw, {word: i for i, word in enumerate(words)}


def heading_chunks(headings, method, bible=None):
    strings = [text for chapter in headings for _, _, text in chapter]
    pool, ids = front_pool(strings)
    header = uvarint(len(ids)) + pool if method == 'front_pool' else b''
    chunks = []
    for chapter in headings:
        if not chapter:
            chunks.append(b'')
            continue
        payload = bytearray(uvarint(len(chapter)))
        previous = 0
        for atom, level, text in chapter:
            payload.extend(uvarint(atom - previous) + bytes([level]))
            previous = atom
            if method == 'front_pool':
                payload.extend(uvarint(ids[text]))
            else:
                encoded = text.encode('ascii') if method == 'raw' else bible.encode(text)
                payload.extend(uvarint(len(encoded)) + encoded)
        # Independently read locations, levels and string payloads.
        count, pos = read_varint(payload, 0)
        current = 0
        decoded = []
        inverse = {value: key for key, value in ids.items()}
        for _ in range(count):
            delta, pos = read_varint(payload, pos)
            current += delta
            level = payload[pos]
            pos += 1
            size, pos = read_varint(payload, pos)
            if method == 'front_pool':
                text = inverse[size]
            else:
                blob = bytes(payload[pos:pos + size])
                text = blob.decode('ascii') if method == 'raw' else bible.decode(blob)
                pos += size
            decoded.append((current, level, text))
        assert decoded == chapter and pos == len(payload)
        chunks.append(bytes(payload))
    return header, chunks


class BibleHeadingCodec:
    def __init__(self, image):
        metadata, count, dictionary_size, model_size, _, _, rule_count, _ = struct.unpack_from('>8I', image, 8)
        pos = 64 + metadata
        dictionary = image[pos:pos + dictionary_size]
        offset = 4 * ((count + 15) // 16)
        self.words = []
        previous = ''
        for i in range(count):
            if not i % 16:
                previous = ''
            prefix = dictionary[offset]
            end = dictionary.index(0, offset + 1)
            previous = previous[:prefix] + dictionary[offset + 1:end].decode('ascii')
            self.words.append(previous)
            offset = end + 1
        self.ids = {word: i for i, word in enumerate(self.words)}
        pos += dictionary_size
        maximum, symbols = struct.unpack_from('>HH', image, pos)
        self.codes = {}
        for length in range(1, maximum + 1):
            code, first, n = struct.unpack_from('>IHH', image, pos + 4 + 8 * (length - 1))
            for i in range(n):
                symbol = struct.unpack_from('>H', image, pos + 4 + 8 * maximum + 2 * (first + i))[0]
                self.codes[symbol] = (code + i, length)
        pos += model_size
        self.rules = [struct.unpack_from('>HH', image, pos + 4 * i) for i in range(rule_count)]
        self.pairs = {pair: len(self.words) + i for i, pair in enumerate(self.rules)}

    def grammar(self, sequence):
        while len(sequence) > 1:
            pairs = [(self.pairs[pair], pair) for pair in zip(sequence, sequence[1:]) if pair in self.pairs]
            if not pairs:
                break
            symbol, pair = min(pairs)
            out = []
            i = 0
            while i < len(sequence):
                if tuple(sequence[i:i+2]) == pair:
                    out.append(symbol)
                    i += 2
                else:
                    out.append(sequence[i])
                    i += 1
            sequence = out
        return sequence

    def encode(self, text):
        out = bytearray()
        tokens = TOKEN.findall(text)
        i = 0
        while i < len(tokens):
            known = tokens[i] in self.ids
            segment = []
            while i < len(tokens) and (tokens[i] in self.ids) == known:
                segment.append(tokens[i])
                i += 1
            if known:
                sequence = self.grammar([self.ids[token] for token in segment])
                encoded = pack_symbols(sequence, self.codes)
                out.extend(uvarint(len(sequence) << 1) + uvarint(len(encoded)) + encoded)
            else:
                raw = ''.join(segment).encode('ascii')
                out.extend(uvarint((len(raw) << 1) | 1) + raw)
        return bytes(out)

    def decode(self, raw):
        pos = 0
        result = []
        while pos < len(raw):
            tag, pos = read_varint(raw, pos)
            count = tag >> 1
            if tag & 1:
                result.append(raw[pos:pos + count].decode('ascii'))
                pos += count
            else:
                size, pos = read_varint(raw, pos)
                sequence = unpack_symbols(raw[pos:pos + size], self.codes, count)
                pos += size
                pending = list(reversed(sequence))
                while pending:
                    symbol = pending.pop()
                    if symbol < len(self.words):
                        result.append(self.words[symbol])
                    else:
                        a, b = self.rules[symbol - len(self.words)]
                        pending.extend([b, a])
        return ''.join(result)


def bundle(data, codec_header, styles, headings_header=b'', headings=None, layout_override=None):
    layout = layout_chunks(data) if layout_override is None else layout_override
    headings = headings or [b''] * len(styles)
    chunks = []
    for parts in zip(styles, layout, headings):
        chunk = bytearray([sum((bool(part) << i) for i, part in enumerate(parts))])
        for part in parts:
            if part:
                chunk.extend(uvarint(len(part)) + part)
        chunks.append(bytes(chunk))
    length = sum(map(len, chunks))
    width = 2 if length < 65536 else 3
    header = b'BWF1' + struct.pack('>HBBHH', len(chunks), width, data['default_layout'], len(codec_header), len(headings_header)) + codec_header + headings_header
    offsets = [0]
    for chunk in chunks:
        offsets.append(offsets[-1] + len(chunk))
    index = b''.join(value.to_bytes(width, 'big') for value in offsets)
    blob = header + index + b''.join(chunks)
    # Walk all random-access records and independently verify component framing.
    for i in reversed(range(len(chunks))):
        offset = int.from_bytes(index[i * width:(i+1) * width], 'big')
        end = int.from_bytes(index[(i+1) * width:(i+2) * width], 'big')
        raw = blob[len(header) + len(index) + offset:len(header) + len(index) + end]
        pos = 1
        decoded = []
        for field in range(3):
            if raw[0] & (1 << field):
                size, pos = read_varint(raw, pos)
                decoded.append(raw[pos:pos + size])
                pos += size
            else:
                decoded.append(b'')
        assert pos == len(raw) and decoded == [styles[i], layout[i], headings[i]]
    return blob, dict(header_bytes=len(header), chapter_index_bytes=len(index), chapter_framing_bytes=sum(len(chunk) - sum(map(len, parts)) for chunk, parts in zip(chunks, zip(styles, layout, headings))), style_payload_bytes=sum(map(len, styles)), layout_payload_bytes=sum(map(len, layout)), heading_payload_bytes=sum(map(len, headings)))


def byte_huffman(chunks):
    model, codes, _ = build_huffman_model([list(chunk) for chunk in chunks], 256)
    packed = []
    for chunk in chunks:
        if chunk:
            encoded = pack_symbols(list(chunk), codes)
            assert bytes(unpack_symbols(encoded, codes, len(chunk))) == chunk
            packed.append(uvarint(len(chunk)) + encoded)
        else:
            packed.append(b'')
    return model, packed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--versions', nargs='+', default=['kjv','nkjv','esv','niv','nasb','csb'])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    results = {}
    for version in args.versions:
        data = read_formatting(version)
        audit = {key: data[key] for key in ('source_sha256', 'flags', 'header_levels', 'generated_titles', 'default_layout', 'verses', 'mapped_acrostic_headings')}
        audit.update(atoms=sum(map(len, data['atoms'])), layout_exceptions=sum(map(len, data['layout'])), extra_headings=sum(map(len, data['headings'])), heading_text_bytes=sum(len(text) for ch in data['headings'] for _, _, text in ch))
        variants = {}
        for projection_name, projection in [('typography', 7), ('all_styles', 15)]:
            events = style_events(data['atoms'], projection)
            for coordinate in ('atoms', 'bytes'):
                for codec in ('varint_state', 'packed_varint', 'gamma', 'rice'):
                    header, chunks = sparse_styles(data['atoms'], events, codec, coordinate)
                    blob, sizes = bundle(data, header, chunks)
                    name = f'{projection_name}/{coordinate}/{codec}'
                    variants[name] = dict(bytes=len(blob), **sizes)
                    (args.output / f'{version}-{name.replace("/", "-")}.bin').write_bytes(blob)
            header, chunks = singleton_runs(data['atoms'], projection)
            blob, sizes = bundle(data, header, chunks)
            variants[f'{projection_name}/singleton_runs'] = dict(bytes=len(blob), **sizes)
            model, compressed = byte_huffman(chunks)
            blob, sizes = bundle(data, header + model, compressed)
            variants[f'{projection_name}/singleton_runs_huffman'] = dict(bytes=len(blob), **sizes)
            audit[projection_name + '_events'] = sum(map(len, events))
            audit[projection_name + '_dense_bits'] = (sum(map(len, data['atoms'])) * max(1, (len({v for ch in events for _, v in ch} | {0}) - 1).bit_length()) + 7) // 8
        headings = {}
        # KJV reuses the exact production text dictionary, grammar and Huffman.
        bible = BibleHeadingCodec((APP / 'build/data/kjv/container.bin').read_bytes()) if version == 'kjv' else None
        for method in ('raw', 'front_pool') + (('existing_bible_codec',) if bible else ()):
            header, chunks = heading_chunks(data['headings'], method, bible)
            blob, sizes = bundle(data, b'', [b''] * len(chunks), header, chunks)
            headings[method] = dict(bytes=len(blob), **sizes)
            (args.output / f'{version}-headings-{method}.bin').write_bytes(blob)
        if version == 'kjv':
            combined = {}
            for projection_name, projection in [('typography', 7), ('all_styles', 15)]:
                for codec in ('rice', 'singleton_runs'):
                    if codec == 'rice':
                        header, styles = sparse_styles(data['atoms'], style_events(data['atoms'], projection), codec, 'atoms')
                    else:
                        header, styles = singleton_runs(data['atoms'], projection)
                    for method in ('front_pool', 'existing_bible_codec'):
                        head_header, heads = heading_chunks(data['headings'], method, bible)
                        blob, sizes = bundle(data, header, styles, head_header, heads)
                        name = f'{projection_name}/{codec}/{method}'
                        combined[name] = dict(bytes=len(blob), **sizes)
                        (args.output / f'kjv-combined-{name.replace("/", "-")}.bin').write_bytes(blob)
            audit['combined'] = combined
            # Search is independently proven unchanged: no production resources touched.
            audit['production_resources'] = {name: digest((APP / 'build/data/kjv' / name).read_bytes()) for name in ('container.bin', 'search.bin', 'pruning.bin', 'verses.bin')}
            expected=json.loads((APP/'build/data/kjv/results.json').read_text())['resource_sha256']
            assert all(value==expected[name] for name,value in audit['production_resources'].items())
            # Whole-file compression is a size bound, not a chapter-seekable option.
            raw = (args.output / 'kjv-combined-all_styles-rice-existing_bible_codec.bin').read_bytes()
            audit['whole_blob_deflate_reference_bytes'] = len(zlib.compress(raw, 9))
        audit['style_masks'] = dict(Counter(a['style'] for ch in data['atoms'] for a in ch))
        audit['max_chapter_font_transition_bytes_at_three_bytes_per_event'] = max(len(e)*3 for e in style_events(data['atoms'],15))
        results[version] = dict(audit=audit, variants=variants, headings=headings)
        (args.output/'results.json').write_text(json.dumps(dict(status='partial',versions=results),indent=2))
        print(version, 'style best', min((v['bytes'], k) for k, v in variants.items()), 'extra headings', audit['extra_headings'], flush=True)
    (args.output / 'results.json').write_text(json.dumps(dict(status='passed', versions=results), indent=2))


if __name__ == '__main__':
    main()
