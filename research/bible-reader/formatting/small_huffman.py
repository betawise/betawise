#!/usr/bin/env python3
"""Compact canonical Huffman tables without the production 1-KiB fast lookup."""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct
from measure import Bits, read_formatting, singleton_runs, heading_chunks, bundle, uvarint, read_varint
from compress_text import huffman_lengths, pack_symbols
from compact import compact
from word_defaults import book_predictions


def model(chunks):
    counts = Counter(byte for chunk in chunks for byte in chunk)
    lengths = huffman_lengths(counts)
    ordered = sorted(lengths, key=lambda symbol: (lengths[symbol], symbol))
    maximum = max(lengths.values())
    histogram = [sum(lengths[symbol] == length for symbol in ordered) for length in range(1, maximum + 1)]
    raw = bytes([maximum]) + struct.pack('>' + 'H' * maximum, *histogram) + bytes(ordered)
    codes = {}
    code = previous = 0
    for symbol in ordered:
        length = lengths[symbol]
        code <<= length - previous
        codes[symbol] = (code, length)
        code += 1
        previous = length
    return raw, codes


def decode(blob, model_bytes, count):
    maximum = model_bytes[0]
    counts = struct.unpack_from('>' + 'H' * maximum, model_bytes, 1)
    symbols = model_bytes[1 + 2 * maximum:]
    assert len(symbols) == sum(counts)
    reader = Bits(blob)
    out = bytearray()
    for _ in range(count):
        code = first = index = 0
        for n in counts:
            code = (code << 1) | reader.get(1)
            if 0 <= code - first < n:
                out.append(symbols[index + code - first])
                break
            index += n
            first = (first + n) << 1
        else:
            raise ValueError('invalid code')
    return bytes(out)


def compress(chunks):
    table, codes = model(chunks)
    encoded = []
    for raw in chunks:
        if not raw:
            encoded.append(b'')
            continue
        payload = pack_symbols(raw, codes)
        assert decode(payload, table, len(raw)) == raw
        encoded.append(uvarint(len(raw)) + payload)
    return table, encoded


def heading_pool(header, block_size=16):
    count, offset = read_varint(header, 0)
    blocks = (count + block_size - 1) // block_size
    offsets = list(struct.unpack_from('>' + 'I' * blocks, header, offset))
    start = offset + 4 * blocks
    offsets.append(len(header) - start)
    chunks = [header[start + a:start + b] for a,b in zip(offsets, offsets[1:])]
    table, encoded = compress(chunks)
    positions = [0]
    for block in encoded:
        positions.append(positions[-1] + len(block))
    result = uvarint(count) + uvarint(len(table)) + table + bytes([2])
    result += b''.join(p.to_bytes(2,'big') for p in positions) + b''.join(encoded)
    # Recover every front-dictionary block independently, including padding.
    for raw, packed in zip(chunks, encoded):
        size, pos = read_varint(packed, 0)
        assert decode(packed[pos:], table, size) == raw
    return result, dict(model_bytes=len(table), blocks=blocks, dictionary_bytes=len(result), original_dictionary_bytes=len(header))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',default='kjv')
    parser.add_argument('--layouts',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    data=read_formatting(args.version)
    layouts=[b'']*len(data['atoms'])
    layout_header=b''
    layout_bytes=0
    if args.layouts:
        from combine import layout_parts
        options=json.loads((args.layouts/'results.json').read_text())['versions'][args.version]
        name=options['best'].replace('/','-')
        blob=(args.layouts/f'{args.version}-{name}.bin').read_bytes()
        layout_header,layouts=layout_parts(blob)
        layout_bytes=len(blob)
    prediction, residual=book_predictions(data)
    head_header,heads=heading_chunks(data['headings'],'front_pool')
    small_heads,head_stats=heading_pool(head_header)
    # Reuse the actual standalone indexed heading records from heading_chunks.
    raw,_=bundle(data,b'',[b'']*len(heads),small_heads,heads,layout_override=[b'']*len(heads))
    head_blob,head_sizes=compact(raw)
    (args.output/'headings.bin').write_bytes(head_blob)
    result=dict(status='passed',version=args.version,layout_file_bytes=layout_bytes,heading_huffman=head_stats,heading_file=head_sizes,variants={})
    components={}
    for name,projection in [('italics',1),('bold',2),('smallcaps',4),('redletter',8)]:
        header,chunks=singleton_runs(data['atoms'],projection)
        if not any(chunks):
            components[name]=dict(present=False,bytes=0)
            continue
        table,encoded=compress(chunks)
        sizes=[]
        for extra,payload in [(b'',chunks),(table,encoded)]:
            raw,_=bundle(data,header+extra,payload,layout_override=[b'']*len(payload))
            blob,_=compact(raw)
            sizes.append(len(blob))
        components[name]=dict(present=True,run_bytes=sizes[0],compact_huffman_bytes=sizes[1])
    result['isolated_style_components']=components
    for name,projection in [('typography',7),('all_styles',15)]:
        style_header,styles=singleton_runs(residual,projection)
        table,encoded=compress(styles)
        for codec,extra,chunks in [('runs',b'',styles),('runs_huffman',table,encoded)]:
            full_header=prediction+style_header+extra
            raw,_=bundle(data,full_header,chunks,layout_override=[b'']*len(chunks))
            style_blob,stats=compact(raw)
            raw,_=bundle(data,full_header+layout_header,chunks,small_heads,heads,layout_override=layouts)
            combined,combined_stats=compact(raw)
            record=dict(style_bytes=len(style_blob),separate_total=len(style_blob)+len(head_blob)+layout_bytes,combined_bytes=len(combined),style_huffman_table_bytes=len(extra),**stats)
            result['variants'][name+'/'+codec]=record
            (args.output/f'{name}-{codec}.bin').write_bytes(combined)
    (args.output/'results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
