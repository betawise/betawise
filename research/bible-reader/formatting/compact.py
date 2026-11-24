#!/usr/bin/env python3
"""Losslessly repack BWF1 research files with sparse chapter lookup/framing."""
import argparse
import json
from pathlib import Path
from measure import read_varint, uvarint


def compact(blob):
    assert blob[:4] == b'BWF1'
    count = int.from_bytes(blob[4:6], 'big')
    width = blob[6]
    header_size = 12 + int.from_bytes(blob[8:10], 'big') + int.from_bytes(blob[10:12], 'big')
    index_end = header_size + (count + 1) * width
    groups = []
    for chapter in range(count):
        begin = int.from_bytes(blob[header_size+chapter*width:header_size+(chapter+1)*width], 'big')
        end = int.from_bytes(blob[header_size+(chapter+1)*width:header_size+(chapter+2)*width], 'big')
        raw = blob[index_end+begin:index_end+end]
        pos = 1
        parts = []
        for field in range(3):
            part = b''
            if raw[0] & (1 << field):
                size, pos = read_varint(raw, pos)
                part = raw[pos:pos+size]
                pos += size
            parts.append(part)
        assert pos == len(raw)
        groups.append(parts)
    global_mask = 0
    for parts in groups:
        global_mask |= sum(bool(part) << field for field,part in enumerate(parts))
    single = global_mask.bit_count() <= 1
    bitmap = bytearray((count+7)//8)
    frames = []
    for chapter, parts in enumerate(groups):
        active = [i for i,part in enumerate(parts) if part]
        if not active:
            continue
        bitmap[chapter//8] |= 1 << (chapter%8)
        frame = bytearray() if single else bytearray([sum(1 << field for field in active)])
        for i,field in enumerate(active):
            if i < len(active)-1:
                frame.extend(uvarint(len(parts[field])))
            frame.extend(parts[field])
        frames.append(bytes(frame))
    offsets = [0]
    for frame in frames:
        offsets.append(offsets[-1]+len(frame))
    new_width = 2 if offsets[-1] < 65536 else 3
    header = bytearray(blob[:header_size])
    header[:4] = b'BWF2'
    header[6] = new_width
    header.append(global_mask)
    index = bytes(bitmap) + b''.join(v.to_bytes(new_width,'big') for v in offsets)
    result = bytes(header) + index + b''.join(frames)
    # Random-seek every chapter, including absent chapters, from actual bytes.
    for chapter in reversed(range(count)):
        if not bitmap[chapter//8] >> (chapter%8) & 1:
            assert not any(groups[chapter])
            continue
        rank = sum(byte.bit_count() for byte in bitmap[:chapter//8]) + (bitmap[chapter//8] & ((1 << (chapter%8))-1)).bit_count()
        table = len(header)+len(bitmap)
        start = int.from_bytes(result[table+rank*new_width:table+(rank+1)*new_width],'big')
        end = int.from_bytes(result[table+(rank+1)*new_width:table+(rank+2)*new_width],'big')
        raw = result[len(header)+len(index)+start:len(header)+len(index)+end]
        mask = global_mask if single else raw[0]
        pos = 0 if single else 1
        active = [i for i in range(3) if mask & (1 << i)]
        decoded = [b'']*3
        for i,field in enumerate(active):
            if i < len(active)-1:
                size,pos=read_varint(raw,pos)
            else:
                size=len(raw)-pos
            decoded[field]=raw[pos:pos+size]
            pos+=size
        assert pos==len(raw) and decoded==groups[chapter]
    return result,dict(bytes=len(result),index_bytes=len(index),present_chapters=len(frames),header_bytes=len(header),framing_bytes=sum(map(len,frames))-sum(len(p)for parts in groups for p in parts))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    results={}
    for path in sorted(args.source.glob('*.bin')):
        raw=path.read_bytes()
        if raw[:4]!=b'BWF1':
            continue
        blob,record=compact(raw)
        record['dense_bytes']=len(raw)
        (args.output/path.name).write_bytes(blob)
        results[path.name]=record
    (args.output/'results.json').write_text(json.dumps(dict(status='passed',variants=results),indent=2))
    print(json.dumps({k:v for k,v in results.items()if k.startswith('kjv-combined')or k.startswith('kjv-headings')},indent=2))


if __name__=='__main__':
    main()
