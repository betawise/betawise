#!/usr/bin/env python3
"""Trade letter-Huffman compression for direct-ROM front dictionary access."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from context_models import decode_letter_dictionary,front_word

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('source',type=Path);ap.add_argument('output',type=Path)
args=ap.parse_args();image=args.source.read_bytes()
assert image[:8]==b'KJVHUF01'
m,d,ls=struct.unpack_from('>III',image,8);start=64+m
lex=decode_letter_dictionary(image[start:start+ls])
for i in range(d):front_word(lex,i,d).decode('ascii')
header=bytearray(image[:64]);header[:8]=b'KJVHUF02';struct.pack_into('>I',header,16,len(lex))
result=bytes(header)+image[64:start]+lex+image[start+ls:]
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(result)
stats=dict(bytes=len(result),dictionary_bytes=len(lex),dictionary_increase=len(lex)-ls,sha256=hashlib.sha256(result).hexdigest())
args.output.with_suffix('.json').write_text(json.dumps(stats,indent=2)+'\n');print(json.dumps(stats))
