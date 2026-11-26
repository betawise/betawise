#!/usr/bin/env python3
"""Check that inline controls leave all canonical search postings unchanged."""
import argparse
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
APP = HERE / 'sidecar-reference'


def unpack_index(path):
    raw = path.read_bytes()
    magic, vocabulary, terminals, version, size = struct.unpack_from('>8sHHII', raw)
    assert magic == b'IDXEXP02' and version == 1
    start = 20 + 4 * (vocabulary + 1)
    end = start + (terminals * 14 + 7) // 8
    values = []
    bits = int.from_bytes(raw[start:end], 'big')
    padding = (end - start) * 8 - terminals * 14
    for i in range(terminals):
        values.append((bits >> (padding + 14 * (terminals - i - 1))) & 16383)
    assert len(raw[end:]) == size
    return vocabulary, raw[20:start], values, raw[end:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    original = unpack_index(APP / 'build/data/nkjv/search.bin')
    report = json.loads((args.directory / 'results.json').read_text())
    for row in report['variants']:
        index = unpack_index(args.directory / row['mode'] / 'search.bin')
        assert index[:2] == original[:2]
        assert index[3] == original[3]
        assert index[2][:len(original[2])] == original[2]
        # New non-space spellings can be introduced when a native verse
        # marker separates a leading-space token. Verify those IDs as well.
        import sys
        sys.path.insert(0, str(APP))
        from convert_source import decode_native, encode_native
        from build_index import build_index
        from format_data import inline_headings, read_formatting
        image = (args.directory / row['mode'] / 'container.bin').read_bytes()
        dictionary_start = 64 + struct.unpack_from('>I', image, 8)[0]
        terminals = struct.unpack_from('>I', image, 12)[0]
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
        rebuilt, _ = build_index(inline_headings(read_formatting('nkjv', APP / 'upstream')), words)
        assert rebuilt == (args.directory / row['mode'] / 'search.bin').read_bytes()
        assert all(word == original[0] + 1 for word in index[2][row['text_terminals']:])
        row['identical_search_postings'] = True
        row['identical_existing_normalization'] = True
    (args.directory / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS canonical records, all postings, existing word normalization, nonword control IDs')


if __name__ == '__main__':
    main()
