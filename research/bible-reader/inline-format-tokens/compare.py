#!/usr/bin/env python3
"""Host-only semantic formatting terminals in the production phrase/Huffman codec."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
# Keep the original sidecar comparison reproducible after production adoption.
APP = HERE / 'sidecar-reference'
sys.path.insert(0, str(APP))
from compress_text import (TOKEN, build_huffman_model, front_dictionary,
    frequent_word_cache, order_dictionary, pack_symbols, train_phrase_grammar,
    unpack_symbols)
from convert_source import decode_native, encode_native
from format_data import inline_headings, read_formatting
from build_index import build_index, grammar_summaries


def verse_markup(number):
    """Exact visible/protected superscript bytes emitted by BufferVerseNumber."""
    return b'\xb1\x0c\xb1\xb1\x02\xb1' + str(number).encode('ascii') + b'\xb2\x02\xb2\xb2\x0c\xb2'


CONTROL_KIND = {'style': 0, 'layout': 1, 'both': 2, 'verse': 3, 'verse-open': 4, 'verse-close': 5}


def control_expansion(control):
    kind, value, layout = control
    if kind == 'verse':
        return verse_markup(value)
    if kind == 'verse-open':
        return verse_markup(1)[:6]
    if kind == 'verse-close':
        return verse_markup(1)[-6:]
    return bytes([2, CONTROL_KIND[kind], value, layout])


def without_verse_markers(tokens):
    """Strip only the explicitly delimited number payload; never body digits."""
    plain = []
    numbers = []
    digits = None
    for token in tokens:
        if isinstance(token, tuple):
            if token[0] == 'verse':
                assert digits is None
                numbers.append(token[1])
            elif token[0] == 'verse-open':
                assert digits is None
                digits = ''
            elif token[0] == 'verse-close':
                assert digits is not None and digits.isdigit()
                numbers.append(int(digits))
                digits = None
            else:
                assert digits is None
                plain.append(token)
        elif digits is not None:
            assert token.isascii() and token.isdigit()
            digits += token
        else:
            plain.append(token)
    assert digits is None
    return plain, numbers


def chapter_stream(atoms, headings, default_layout, combined, verse_mode=None):
    """Place control terminals before separators, preserving leading-space words."""
    pieces = []
    expected = []
    titles = {}
    for position, level, title in headings:
        titles.setdefault(position, []).append((level, title))
    style = 0
    for index, atom in enumerate(atoms):
        if index:
            separator = '\n' if atom['first'] else ' '
        else:
            separator = ''
        # Headings retain the production searchable byte stream unchanged.
        # Separator precedes a heading, as in the production formatter events.
        if index in titles:
            pieces.append(separator)
            separator = ''
            for level, title in titles[index]:
                pieces.append(chr(3) + chr(16 | level) + title + chr(4))
        layout_default = default_layout if atom['first'] else 0
        if combined:
            if style != atom['style'] or atom['layout'] != layout_default:
                pieces.append(('both', atom['style'], atom['layout']))
        else:
            if style != atom['style']:
                pieces.append(('style', atom['style'], 0))
            if atom['layout'] != layout_default:
                pieces.append(('layout', 0, atom['layout']))
        style = atom['style']
        if verse_mode and atom['first']:
            pieces.append(separator)
            if verse_mode == 'verse-whole':
                pieces.append(('verse', atom['verse'], 0))
            else:
                pieces.extend([('verse-open', 0, 0), str(atom['verse']), ('verse-close', 0, 0)])
            pieces.append(atom['text'])
        else:
            pieces.append(separator + atom['text'])
        expected.append((atom['text'], atom['style'], atom['layout']))
    pieces.append('\n')
    for level, title in titles.get(len(atoms), []):
        pieces.append(chr(3) + chr(16 | level) + title + chr(4))
    return pieces, expected


def verify_semantics(tokens, default_layout, expected, expected_headings):
    """Independent byte parser: reconstruct atom attributes and heading events."""
    style = 0
    pending_layout = None
    first = True
    text = bytearray()
    atoms = []
    headings = []
    heading = None
    level = None

    def finish_atom():
        nonlocal pending_layout, first
        if text:
            atoms.append((decode_native(bytes(text)), style,
                pending_layout if pending_layout is not None else default_layout if first else 0))
            text.clear()
            pending_layout = None
            first = False

    for token in tokens:
        if isinstance(token, tuple):
            finish_atom()
            kind, value, layout = token
            if kind in ('style', 'both'):
                style = value
            if kind in ('layout', 'both'):
                pending_layout = layout
            continue
        for byte in encode_native(token):
            if heading is not None:
                if level is None:
                    level = byte & 15
                elif byte == 4:
                    headings.append((len(atoms), level, decode_native(bytes(heading))))
                    heading = level = None
                else:
                    heading.append(byte)
            elif byte == 3:
                finish_atom()
                heading = bytearray()
            elif byte in (32, 10):
                finish_atom()
                if byte == 10:
                    first = True
            else:
                text.append(byte)
    finish_atom()
    assert atoms == expected, next(((i, a, b) for i, (a, b) in enumerate(zip(atoms, expected)) if a != b), (len(atoms), len(expected)))
    assert headings == expected_headings


def encode_variant(data, blocks, metadata, base_words, mode, output):
    numbered = mode.startswith('verse-')
    combined = mode == 'combined' or numbered
    default_layout = data['default_layout'] if mode != 'explicit' else 0
    streams = []
    expected = []
    for atoms, headings in zip(data['atoms'], data['headings']):
        pieces, events = chapter_stream(atoms, headings, default_layout, combined, mode if numbered else None)
        sequence = []
        for piece in pieces:
            sequence.extend([piece] if isinstance(piece, tuple) else TOKEN.findall(piece))
        streams.append(sequence)
        expected.append(events)
    controls = sorted({t for ch in streams for t in ch if isinstance(t, tuple)})
    # Retain original text IDs/canonical spellings for search compatibility.
    extra = sorted({t for ch in streams for t in ch if isinstance(t, str)} - set(base_words))
    words = base_words + extra
    ids = {word: i for i, word in enumerate(words)}
    ids.update({control: len(words) + i for i, control in enumerate(controls)})
    sequences = [[ids[t] for t in ch] for ch in streams]
    terminal_count = len(words) + len(controls)
    print(mode, 'training', len(controls), 'control terminals', flush=True)
    sequences, rules = train_phrase_grammar(sequences, terminal_count)
    model, codes, maximum = build_huffman_model(sequences, terminal_count + len(rules))
    payload = bytearray()
    records = bytearray()
    expanded_sizes = []
    terminals = words + controls
    for ci, sequence in enumerate(sequences):
        encoded = pack_symbols(sequence, codes)
        payload.extend(encoded)
        expanded_size = sum(len(control_expansion(t)) if isinstance(t, tuple) else len(encode_native(t)) for t in streams[ci])
        expanded_sizes.append(expanded_size)
        verse_count = blocks[ci].count(b'\n')
        assert expanded_size < 65536 and verse_count <= 176
        size_field = (verse_count << 16 | expanded_size) if numbered else expanded_size
        records.extend(struct.pack('>IIII', len(payload) - len(encoded), len(encoded), len(sequence), size_field))
        decoded = unpack_symbols(encoded, codes, len(sequence))
        assert decoded == sequence
        expanded = []
        pending = list(reversed(decoded))
        while pending:
            symbol = pending.pop()
            if symbol < terminal_count:
                expanded.append(terminals[symbol])
            else:
                a, b = rules[symbol - terminal_count]
                pending.extend((b, a))
        assert expanded == streams[ci]
        # A control expands to 0x02, kind, style, layout: fixed four-byte markup.
        expanded_bytes = b''.join(control_expansion(t)
            if isinstance(t, tuple) else encode_native(t) for t in expanded)
        assert len(expanded_bytes) == expanded_size
        stripped, numbers = without_verse_markers(expanded)
        if numbered:
            assert numbers == list(range(1, verse_count + 1)), (ci, numbers)
            # Check serialized literal expansions, including byte-for-byte native
            # marker geometry, independently of the stripped semantic stream.
            import re
            found = re.findall(rb'\xb1\x0c\xb1\xb1\x02\xb1([0-9]+)\xb2\x02\xb2\xb2\x0c\xb2', expanded_bytes)
            assert list(map(int, found)) == numbers
        plain = encode_native(''.join(t for t in stripped if isinstance(t, str)))
        assert plain == blocks[ci], ci
        verify_semantics(stripped, default_layout, expected[ci], data['headings'][ci])
    # Empty text-dictionary entries let an index normalization table explicitly
    # mark control IDs as nonwords. Three-byte dispatch records identify them.
    dictionary = front_dictionary(words + [''] * len(controls))
    dispatch = bytes([default_layout]) + b''.join(bytes([
        CONTROL_KIND[kind], style, layout]) + (control_expansion((kind, style, layout))
            if CONTROL_KIND[kind] >= 3 else b'') for kind, style, layout in controls)
    dictionary += dispatch
    grammar = b''.join(struct.pack('>HH', *r) for r in rules)
    frequencies = Counter(t for ch in streams for t in ch if isinstance(t, str))
    cache = frequent_word_cache(words + [''] * len(controls),
        [frequencies[w] for w in words] + [0] * len(controls))
    header = bytearray(struct.pack('>8s8I', b'NKJVIF02' if numbered else b'NKJVIF01', len(metadata), terminal_count,
        len(dictionary), len(model), len(blocks), sum(map(len, blocks)), len(rules), maximum).ljust(64, b'\0'))
    struct.pack_into('>HH', header, 44, len(words), len(controls))
    body = metadata + dictionary + model + grammar + records + payload
    struct.pack_into('>I', header, 40, 64 + len(body))
    image = bytes(header) + body + cache
    index, vocabulary = build_index(blocks, words + [''] * len(controls))
    pruning = grammar_summaries(words + [''] * len(controls), image)
    output.mkdir(parents=True, exist_ok=True)
    for name, blob in [('container.bin', image), ('search.bin', index), ('pruning.bin', pruning)]:
        (output / name).write_bytes(blob)
    result = dict(mode=mode, container_bytes=len(image), search_bytes=len(index),
        pruning_bytes=len(pruning), verses_bytes=0 if numbered else len(data['atoms']) * 2,
        resource_bytes=len(image) + len(index) + len(pruning) + (0 if numbered else 2 * len(blocks)),
        expanded_markup_bytes=sum(expanded_sizes), maximum_expanded_chapter_bytes=max(expanded_sizes),
        payload_bytes=len(payload), dictionary_bytes=len(dictionary), model_bytes=len(model),
        grammar_bytes=len(grammar), cache_bytes=len(cache), chapter_records_bytes=len(records),
        metadata_bytes=len(metadata), control_dispatch_bytes=len(dispatch),
        control_terminals=len(controls), control_occurrences=sum(isinstance(t, tuple) for ch in streams for t in ch),
        extra_text_terminals=len(extra), text_terminals=len(words), rules=len(rules), vocabulary=vocabulary,
        default_layout=default_layout, verified_chapters=len(blocks),
        verified_atoms=sum(map(len, expected)), verified_headings=sum(map(len, data['headings'])),
        native_superscript_markers=numbered, verse_count_in_chapter_record=numbered,
        verified_verse_markers=sum(block.count(b'\n') for block in blocks) if numbered else 0,
        source_text_and_attributes_roundtrip=True, sha256=hashlib.sha256(image).hexdigest())
    (output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'build/production-typography')
    parser.add_argument('--modes', nargs='+', choices=['explicit', 'separate', 'combined', 'verse-whole', 'verse-parts'], default=['explicit', 'separate', 'combined'])
    args = parser.parse_args()
    source = APP / 'build/data/nkjv'
    data = read_formatting('nkjv', APP / 'upstream')
    # Match production's three supported typography bits; red-letter metadata
    # exists upstream but is deliberately absent from the current sidecars.
    for chapter in data['atoms']:
        for atom in chapter:
            atom['style'] &= 7
    blocks = inline_headings(data)
    original = (source / 'container.bin').read_bytes()
    metadata = original[64:64 + struct.unpack_from('>I', original, 8)[0]]
    base_words = order_dictionary(sorted({t for block in blocks for t in TOKEN.findall(decode_native(block))}))
    files = ['container.bin', 'search.bin', 'pruning.bin', 'verses.bin', 'styles.bin', 'layouts.bin']
    baseline = {name: (source / name).stat().st_size for name in files}
    rows = [encode_variant(data, blocks, metadata, base_words, mode, args.output / mode) for mode in args.modes]
    for row in rows:
        row['delta_bytes'] = row['resource_bytes'] - sum(baseline.values())
        row['delta_percent'] = 100 * row['delta_bytes'] / sum(baseline.values())
    report = dict(version='NKJV', status='passed', baseline=baseline,
        baseline_resource_bytes=sum(baseline.values()), variants=rows,
        baseline_sha256={name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in files},
        source_sha256=data['source_sha256'], production_changed=False,
        scope='Resource bytes only; no device decoder/ROM/speed claims. Heading bytes and search postings preserved.')
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
