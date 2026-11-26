#!/usr/bin/env python3
"""Read serialized prototype files back and verify source text and attributes."""
import argparse
import json
from pathlib import Path
import struct
from compare import (APP, read_formatting, inline_headings, decode_native,
    encode_native, unpack_symbols, verify_semantics, control_expansion, without_verse_markers, verse_markup)


def verify(path, data, blocks):
    image = (path / 'container.bin').read_bytes()
    assert image[:8] in (b'NKJVIF01', b'NKJVIF02')
    numbered = image[:8] == b'NKJVIF02'
    metadata, terminals, dictionary_bytes, model_bytes, chapters, _, rules_count, maximum = struct.unpack_from('>8I', image, 8)
    words_count, controls_count = struct.unpack_from('>HH', image, 44)
    assert terminals == words_count + controls_count
    dictionary_start = 64 + metadata
    position = dictionary_start + 4 * ((terminals + 15) // 16)
    words = []
    previous = b''
    for i in range(terminals):
        if i % 16 == 0:
            previous = b''
        prefix = image[position]
        end = image.index(b'\0', position + 1)
        word = previous[:prefix] + image[position + 1:end]
        words.append(decode_native(word))
        previous = word
        position = end + 1
    default_layout = image[position]
    position += 1
    controls = []
    for i in range(controls_count):
        kind, style, layout = image[position:position + 3]
        control = (('style', 'layout', 'both', 'verse', 'verse-open', 'verse-close')[kind], style, layout)
        controls.append(control)
        position += 3
        if kind >= 3:
            literal = control_expansion(control)
            assert image[position:position + len(literal)] == literal
            position += len(literal)
    assert position == dictionary_start + dictionary_bytes
    symbols = words[:words_count] + controls
    model_start = position
    model_maximum, symbol_count = struct.unpack_from('>HH', image, model_start)
    assert model_maximum == maximum and symbol_count == terminals + rules_count
    ordered = struct.unpack_from('>' + 'H' * symbol_count, image, model_start + 4 + 8 * maximum)
    codes = {}
    for length in range(1, maximum + 1):
        first, index, count = struct.unpack_from('>IHH', image, model_start + 4 + 8 * (length - 1))
        for offset in range(count):
            codes[ordered[index + offset]] = (first + offset, length)
    grammar_start = model_start + model_bytes
    rules = [struct.unpack_from('>HH', image, grammar_start + 4 * i) for i in range(rules_count)]
    records = grammar_start + 4 * rules_count
    payload = records + 16 * chapters
    atoms_checked = 0
    markers_checked = 0
    for ci in range(chapters):
        offset, size, count, expanded_size = struct.unpack_from('>IIII', image, records + 16 * ci)
        if numbered:
            assert expanded_size >> 16 == blocks[ci].count(b'\n')
            expanded_size &= 65535
        pending = list(reversed(unpack_symbols(image[payload + offset:payload + offset + size], codes, count)))
        expanded = []
        while pending:
            symbol = pending.pop()
            if symbol < terminals:
                expanded.append(symbols[symbol])
            else:
                a, b = rules[symbol - terminals]
                assert a < symbol and b < symbol
                pending.extend((b, a))
        stripped, numbers = without_verse_markers(expanded)
        assert encode_native(''.join(t for t in stripped if isinstance(t, str))) == blocks[ci]
        expanded_bytes = b''.join(control_expansion(t) if isinstance(t, tuple) else encode_native(t) for t in expanded)
        assert len(expanded_bytes) == expanded_size
        if numbered:
            import re
            found = re.findall(rb'\xb1\x0c\xb1\xb1\x02\xb1([0-9]+)\xb2\x02\xb2\xb2\x0c\xb2', expanded_bytes)
            assert list(map(int, found)) == numbers == list(range(1, blocks[ci].count(b'\n') + 1))
            markers_checked += len(numbers)
        expected = [(a['text'], a['style'] & 7, a['layout']) for a in data['atoms'][ci]]
        verify_semantics(stripped, default_layout, expected, data['headings'][ci])
        atoms_checked += len(expected)
    return dict(status='passed', serialized_chapters=chapters, atoms=atoms_checked,
        headings=sum(map(len, data['headings'])), exact_expanded_lengths=True,
        native_superscript_markers=markers_checked, chapter_counts_verified=numbered)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    data = read_formatting('nkjv', APP / 'upstream')
    blocks = inline_headings(data)
    report = json.loads((args.directory / 'results.json').read_text())
    for row in report['variants']:
        row['serialized_validation'] = verify(args.directory / row['mode'], data, blocks)
        print('PASS', row['mode'], row['serialized_validation'], flush=True)
    (args.directory / 'results.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
