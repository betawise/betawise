#!/usr/bin/env python3
"""Local libzstd sizing and exact round-trip comparisons on the pinned corpus."""
import argparse
import ctypes as C
import ctypes.util
import hashlib
import json
from pathlib import Path
import struct


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--levels', type=int, nargs='+', default=[3, 9, 19])
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    z = C.CDLL(ctypes.util.find_library('zstd'))

    def bind(name, restype, *types):
        f = getattr(z, name)
        f.restype, f.argtypes = restype, types
        return f

    sz, ptr, integer = C.c_size_t, C.c_void_p, C.c_int
    bound = bind('ZSTD_compressBound', sz, sz)
    error = bind('ZSTD_isError', C.c_uint, sz)
    error_name = bind('ZSTD_getErrorName', C.c_char_p, sz)
    version = bind('ZSTD_versionString', C.c_char_p)
    compress = bind('ZSTD_compress', sz, ptr, sz, ptr, sz, integer)
    decompress = bind('ZSTD_decompress', sz, ptr, sz, ptr, sz)
    create_c = bind('ZSTD_createCCtx', ptr)
    create_d = bind('ZSTD_createDCtx', ptr)
    free_c = bind('ZSTD_freeCCtx', sz, ptr)
    free_d = bind('ZSTD_freeDCtx', sz, ptr)
    compress_dict = bind('ZSTD_compress_usingDict', sz, ptr, ptr, sz, ptr, sz, ptr, sz, integer)
    decompress_dict = bind('ZSTD_decompress_usingDict', sz, ptr, ptr, sz, ptr, sz, ptr, sz)
    train = bind('ZDICT_trainFromBuffer', sz, ptr, sz, ptr, C.POINTER(sz), C.c_uint)
    dctx_estimate = bind('ZSTD_estimateDCtxSize', sz)
    stream_estimate = bind('ZSTD_estimateDStreamSize_fromFrame', sz, ptr, sz)

    def checked(n):
        if error(n):
            raise RuntimeError(error_name(n).decode())
        return n

    source = args.source.read_bytes()
    books = json.loads(source.decode('utf-8-sig'))
    chapters = [('\n'.join(c) + '\n').encode() for b in books for c in b['chapters']]
    metadata, start = [], 0
    for book in books:
        metadata.append([book['name'], start, len(book['chapters'])])
        start += len(book['chapters'])
    meta = json.dumps(metadata, ensure_ascii=False, separators=(',', ':')).encode()
    raw = b''.join(chapters)
    rows = []
    ctx_c, ctx_d = create_c(), create_d()
    assert ctx_c and ctx_d
    try:
        dictionaries = [(0, b'')]
        sample_sizes = (sz * len(chapters))(*map(len, chapters))
        for capacity in [16384, 65536]:
            buffer = C.create_string_buffer(capacity)
            n = checked(train(buffer, capacity, raw, sample_sizes, len(chapters)))
            dictionary = buffer.raw[:n]
            (args.output / f'dictionary-{capacity}.bin').write_bytes(dictionary)
            dictionaries.append((capacity, dictionary))
        for requested, dictionary in dictionaries:
            for level in args.levels:
                for scope in (['whole', 'chapter'] if not dictionary else ['chapter']):
                    blocks = [raw] if scope == 'whole' else chapters
                    payload, index = bytearray(), bytearray()
                    stream_max = 0
                    for block in blocks:
                        dest = C.create_string_buffer(bound(len(block)))
                        if dictionary:
                            n = checked(compress_dict(ctx_c, dest, len(dest), block, len(block), dictionary, len(dictionary), level))
                        else:
                            n = checked(compress(dest, len(dest), block, len(block), level))
                        encoded = dest.raw[:n]
                        decoded = C.create_string_buffer(len(block))
                        if dictionary:
                            dn = checked(decompress_dict(ctx_d, decoded, len(decoded), encoded, n, dictionary, len(dictionary)))
                        else:
                            dn = checked(decompress(decoded, len(decoded), encoded, n))
                        assert dn == len(block) and decoded.raw[:dn] == block
                        index.extend(struct.pack('>IIII', len(payload), n, len(block), 0))
                        payload.extend(encoded)
                        stream_max = max(stream_max, checked(stream_estimate(encoded, n)))
                    if scope == 'chapter':
                        header = struct.pack('>8s4I', b'KJVZST01', len(meta), len(dictionary), len(chapters), len(raw)).ljust(64, b'\0')
                        image = header + meta + dictionary + index + payload
                    else:
                        image = bytes(payload)
                    name = f'zstd-{level}-{scope}-dict{requested}'
                    (args.output / f'{name}.bin').write_bytes(image)
                    row = dict(level=level, scope=scope, dictionary_bytes=len(dictionary), bytes=len(image), payload_bytes=len(payload), verified_blocks=len(blocks), host_dctx_estimate_bytes=dctx_estimate(), host_max_dstream_estimate_bytes=stream_max, sha256=hashlib.sha256(image).hexdigest())
                    rows.append(row)
                    print(json.dumps(row), flush=True)
                    (args.output / 'zstd-results.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(source).hexdigest(), version=version().decode(), results=rows), indent=2) + '\n')
    finally:
        free_c(ctx_c)
        free_d(ctx_d)


if __name__ == '__main__':
    main()
