#!/usr/bin/env python3
"""Generate table-free C converters from the shared private charset descriptor."""
import argparse
from pathlib import Path
from smallcaps import load, tables


def generate(descriptor):
    lookup = tables(descriptor)
    # Keep the formula and explicit descriptor in lockstep, including aliases
    # and unsupported input. This verifies all bytes, not selected examples.
    from smallcaps import encode, decode
    for style_index, style in enumerate(descriptor['styles']):
        for source in range(256):
            index = lookup['source_to_index'][source]
            expected = None if index == 255 else lookup['variants'][index][style_index]
            if encode(source, style) != expected:
                raise ValueError(f'formula/descriptor mismatch for {source:02X} {style}')
    for slot in range(256):
        if decode(slot) != (lookup['decode'][slot] or None):
            raise ValueError(f'decode formula/descriptor mismatch at {slot:02X}')
    return Path(__file__).with_name('smallcaps_codec.h.in').read_text()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--charset',type=Path,default=Path(__file__).with_name('neo-smallcaps.json'))
    parser.add_argument('--output',type=Path,default=Path(__file__).with_name('neo-smallcaps.h'))
    parser.add_argument('--check',action='store_true')
    args = parser.parse_args()
    text = generate(load(args.charset))
    if args.check:
        if not args.output.exists() or args.output.read_text() != text:
            raise SystemExit(f'stale generated charset: {args.output}')
    else:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text)
    print(args.output)


if __name__=='__main__':main()
