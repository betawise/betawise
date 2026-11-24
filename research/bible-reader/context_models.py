#!/usr/bin/env python3
"""Train ROM-budgeted static backoff models; run local deterministic codecs.

No inference, network, Neo screenshots or saved device sessions are used.
Requires a host C++17 compiler. All stored model/resource bytes are counted.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import time
from measure import canonical, codes_for, pack, unpack


def normalize(counts):
    counts = [max(0, n) for n in counts]
    total = sum(counts)
    if total <= 65535:
        return counts
    assert len(counts) < 65535
    # Quantize without giving an extra count to every already-common symbol.
    # Find the largest integer scale whose rounded-down, positive frequencies
    # still fit a uint16 cumulative total.
    low, high = 0, 65536
    while high - low > 1:
        scale = (low + high) // 2
        if sum(max(1, n * scale // total) if n else 0 for n in counts) <= 65535:
            low = scale
        else:
            high = scale
    result = [max(1, n * low // total) if n else 0 for n in counts]
    assert sum(result) <= 65535
    return result


def cumulative(counts):
    out, total = bytearray(), 0
    for n in normalize(counts):
        total += n
        out.extend(struct.pack('>H', total))
    return bytes(out)


def front_word(blob, symbol, entries):
    blocks = (entries + 15) // 16
    offset = 4 * blocks + struct.unpack_from('>I', blob, 4 * (symbol // 16))[0]
    word = b''
    for _ in range(symbol % 16 + 1):
        prefix = blob[offset]
        end = blob.index(0, offset + 1)
        assert prefix <= len(word)
        word = word[:prefix] + blob[offset + 1:end]
        offset = end + 1
    return word


def sequences_bytes(sequences):
    out = bytearray(struct.pack('>I', len(sequences)))
    for seq in sequences:
        out.extend(struct.pack('>I', len(seq)))
        out.extend(struct.pack(f'>{len(seq)}H', *seq))
    return bytes(out)


def read_sequences(data):
    n = struct.unpack_from('>I', data)[0]
    result, p = [], 4
    for _ in range(n):
        count = struct.unpack_from('>I', data, p)[0]
        p += 4
        result.append(list(struct.unpack_from(f'>{count}H', data, p)))
        p += 2 * count
    assert p == len(data)
    return result


def train(sequences, alphabet, order, exclusion=False, wide=False, max_followers=64):
    global_counts = Counter(s for seq in sequences for s in seq)
    counts = [global_counts[s] for s in range(alphabet)]
    # Keep the original simple-selector baselines reproducible. The refined
    # exclusion selector scores against its actual quantized fallback model.
    effective = normalize(counts) if exclusion and not wide else counts
    total_counts = sum(effective)
    probs = [n / total_counts for n in effective]
    contexts = defaultdict(Counter)
    for seq in sequences:
        for i, s in enumerate(seq):
            for n in range(1, min(i, order) + 1):
                key = 1
                for previous in seq[i - n:i]:
                    key = key * (alphabet + 1) + previous + 1
                assert key <= 0xffffffff
                contexts[key][s] += 1
    candidates = []
    for key, freq in contexts.items():
        total = sum(freq.values())
        if total < 32:
            continue
        baseline = sum(-n * math.log2(probs[s]) for s, n in freq.items())
        ranked = freq.most_common(max_followers)
        best = None
        for k in [k for k in [4, 8, 16, 32, 64, 128, 256, 512] if k <= max_followers]:
            selected = ranked[:k]
            rest = total - sum(n for s, n in selected)
            denom = total + (rest == 0)
            cost = sum(-n * math.log2(n / denom) for s, n in selected)
            if rest:
                cost += -rest * math.log2(rest / denom)
                cost += baseline - sum(-n * math.log2(probs[s]) for s, n in selected)
                if exclusion:
                    cost += rest * math.log2(max(1e-15, 1 - sum(probs[s] for s, n in selected)))
            size = 12 + 4 * (len(selected) + 1)
            gain = baseline - cost
            net = gain - size * 8
            if net > 0 and (best is None or net > best[0]):
                best = (net, gain / size, size, sorted(selected + [(alphabet, max(1, rest))]))
        if best:
            net, ratio, size, entries = best
            candidates.append((ratio, net, key, size, entries))
    candidates.sort(key=lambda c: (-c[0], -c[1], c[2]))
    return counts, candidates


def model_bytes(counts, candidates, alphabet, order, budget, wide=False, exclusion=False):
    used, chosen = 0, []
    for _, _, key, size, entries in candidates:
        if used + size <= budget:
            used += size
            chosen.append((key, entries))
    records, values = bytearray(), bytearray()
    for key, entries in sorted(chosen):
        normalized = normalize([n for s, n in entries])
        records.extend(struct.pack('>IIHH', key, len(values), len(entries), sum(normalized)))
        total = 0
        for (symbol, _), n in zip(entries, normalized):
            total += n
            values.extend(struct.pack('>HH', symbol, total))
    if wide:
        total, base = 0, bytearray()
        for count in counts:
            total += count
            base.extend(struct.pack('>I', total))
        assert total < 1 << 24
    else:
        base = cumulative(counts)
    flags = (order if chosen else 0) | (256 if wide else 0) | (512 if exclusion else 0)
    blob = struct.pack('>III', alphabet, flags, len(chosen)) + base + records + values
    assert len(records) + len(values) == used
    return blob, used, len(chosen)


def parse_grammar(path):
    image = path.read_bytes()
    magic, m, d, ll, bl, nc, nr, np = struct.unpack('>8s7I', image[:36])
    assert magic == b'KJVGRMF1'
    ls = 64 + m
    bs = ls + 3 * ll
    gs = bs + bl
    ix = gs + 4 * np
    ps = ix + 16 * nc
    meta, lex, grammar = image[64:64 + m], image[bs:gs], image[gs:ix]
    codes = canonical(list(image[ls:ls + ll]))
    seqs = []
    for i in range(nc):
        offset, size, count, crc = struct.unpack_from('>IIII', image, ix + 16 * i)
        seqs.append(unpack(image[ps + offset:ps + offset + size], codes, count))
    return meta, d, lex, grammar, seqs


def expand_sequence(seq, words, grammar):
    d, out = len(words), bytearray()
    stack = []
    for symbol in seq:
        stack.append(symbol)
        while stack:
            s = stack.pop()
            if s < d:
                out.extend(words[s])
            else:
                a, b = struct.unpack_from('>HH', grammar, 4 * (s - d))
                assert a < s and b < s
                stack.extend([b, a])
    return bytes(out)


def extend_grammar(sequences, grammar, terminals, target):
    rules = list(struct.iter_unpack('>HH', grammar))
    while len(rules) < target:
        freq = Counter(p for seq in sequences for p in zip(seq, seq[1:]))
        selected = [p for p, n in freq.most_common(min(128, target - len(rules))) if n >= 4]
        if not selected:
            break
        mapping = {pair: terminals + len(rules) + i for i, pair in enumerate(selected)}
        assert terminals + len(rules) + len(selected) < 65535
        rules.extend(selected)
        updated = []
        for seq in sequences:
            out, i = [], 0
            while i < len(seq):
                symbol = mapping.get(tuple(seq[i:i + 2]))
                if symbol is not None:
                    out.append(symbol)
                    i += 2
                else:
                    out.append(seq[i])
                    i += 1
            updated.append(out)
        sequences = updated
    # Remove unreachable pair entries created by overlapping batched candidates.
    live = set(s for seq in sequences for s in seq if s >= terminals)
    stack = list(live)
    while stack:
        s = stack.pop()
        for child in rules[s - terminals]:
            if child >= terminals and child not in live:
                live.add(child)
                stack.append(child)
    remap = {s: terminals + i for i, s in enumerate(sorted(live))}
    compact = [(remap.get(a, a), remap.get(b, b)) for s in sorted(live) for a, b in [rules[s - terminals]]]
    depths = [0] * terminals
    for a, b in compact:
        depths.append(1 + max(depths[a], depths[b]))
    print(f'Grammar: {len(rules)} trained pairs, {len(compact)} reachable pairs, depth {max(depths)}', flush=True)
    return [[remap.get(s, s) for s in seq] for seq in sequences], b''.join(struct.pack('>HH', a, b) for a, b in compact), max(depths)


def dictionary_letters(lex, entries, output):
    """Actual independently seekable front-dictionary Huffman blocks."""
    blocks = (entries + 15) // 16
    offsets = list(struct.unpack_from(f'>{blocks}I', lex)) + [len(lex) - 4 * blocks]
    raw_blocks = [lex[4 * blocks + a:4 * blocks + b] for a, b in zip(offsets, offsets[1:])]
    freq = Counter(byte for block in raw_blocks for byte in block)
    lengths = codes_for(freq)
    symbols = sorted(freq)
    codes = canonical([lengths[b] for b in symbols])
    ids = {b: i for i, b in enumerate(symbols)}
    table = struct.pack('>HH', blocks, len(symbols)) + bytes(symbols) + bytes(lengths[b] for b in symbols)
    index, payload = bytearray(), bytearray()
    for raw in raw_blocks:
        encoded = pack([ids[b] for b in raw], codes)
        index.extend(struct.pack('>IHH', len(payload), len(encoded), len(raw)))
        payload.extend(encoded)
    image = table + index + payload
    output.write_bytes(image)
    image = output.read_bytes()
    nb, ns = struct.unpack_from('>HH', image)
    stored_symbols = image[4:4 + ns]
    stored_codes = canonical(list(image[4 + ns:4 + 2 * ns]))
    ix, ps = 4 + 2 * ns, 4 + 2 * ns + 8 * nb
    decoded_blocks = []
    for i in reversed(range(nb)):
        a, n, raw_n = struct.unpack_from('>IHH', image, ix + 8 * i)
        decoded = bytes(stored_symbols[s] for s in unpack(image[ps + a:ps + a + n], stored_codes, raw_n))
        assert decoded == raw_blocks[i]
        decoded_blocks.append(decoded)
    # Check front reconstruction from the independently Huffman-decoded blocks.
    reconstructed, off, pos = bytearray(), bytearray(), 0
    for block in reversed(decoded_blocks):
        off.extend(struct.pack('>I', pos))
        reconstructed.extend(block)
        pos += len(block)
    assert bytes(off + reconstructed) == lex
    return dict(bytes=len(image), original_bytes=len(lex), blocks=nb,
                max_raw_block_bytes=max(map(len, raw_blocks)), sha256=hashlib.sha256(image).hexdigest())


def decode_letter_dictionary(image):
    nb, ns = struct.unpack_from('>HH', image)
    symbols = image[4:4 + ns]
    codes = canonical(list(image[4 + ns:4 + 2 * ns]))
    ix, ps = 4 + 2 * ns, 4 + 2 * ns + 8 * nb
    offsets, blob = bytearray(), bytearray()
    for i in range(nb):
        a, n, raw_n = struct.unpack_from('>IHH', image, ix + 8 * i)
        raw = bytes(symbols[s] for s in unpack(image[ps + a:ps + a + n], codes, raw_n))
        offsets.extend(struct.pack('>I', len(blob)))
        blob.extend(raw)
    return bytes(offsets + blob)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', type=Path)
    ap.add_argument('--grammar', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--datasets', nargs='+', default=['byte', 'word', 'phrase'])
    ap.add_argument('--budgets', nargs='+', type=int, default=[0, 8192, 32768, 131072])
    ap.add_argument('--extend-phrases', type=int, default=0)
    ap.add_argument('--wide-base', action='store_true', help='32-bit base CDF, exact counts; context CDFs remain uint16')
    ap.add_argument('--exclusion', action='store_true', help='order-1 escape excludes its known followers from base probabilities')
    ap.add_argument('--max-followers', type=int, choices=[4, 8, 16, 32, 64, 128, 256, 512], default=64)
    args = ap.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    source = args.source.read_bytes()
    source_hash = hashlib.sha256(source).hexdigest()
    assert source_hash == 'f627b3c24a617013a4514ab24b6dd1bb305b09af237994c018f74cb9c7e71f41'
    books = json.loads(source.decode('utf-8-sig'))
    chapters = [('\n'.join(c) + '\n').encode() for b in books for c in b['chapters']]
    meta, d, lex, grammar, phrase_seqs = parse_grammar(args.grammar)
    depth = 5
    if args.extend_phrases:
        phrase_seqs, grammar, depth = extend_grammar(phrase_seqs, grammar, d, args.extend_phrases)
    words = [front_word(lex, i, d) for i in range(d)]
    for chapter, seq in zip(chapters, phrase_seqs):
        assert expand_sequence(seq, words, grammar) == chapter
    ids = {w.decode(): i for i, w in enumerate(words)}
    word_seqs = [[ids[t] for t in re.findall(r" ?[A-Za-z]+(?:['’][A-Za-z]+)*|.", c.decode(), re.S)] for c in chapters]
    binary = out / 'context-codec'
    subprocess.run(['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', str(Path(__file__).with_name('context_codec.cpp')), '-o', str(binary)], check=True)
    letters = dictionary_letters(lex, d, out / 'front-letters.bin')
    print('Dictionary letters:', json.dumps(letters), flush=True)
    rows = []
    for dataset in args.datasets:
        seqs, alphabet, order, resource_lex, resource_grammar = {
            'byte': ([list(c) for c in chapters], 256, 3, b'', b''),
            'word': (word_seqs, d, 1, lex, b''),
            'phrase': (phrase_seqs, d + len(grammar) // 4, 1, lex, grammar),
            'word2': (word_seqs, d, 2, lex, b''),
            'phrase2': (phrase_seqs, d + len(grammar) // 4, 2, lex, grammar),
        }[dataset]
        raw_input = sequences_bytes(seqs)
        input_path = out / f'{dataset}.symbols'
        input_path.write_bytes(raw_input)
        started = time.monotonic()
        counts, candidates = train(seqs, alphabet, order, args.exclusion, args.wide_base, args.max_followers)
        print(f'{dataset}: {len(candidates)} candidate contexts, trained in {time.monotonic()-started:.2f}s', flush=True)
        for budget in args.budgets:
            assert not args.exclusion or order <= 1
            model, context_bytes, contexts = model_bytes(counts, candidates, alphabet, order, budget, args.wide_base, args.exclusion)
            name = f'{dataset}-ctx-{budget}'
            model_path = out / (name + '.model')
            model_path.write_bytes(model)
            archive_path, decoded_path = out / (name + '.arith'), out / (name + '.decoded')
            started = time.monotonic()
            completed = subprocess.run([str(binary), str(input_path), str(model_path), str(archive_path), str(decoded_path)], check=True, capture_output=True, text=True)
            stats = json.loads(completed.stdout)
            assert decoded_path.read_bytes() == raw_input
            decoded = read_sequences(decoded_path.read_bytes())
            for i in reversed(range(len(chapters))):
                text = bytes(decoded[i]) if dataset == 'byte' else expand_sequence(decoded[i], words, resource_grammar)
                assert text == chapters[i]
            codec = archive_path.read_bytes()
            # Self-describing outer resource container; all section sizes counted.
            header = struct.pack('>8s8I', b'KJVCTX01', len(meta), d if resource_lex else 0, len(resource_lex), len(resource_grammar) // 4, ['byte', 'word', 'phrase', 'word2', 'phrase2'].index(dataset), len(codec), sum(map(len, chapters)), len(chapters)).ljust(64, b'\0')
            image = header + meta + resource_lex + resource_grammar + codec
            (out / (name + '.bin')).write_bytes(image)
            row = dict(dataset=dataset, wide_base=args.wide_base, exclusion=args.exclusion, max_followers=args.max_followers, context_budget=budget, contexts=contexts, context_bytes=context_bytes, bytes=len(image), model_bytes=len(model), payload_bytes=stats['payload_bytes'], resource_bytes=64+len(meta)+len(resource_lex)+len(resource_grammar), verified_chapters=len(chapters), host_encode_decode_seconds=round(time.monotonic()-started, 3), sha256=hashlib.sha256(image).hexdigest())
            if resource_lex:
                letter_blob = (out / 'front-letters.bin').read_bytes()
                compressed_header = struct.pack('>8s8I', b'KJVCTX02', len(meta), d, len(letter_blob), len(resource_grammar) // 4, ['byte', 'word', 'phrase', 'word2', 'phrase2'].index(dataset), len(codec), sum(map(len, chapters)), len(chapters)).ljust(64, b'\0')
                compressed_image = compressed_header + meta + letter_blob + resource_grammar + codec
                container_path = out / (name + '-letters.bin')
                container_path.write_bytes(compressed_image)
                # Decode only saved resources, including Huffman dictionary and
                # arithmetic model. The backend's --decode path has no source.
                saved = container_path.read_bytes()
                magic, mm, dd, lb, ng, kind, cb, raw_n, nc = struct.unpack('>8s8I', saved[:40])
                assert magic == b'KJVCTX02' and json.loads(saved[64:64 + mm]) == json.loads(meta)
                lex_start = 64 + mm
                stored_lex = decode_letter_dictionary(saved[lex_start:lex_start + lb])
                stored_words = [front_word(stored_lex, i, dd) for i in range(dd)]
                gs = lex_start + lb
                stored_grammar = saved[gs:gs + 4 * ng]
                stored_codec = saved[gs + 4 * ng:]
                assert len(stored_codec) == cb and stored_lex == resource_lex
                verify_archive = out / 'verify-container.arith'
                verify_output = out / 'verify-container.decoded'
                verify_archive.write_bytes(stored_codec)
                subprocess.run([str(binary), '--decode', str(verify_archive), str(verify_output)], check=True)
                stored_sequences = read_sequences(verify_output.read_bytes())
                assert len(stored_sequences) == nc
                for i in reversed(range(nc)):
                    assert expand_sequence(stored_sequences[i], stored_words, stored_grammar) == chapters[i]
                row.update(letter_compressed_bytes=len(compressed_image), letter_container_sha256=hashlib.sha256(compressed_image).hexdigest(), phrase_rules=ng, max_phrase_depth=depth if ng else 0)
            rows.append(row)
            print(json.dumps(row), flush=True)
            (out / 'context-results.json').write_text(json.dumps(dict(source_sha256=source_hash, dictionary_letters=letters, results=rows), indent=2) + '\n')


if __name__ == '__main__':
    main()
