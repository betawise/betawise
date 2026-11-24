#!/usr/bin/env python3
"""Inspect jburson KJV word flags; measure and verify a style event sidecar."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


def varint(n):
    out = bytearray()
    while n >= 128:
        out.append((n & 127) | 128)
        n >>= 7
    out.append(n)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.source.read_bytes()
    items = json.loads(source)
    flags, combinations, styles, plain = Counter(), Counter(), [], []
    verses = headings = marked = 0
    for item in items:
        if 'h' in item:
            headings += 1
            continue
        verses += 1
        tokens = item['t'].split()
        paragraphs = []
        for i, token in enumerate(tokens):
            matches = re.findall(r'\*([a-z]+)', token)
            assert len(matches) <= 1
            fs = ''.join(matches)
            assert set(fs) <= set('psr'), (token, fs)
            flags.update(fs)
            if fs:
                marked += 1
                combinations[fs] += 1
            if 'p' in fs:
                paragraphs.append(i)
            styles.append(int('s' in fs) + 2 * int('r' in fs))
        assert paragraphs == [0]
        plain.append(re.sub(r'\*[a-z]+', '', item['t']))
    assert verses == 31102 and headings == 1327
    encoded, events = bytearray(), []
    previous = state = 0
    for i, style in enumerate(styles):
        if style != state:
            encoded.extend(varint(i - previous))
            encoded.append(style)
            events.append((i, style))
            previous, state = i, style
    (args.output / 'jburson-style-transitions.bin').write_bytes(encoded)
    stored = (args.output / 'jburson-style-transitions.bin').read_bytes()
    pos = word = 0
    decoded = []
    while pos < len(stored):
        delta = shift = 0
        while True:
            byte = stored[pos]
            pos += 1
            delta |= (byte & 127) << shift
            shift += 7
            if byte < 128:
                break
        word += delta
        state = stored[pos]
        pos += 1
        decoded.append((word, state))
    assert decoded == events
    cursor = state = 0
    for i, expected in enumerate(styles):
        if cursor < len(decoded) and decoded[cursor][0] == i:
            state = decoded[cursor][1]
            cursor += 1
        assert state == expected
    result = dict(source_sha256=hashlib.sha256(source).hexdigest(), items=len(items), verses=verses, headings=headings, words=len(styles), marked_words=marked, flags=dict(flags), flag_combinations=dict(combinations), style_transition_events=len(events), style_transition_bytes=len(encoded), paragraph_markers_all_at_verse_start=True, style_sidecar_exact_roundtrip=True, plain_verse_text_bytes=len(('\n'.join(plain)+'\n').encode()))
    (args.output / 'formatted-source-results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
