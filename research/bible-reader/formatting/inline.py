#!/usr/bin/env python3
"""Measure in-stream style changes with the existing phrase-Huffman/index code."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from measure import APP, ROOT, read_formatting, style_events
from compress_text import build_container
from build_index import build_index, grammar_summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='kjv')
    parser.add_argument('--layout-mode', choices=['sidecar','inline'], default='sidecar')
    parser.add_argument('--layout-defaults', choices=['translation','book','chapter'], default='translation')
    parser.add_argument('--word-defaults', choices=['none','book','learned'], default='none')
    parser.add_argument('--projection', choices=['typography','all_styles'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    data = read_formatting(args.version)
    projection = 7 if args.projection == 'typography' else 15
    prediction_header = b''
    atoms = data['atoms']
    if args.word_defaults == 'book':
        from word_defaults import book_predictions
        prediction_header, atoms = book_predictions(data)
    elif args.word_defaults == 'learned':
        from learned import predictions
        prediction_header, atoms, _ = predictions(data, 'book', 32)
    events = style_events(atoms, projection)
    layout_header = b''
    layouts = [[] for _ in atoms]
    if args.layout_mode == 'inline':
        from layout import profiles
        layout_header, layouts = profiles(data, args.layout_defaults)
    blocks = []
    inserted = 0
    for chapter_atoms, original, changes, layout_events in zip(data['atoms'], data['blocks'], events, layouts):
        markers = {}
        for atom, state in changes:
            position = chapter_atoms[atom]['byte']
            markers.setdefault(position, bytearray()).append(0x10 | state)
        for atom, mask in layout_events:
            position = chapter_atoms[atom]['byte']
            markers.setdefault(position, bytearray()).extend([2, 0x10 | (mask >> 4), 0x10 | (mask & 15)])
        output = bytearray()
        previous = 0
        for position, marker in sorted(markers.items()):
            output.extend(original[previous:position])
            output.extend(marker)
            inserted += len(marker)
            previous = position
        output.extend(original[previous:])
        assert bytes(c for c in output if c >= 32 or c == 10) == original
        assert re.findall(rb"[A-Za-z]+(?:'[A-Za-z]+)*", output.lower()) == re.findall(rb"[A-Za-z]+(?:'[A-Za-z]+)*", original.lower())
        blocks.append(bytes(output))
    source = APP/'build/data'/args.version
    original_image = (source/'container.bin').read_bytes()
    metadata_length = int.from_bytes(original_image[8:12], 'big')
    metadata = json.loads(original_image[64:64+metadata_length])
    image, dictionary = build_container(blocks, metadata)
    index, vocabulary_size = build_index(blocks, dictionary)
    pruning = grammar_summaries(dictionary, image)
    for name, blob in [('container.bin',image),('search.bin',index),('pruning.bin',pruning)]:
        (args.output/name).write_bytes(blob)
    (args.output/'prediction-header.bin').write_bytes(prediction_header)
    (args.output/'layout-defaults.bin').write_bytes(layout_header)
    result = dict(version=args.version, layout_mode=args.layout_mode, layout_defaults=args.layout_defaults, layout_default_bytes=len(layout_header), layout_events=sum(map(len,layouts)), projection=args.projection, word_defaults=args.word_defaults, prediction_bytes=len(prediction_header), source_sha256=data['source_sha256'],
        controls_inserted=inserted, container_bytes=len(image),
        container_delta=len(image)-len(original_image), search_bytes=len(index),
        search_delta=len(index)-(source/'search.bin').stat().st_size,
        pruning_bytes=len(pruning), vocabulary_size=vocabulary_size,
        bytecode_and_word_sequence_roundtrip=True,
        combined_delta=len(image)+len(index)+len(pruning)+len(prediction_header)+len(layout_header)-sum((source/n).stat().st_size for n in ['container.bin','search.bin','pruning.bin']))
    print(json.dumps(result),flush=True)
    # Use the production C search against the original unformatted source oracle.
    sys.path.insert(0,str(ROOT/'betawise/tests/biblewise'))
    from check import check_search
    corpus=json.loads((source/'source.json').read_text())
    chapters=[chapter for book in corpus for chapter in book['chapters']]
    result['production_search_cases']=check_search(args.output,args.output,chapters)
    result['status']='passed'
    result['container_sha256']=hashlib.sha256(image).hexdigest()
    (args.output/'results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)


if __name__ == '__main__':
    main()
