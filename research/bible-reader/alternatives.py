#!/usr/bin/env python3
"""Offline singleton, alternating alphabet, and bounded LZSS experiments."""
import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib
from measure import canonical, codes_for, pack


class Reader:
    def __init__(self, data):
        self.data, self.position = data, 0

    def bits(self, n):
        result = 0
        for _ in range(n):
            p = self.position
            result = result * 2 + ((self.data[p // 8] >> (7 - p % 8)) & 1)
            self.position += 1
        return result

    def symbol(self, table):
        code = 0
        for n in range(1, 33):
            code = code * 2 + self.bits(1)
            if (n, code) in table:
                return table[n, code]
        raise ValueError('invalid Huffman code')


def model(tokens):
    freq = Counter(tokens)
    words = sorted(freq)
    lengths = codes_for(freq)
    codes = canonical([lengths[w] for w in words])
    return words, {w: codes[i] for i, w in enumerate(words)}


def table_size(words, codes, front=False):
    # Count serialized dictionary bytes, code lengths and a ROM symbol map.
    # Two bytes per ID are enough for these experiments.
    assert len(words) < 65536
    if not front:
        return 8 + 7 * len(words) + sum(len(w.encode()) + 1 for w in words)
    size, prev = 8 + 3 * len(words) + 4 * ((len(words) + 15) // 16), b''
    for i, w in enumerate(words):
        w = w.encode()
        if i % 16 == 0:
            prev = b''
        n = 0
        while n < min(len(w), len(prev)) and w[n] == prev[n]:
            n += 1
        size += 2 + len(w) - n
        prev = w
    return size


def lookup(codes):
    return {(n, c): s for s, (c, n) in codes.items()}


def encode_parts(parts):
    return pack(range(len(parts)), dict(enumerate(parts)))


def lzss_encode(data, window_bits):
    # Classic flag-byte LZSS, two-byte (distance-1,length-3) matches.
    # w10/l6, w11/l5, w12/l4; history is reset each chapter.
    length_bits = 16 - window_bits
    limit = (1 << length_bits) + 2
    window = 1 << window_bits
    chains = defaultdict(deque)
    out, pos = bytearray(), 0
    while pos < len(data):
        flag_pos = len(out)
        out.append(0)
        flags = 0
        for bit in range(8):
            if pos >= len(data):
                break
            best, distance = 0, 0
            candidates = chains[data[pos:pos + 3]]
            while candidates and candidates[0] < pos - window:
                candidates.popleft()
            for start in reversed(list(candidates)[-64:]):
                n = 3
                while n < limit and pos + n < len(data) and data[start + n] == data[pos + n]:
                    n += 1
                if n > best:
                    best, distance = n, pos - start
                if n == limit:
                    break
            # A short trailing key cannot actually support a three-byte match.
            if len(data) - pos < 3:
                best = 0
            if best >= 3:
                out.extend(struct.pack('>H', ((distance - 1) << length_bits) | (best - 3)))
                step = best
            else:
                flags |= 1 << bit
                out.append(data[pos])
                step = 1
            for p in range(pos, pos + step):
                q = chains[data[p:p + 3]]
                q.append(p)
                # This is an encoder-only speed heuristic, not decoder state.
                if len(q) > 64:
                    q.popleft()
            pos += step
        out[flag_pos] = flags
    return bytes(out)


def lzss_decode(data, window_bits, output_size):
    out, p = bytearray(), 0
    lb = 16 - window_bits
    while len(out) < output_size:
        flags = data[p]
        p += 1
        for bit in range(8):
            if len(out) == output_size:
                break
            if flags & (1 << bit):
                out.append(data[p])
                p += 1
            else:
                code = struct.unpack_from('>H', data, p)[0]
                p += 2
                distance, n = (code >> lb) + 1, (code & ((1 << lb) - 1)) + 3
                assert distance <= len(out)
                for _ in range(n):
                    out.append(out[-distance])
    assert len(out) == output_size and p == len(data)
    return bytes(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.source.read_bytes()
    books = json.loads(source.decode('utf-8-sig'))
    chapters = [('\n'.join(c) + '\n').encode() for b in books for c in b['chapters']]
    metadata, start = [], 0
    for b in books:
        metadata.append([b['name'], start, len(b['chapters'])])
        start += len(b['chapters'])
    common = 64 + len(json.dumps(metadata, ensure_ascii=False, separators=(',', ':')).encode()) + 16 * len(chapters)
    rows = []

    def record(name, payloads, dictionaries=0, **extra):
        payload = b''.join(payloads)
        (args.output / (re.sub('[^a-z0-9]+', '-', name.lower()) + '.payload')).write_bytes(payload)
        row = dict(method=name, bytes=len(payload) + dictionaries + common, payload_bytes=len(payload), table_bytes=dictionaries, framing_bytes=common, verified_chapters=len(chapters), payload_sha256=hashlib.sha256(payload).hexdigest(), **extra)
        rows.append(row)
        print(json.dumps(row), flush=True)

    # Escape any TOKEN occurring exactly once; literals retain attached spaces.
    ts = [re.findall(r" ?[A-Za-z]+(?:['’][A-Za-z]+)*|.", c.decode(), re.S) for c in chapters]
    freq = Counter(t for seq in ts for t in seq)
    baseline_words, baseline_codes = model(t for seq in ts for t in seq)
    baseline_payloads = [encode_parts([baseline_codes[t] for t in seq]) for seq in ts]
    for front in [False, True]:
        record(f'word Huffman baseline, {"front" if front else "plain"} dictionary + ROM map', baseline_payloads, table_size(baseline_words, baseline_codes, front))
    rare = {t for t, n in freq.items() if n == 1}
    escape = '\0'
    words, codes = model(escape if t in rare else t for seq in ts for t in seq)
    literal_freq = Counter(byte for t in rare for byte in t.encode())
    literal_lengths = codes_for(literal_freq)
    literal_ids = sorted(literal_freq)
    lit = canonical([literal_lengths[b] for b in literal_ids])
    literal_codes = {b: lit[i] for i, b in enumerate(literal_ids)}
    for huffman_literals in [False, True]:
        payloads = []
        for chapter, seq in zip(chapters, ts):
            parts = []
            for t in seq:
                if t not in rare:
                    parts.append(codes[t])
                else:
                    raw = t.encode()
                    assert len(raw) < 256
                    parts.extend([codes[escape], (len(raw), 8)])
                    parts.extend(literal_codes[b] if huffman_literals else (b, 8) for b in raw)
            packed = encode_parts(parts)
            reader, out = Reader(packed), bytearray()
            dl, ll = lookup(codes), lookup(literal_codes)
            for _ in seq:
                token = reader.symbol(dl)
                if token == escape:
                    n = reader.bits(8)
                    out.extend(reader.symbol(ll) if huffman_literals else reader.bits(8) for _ in range(n))
                else:
                    out.extend(token.encode())
            assert bytes(out) == chapter
            payloads.append(packed)
        extra = 512 if huffman_literals else 0
        for front in [False, True]:
            record(f'singleton escape, {"Huffman" if huffman_literals else "raw"} literals, {"front" if front else "plain"} dictionary', payloads, table_size(words, codes, front) + extra, escaped_tokens=len(rare))

    # Two alternating streams; empty entries permit arbitrary consecutive types.
    alternating = []
    for c in chapters:
        matches = re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)*|[^A-Za-z]+", c.decode())
        ws, ss, expect_word = [], [], True
        for token in matches:
            is_word = bool(re.match('[A-Za-z]', token))
            if is_word != expect_word:
                (ws if expect_word else ss).append('')
                expect_word = not expect_word
            (ws if expect_word else ss).append(token)
            expect_word = not expect_word
        if len(ss) < len(ws):
            ss.append('')
        assert len(ws) == len(ss)
        assert ''.join(w + s for w, s in zip(ws, ss)).encode() == c
        alternating.append((ws, ss))
    wm, wc = model([w for ws, ss in alternating for w in ws] + [''])
    sm, sc = model([s for ws, ss in alternating for s in ss] + [''])
    payloads = []
    for chapter, (ws, ss) in zip(chapters, alternating):
        parts = [code for w, s in zip(ws, ss) for code in (wc[w], sc[s])]
        packed = encode_parts(parts)
        reader, out = Reader(packed), []
        wl, sl = lookup(wc), lookup(sc)
        for _ in ws:
            out.extend([reader.symbol(wl), reader.symbol(sl)])
        assert ''.join(out).encode() == chapter
        payloads.append(packed)
    for front in [False, True]:
        record(f'alternating word separator Huffman, {"front" if front else "plain"} dictionaries', payloads, table_size(wm, wc, front) + table_size(sm, sc, front), word_entries=len(wm), separator_entries=len(sm))
    wf = Counter(w for ws, ss in alternating for w in ws)
    wr = {w for w, n in wf.items() if n == 1}
    ew, ec = model([escape if w in wr else w for ws, ss in alternating for w in ws] + [''])
    payloads = []
    for chapter, (ws, ss) in zip(chapters, alternating):
        parts = []
        for w, s in zip(ws, ss):
            if w in wr:
                raw = w.encode()
                assert len(raw) < 256
                parts.extend([ec[escape], (len(raw), 8)])
                parts.extend((b, 8) for b in raw)
            else:
                parts.append(ec[w])
            parts.append(sc[s])
        packed = encode_parts(parts)
        reader, out = Reader(packed), bytearray()
        el, sl = lookup(ec), lookup(sc)
        for _ in ws:
            w = reader.symbol(el)
            if w == escape:
                n = reader.bits(8)
                out.extend(reader.bits(8) for _ in range(n))
            else:
                out.extend(w.encode())
            out.extend(reader.symbol(sl).encode())
        assert bytes(out) == chapter
        payloads.append(packed)
    record('alternating Huffman + singleton raw escape, front dictionaries', payloads, table_size(ew, ec, True) + table_size(sm, sc, True), escaped_words=len(wr))
    for bits in [10, 11, 12]:
        payloads = []
        for chapter in chapters:
            packed = lzss_encode(chapter, bits)
            assert lzss_decode(packed, bits, len(chapter)) == chapter
            payloads.append(packed)
        record(f'LZSS chapter w{bits} l{16-bits}', payloads, history_bytes=1 << bits)
    (args.output / 'alternative-results.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(source).hexdigest(), results=rows), indent=2) + '\n')


if __name__ == '__main__':
    main()
