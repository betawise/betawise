#!/usr/bin/env python3
"""Offline KJV representation experiment. Python stdlib; optional python-lz4.

Input: thiagobodruk/bible json/en_kjv.json, retained separately with its hash.
No firmware, saved sessions, emulator, display captures or network are used.
"""
import argparse
import bz2
from collections import Counter
import hashlib
import heapq
import json
import lzma
from pathlib import Path
import re
import struct
import sys
import zlib


def codes_for(freq):
    heap = [(n, i, [s]) for i, (s, n) in enumerate(sorted(freq.items()))]
    heapq.heapify(heap)
    lengths = Counter()
    serial = len(heap)
    while len(heap) > 1:
        a, _, aa = heapq.heappop(heap)
        b, _, bb = heapq.heappop(heap)
        for s in aa + bb:
            lengths[s] += 1
        heapq.heappush(heap, (a + b, serial, aa + bb))
        serial += 1
    return dict(lengths)


def canonical(lengths):
    result, code, prev = {}, 0, 0
    for symbol, length in sorted(enumerate(lengths), key=lambda p: (p[1], p[0])):
        code <<= length - prev
        result[symbol] = (code, length)
        code += 1
        prev = length
    return result


def pack(ids, codes):
    out, bits, n = bytearray(), 0, 0
    for i in ids:
        code, size = codes[i]
        bits = (bits << size) | code
        n += size
        while n >= 8:
            n -= 8
            out.append((bits >> n) & 255)
        bits &= (1 << n) - 1
    if n:
        out.append(bits << (8 - n))
    return bytes(out)


def unpack(data, codes, count):
    lookup = {(size, code): symbol for symbol, (code, size) in codes.items()}
    out, code, size = [], 0, 0
    max_size = max(s for _, s in codes.values())
    for byte in data:
        for bit in range(7, -1, -1):
            code = (code << 1) | ((byte >> bit) & 1)
            size += 1
            if (size, code) in lookup:
                out.append(lookup[size, code])
                code = size = 0
                if len(out) == count:
                    return out
            elif size >= max_size:
                raise ValueError('invalid code')
    raise ValueError('truncated stream')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.source.read_bytes()
    books = json.loads(source.decode('utf-8-sig'))
    assert len(books) == 66
    chapters, metadata = [], []
    verses = 0
    for book in books:
        metadata.append([book['name'], len(chapters), len(book['chapters'])])
        for chapter in book['chapters']:
            assert chapter and all(isinstance(v, str) and v and '\n' not in v and '\0' not in v for v in chapter)
            chapters.append(('\n'.join(chapter) + '\n').encode('utf-8'))
            verses += len(chapter)
    assert len(chapters) == 1189 and verses == 31102
    raw = b''.join(chapters)
    # Attach ONE literal preceding space to each word; every other character
    # remains an explicit token. No inferred punctuation or whitespace rules.
    pattern = re.compile(r" ?[A-Za-z]+(?:['’][A-Za-z]+)*|.", re.S)
    tokenized = [pattern.findall(c.decode('utf-8')) for c in chapters]
    for c, ts in zip(chapters, tokenized):
        assert ''.join(ts).encode('utf-8') == c
    freq = Counter(t for ts in tokenized for t in ts)
    dictionary = sorted(freq)
    ids = {t: i for i, t in enumerate(dictionary)}
    sequences = [[ids[t] for t in ts] for ts in tokenized]
    meta = json.dumps(metadata, ensure_ascii=False, separators=(',', ':')).encode()
    rows = []

    def record(name, size, **kw):
        rows.append(dict(method=name, bytes=size, percent=round(size / len(raw) * 100, 2), **kw))

    common = 64 + len(meta) + 16 * len(chapters)
    record('raw UTF-8 + chapter index', len(raw) + common)
    for name, enc, dec in [
        ('zlib whole (archive baseline)', lambda b: zlib.compress(b, 9), zlib.decompress),
        ('bzip2 whole (archive baseline)', bz2.compress, bz2.decompress),
        ('xz whole (archive baseline)', lambda b: lzma.compress(b, preset=9), lzma.decompress),
    ]:
        packed = enc(raw)
        assert dec(packed) == raw
        record(name, len(packed), indexed=False)
    for window in [10, 12, 15]:
        total = 0
        for chapter in chapters:
            obj = zlib.compressobj(9, zlib.DEFLATED, -window)
            packed = obj.compress(chapter) + obj.flush()
            assert zlib.decompress(packed, -window) == chapter
            total += len(packed)
        record(f'DEFLATE chapter w{window}', total + common, history_bytes=1 << window)
    try:
        import lz4.block
        total = 0
        for chapter in chapters:
            packed = lz4.block.compress(chapter, mode='high_compression', compression=12, store_size=False)
            assert lz4.block.decompress(packed, uncompressed_size=len(chapter)) == chapter
            total += len(packed)
        record('LZ4 HC chapter', total + common)
    except ImportError:
        pass

    lengths = codes_for(freq)
    word_lengths = [lengths[t] for t in dictionary]
    huff = canonical(word_lengths)
    width = (len(dictionary) - 1).bit_length()
    for name, codes, lens in [
        (f'dictionary fixed {width}-bit', {i: (i, width) for i in range(len(dictionary))}, b''),
        ('dictionary canonical Huffman', huff, bytes(word_lengths)),
    ]:
        blob, offsets = bytearray(), bytearray()
        for token in dictionary:
            offsets.extend(struct.pack('>I', len(blob)))
            blob.extend(token.encode('utf-8') + b'\0')
        prefix = meta + offsets + lens + blob
        index, payload = bytearray(), bytearray()
        for chapter, seq in zip(chapters, sequences):
            packed = pack(seq, codes)
            index.extend(struct.pack('>IIII', len(payload), len(packed), len(seq), zlib.crc32(chapter)))
            payload.extend(packed)
        header = struct.pack('>8s7I', b'KJVEXP01', len(meta), len(dictionary), len(lens), len(blob), len(chapters), len(raw), width).ljust(64, b'\0')
        image = header + prefix + index + payload
        path = args.output / ('kjv-huffman.bin' if lens else 'kjv-fixed.bin')
        path.write_bytes(image)
        # Decode the serialized image, independently seeking EVERY chapter.
        image = path.read_bytes()
        _, m, d, ll, bl, nc, nr, fw = struct.unpack('>8s7I', image[:36])
        assert json.loads(image[64:64 + m]) == metadata
        off_start = 64 + m
        len_start = off_start + 4 * d
        blob_start = len_start + ll
        index_start = blob_start + bl
        payload_start = index_start + 16 * nc
        dc = canonical(list(image[len_start:blob_start])) if ll else {i: (i, fw) for i in range(d)}
        words = []
        for i in range(d):
            offset = struct.unpack_from('>I', image, off_start + 4 * i)[0]
            end = image.index(0, blob_start + offset, index_start)
            words.append(image[blob_start + offset:end])
        for i in reversed(range(nc)):
            offset, size, count, crc = struct.unpack_from('>IIII', image, index_start + 16 * i)
            packed = image[payload_start + offset:payload_start + offset + size]
            decoded = b''.join(words[t] for t in unpack(packed, dc, count))
            assert decoded == chapters[i] and zlib.crc32(decoded) == crc
        record(name, len(image), payload_bytes=len(payload), dictionary_bytes=len(offsets) + len(lens) + len(blob), chapter_index_bytes=len(index), header_and_book_bytes=64 + len(meta), sha256=hashlib.sha256(image).hexdigest(), verified_chapters=nc)

    # Byte Huffman baseline, using the same chapter framing.
    bf = Counter(raw)
    bc_lengths = codes_for(bf)
    bc = canonical([bc_lengths[i] for i in sorted(bf)])
    byte_ids = {b: i for i, b in enumerate(sorted(bf))}
    byte_symbols = sorted(bf)
    total = 0
    for chapter in chapters:
        packed = pack([byte_ids[b] for b in chapter], bc)
        assert bytes(byte_symbols[i] for i in unpack(packed, bc, len(chapter))) == chapter
        total += len(packed)
    record('byte canonical Huffman', total + common + 512)
    # Shared phrase grammar: batch the 128 most common adjacent symbol pairs,
    # then greedily replace nonoverlapping occurrences, never across chapters.
    # References always point to older symbols, bounding expansion depth.
    seqs = sequences
    productions = []
    depths = [0] * len(dictionary)
    base_blob = b''.join(t.encode('utf-8') + b'\0' for t in dictionary)
    base_offsets, position = bytearray(), 0
    for t in dictionary:
        base_offsets.extend(struct.pack('>I', position))
        position += len(t.encode('utf-8')) + 1
    # Sorted dictionary, front-coded in independently seekable blocks of 16.
    # Prefix lengths are UTF-8 BYTE counts, not Unicode character counts.
    front_offsets, front_data = bytearray(), bytearray()
    previous = b''
    for i, t in enumerate(dictionary):
        word = t.encode('utf-8')
        if i % 16 == 0:
            front_offsets.extend(struct.pack('>I', len(front_data)))
            previous = b''
        prefix = 0
        while prefix < min(len(previous), len(word)) and previous[prefix] == word[prefix]:
            prefix += 1
        front_data.append(prefix)
        front_data.extend(word[prefix:] + b'\0')
        previous = word
    front_blob = bytes(front_offsets + front_data)

    def front_word(data, symbol, entries):
        blocks = (entries + 15) // 16
        offset = 4 * blocks + struct.unpack_from('>I', data, 4 * (symbol // 16))[0]
        word = b''
        for _ in range(symbol % 16 + 1):
            prefix = data[offset]
            end = data.index(0, offset + 1)
            assert prefix <= len(word)
            word = word[:prefix] + data[offset + 1:end]
            offset = end + 1
        return word

    for i, t in enumerate(dictionary):
        assert front_word(front_blob, i, len(dictionary)) == t.encode('utf-8')
    for iteration in range(16):
        pairs = Counter(pair for seq in seqs for pair in zip(seq, seq[1:]))
        selected = [p for p, n in pairs.most_common(128) if n >= 16]
        if not selected:
            break
        replacements = {}
        for pair in selected:
            symbol = len(dictionary) + len(productions)
            assert symbol < 65536
            replacements[pair] = symbol
            productions.append(pair)
            depths.append(1 + max(depths[s] for s in pair))
        updated = []
        for seq in seqs:
            out, i = [], 0
            while i < len(seq):
                pair = tuple(seq[i:i + 2])
                if pair in replacements:
                    out.append(replacements[pair])
                    i += 2
                else:
                    out.append(seq[i])
                    i += 1
            updated.append(out)
        seqs = updated
        if iteration not in [3, 7, 15]:
            continue
        sf = Counter(s for seq in seqs for s in seq)
        # Retain zero-use terminals/productions as very rare symbols so the
        # entire lexicon remains addressable with this simple table format.
        sl = codes_for({i: max(1, sf[i]) for i in range(len(depths))})
        lens = bytes(sl[i] for i in range(len(depths)))
        cc = canonical(list(lens))
        index, payload = bytearray(), bytearray()
        for chapter, seq in zip(chapters, seqs):
            packed = pack(seq, cc)
            index.extend(struct.pack('>IIII', len(payload), len(packed), len(seq), zlib.crc32(chapter)))
            payload.extend(packed)
        grammar = b''.join(struct.pack('>HH', a, b) for a, b in productions)
        header = struct.pack('>8s7I', b'KJVGRAM1', len(meta), len(dictionary), len(lens), len(base_blob), len(chapters), len(raw), len(productions)).ljust(64, b'\0')
        image = header + meta + base_offsets + lens + base_blob + grammar + index + payload
        path = args.output / f'kjv-grammar-{len(productions)}.bin'
        path.write_bytes(image)
        image = path.read_bytes()
        _, m, d, ll, bl, nc, nr, np = struct.unpack('>8s7I', image[:36])
        start = 64 + m
        lengths_start = start + 4 * d
        blob_start = lengths_start + ll
        grammar_start = blob_start + bl
        index_start = grammar_start + 4 * np
        payload_start = index_start + 16 * nc
        dc = canonical(list(image[lengths_start:blob_start]))
        words = []
        for i in range(d):
            offset = struct.unpack_from('>I', image, start + 4 * i)[0]
            end = image.index(0, blob_start + offset, grammar_start)
            words.append(image[blob_start + offset:end])

        def expand(symbol):
            stack, output = [symbol], bytearray()
            while stack:
                s = stack.pop()
                if s < d:
                    output.extend(words[s])
                else:
                    a, b = struct.unpack_from('>HH', image, grammar_start + 4 * (s - d))
                    assert a < s and b < s
                    stack.extend([b, a])
            return bytes(output)

        for i in reversed(range(nc)):
            offset, size, count, crc = struct.unpack_from('>IIII', image, index_start + 16 * i)
            packed = image[payload_start + offset:payload_start + offset + size]
            decoded = b''.join(expand(s) for s in unpack(packed, dc, count))
            assert decoded == chapters[i] and zlib.crc32(decoded) == crc
        record(f'phrase grammar {np} + Huffman', len(image), payload_bytes=len(payload), dictionary_and_grammar_bytes=len(base_offsets) + len(lens) + bl + len(grammar), max_expansion_depth=max(depths), max_huffman_bits=max(lens), verified_chapters=nc, sha256=hashlib.sha256(image).hexdigest())
        if iteration == 15:
            # Same grammar and payload, replacing the terminal dictionary only.
            # Include a ROM canonical-order symbol map (uint16 IDs), so target
            # decoding need not scan the full lengths array or build it in RAM.
            order = b''.join(struct.pack('>H', s) for s in sorted(cc, key=lambda s: (cc[s][1], s)))
            header = struct.pack('>8s7I', b'KJVGRMF1', len(meta), d, len(lens), len(front_blob), nc, nr, np).ljust(64, b'\0')
            optimized = header + meta + lens + order + front_blob + grammar + index + payload
            path = args.output / 'kjv-front-grammar.bin'
            path.write_bytes(optimized)
            image = path.read_bytes()
            _, m, d, ll, bl, nc, nr, np = struct.unpack('>8s7I', image[:36])
            ls = 64 + m
            os = ls + ll
            bs = os + 2 * ll
            gs = bs + bl
            ix = gs + 4 * np
            ps = ix + 16 * nc
            dc = canonical(list(image[ls:os]))
            stored_order = [struct.unpack_from('>H', image, os + 2 * i)[0] for i in range(ll)]
            assert stored_order == sorted(dc, key=lambda s: (dc[s][1], s))
            lexicon = image[bs:gs]

            def expand_front(symbol):
                stack, out = [symbol], bytearray()
                while stack:
                    s = stack.pop()
                    if s < d:
                        out.extend(front_word(lexicon, s, d))
                    else:
                        a, b = struct.unpack_from('>HH', image, gs + 4 * (s - d))
                        assert a < s and b < s
                        stack.extend([b, a])
                return bytes(out)

            for i in reversed(range(nc)):
                offset, size, count, crc = struct.unpack_from('>IIII', image, ix + 16 * i)
                decoded = b''.join(expand_front(s) for s in unpack(image[ps + offset:ps + offset + size], dc, count))
                assert decoded == chapters[i] and zlib.crc32(decoded) == crc
            record('front dictionary + 2048 phrases + Huffman + ROM symbol map', len(image), payload_bytes=len(payload), front_dictionary_bytes=len(front_blob), huffman_lengths_and_map_bytes=len(lens) + len(order), phrase_bytes=len(grammar), max_expansion_depth=max(depths), verified_chapters=nc, sha256=hashlib.sha256(image).hexdigest())
    result = dict(source_sha256=hashlib.sha256(source).hexdigest(), source_bytes=len(source), raw_utf8_bytes=len(raw), raw_sha256=hashlib.sha256(raw).hexdigest(), books=len(books), chapters=len(chapters), verses=verses, tokens=sum(freq.values()), dictionary_entries=len(dictionary), fixed_bits=width, huffman_max_bits=max(word_lengths), max_chapter_bytes=max(map(len, chapters)), max_token_bytes=max(len(t.encode('utf-8')) for t in dictionary), non_ascii_characters=dict(Counter(c for c in raw.decode('utf-8') if ord(c) > 127)), results=rows)
    (args.output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
