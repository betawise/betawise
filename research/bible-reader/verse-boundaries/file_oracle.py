"""Independent framing/index assertions layered onto the canonical bitmap oracle."""
import json
import struct


def tokens(raw):
    flags=0
    offset=0
    while offset<len(raw):
        code=raw[offset]
        if code in (0xb1,0xb2):
            assert offset+2<len(raw) and raw[offset+2]==code, ('region framing',offset)
            flags=flags|raw[offset+1] if code==0xb1 else flags&~raw[offset+1]
            offset+=3
        elif code==0xb8:
            assert offset+3<len(raw), ('opaque header',offset)
            length=raw[offset+1]
            assert 4<=length<=255 and offset+length<=len(raw), ('opaque length',offset,length)
            assert raw[offset+length-2:offset+length]==bytes([length,code]), ('opaque trailer',offset)
            offset+=length
        else:
            yield offset,code,flags
            offset+=1


def validate_index(raw, expected_verses, semantic):
    count=len(expected_verses)
    index_bytes=6*count+4*((count+31)//32)
    body_end=len(raw)-index_bytes
    assert body_end>=0, 'file too short for its index'
    offset=body_end
    payload=bytearray()
    while offset<len(raw):
        length=raw[offset+1]
        assert raw[offset]==0xb8 and 4<=length<=255
        assert raw[offset+length-2:offset+length]==bytes([length,0xb8])
        payload.extend(raw[offset+2:offset+length-2])
        offset+=length
    assert len(payload)==6*len(expected_verses),'index entry count'
    entries=list(struct.iter_unpack('>HHH',payload))
    previous=0
    for verse,((search,start,end),expected)in enumerate(zip(entries,expected_verses),1):
        assert previous<=search<=start<=end<=body_end, ('index offsets',verse,search,start,end,body_end)
        words,_=semantic(raw[start:end])
        assert ' '.join(word for word,styles in words)==expected, ('indexed verse body',verse)
        previous=end
    return dict(entries=len(entries),payload_bytes=len(payload),record_bytes=len(raw)-body_end,body_bytes=body_end)


def install():
    import bible_rich
    bible_rich.tokens=tokens
    original_render=bible_rich.render_native

    def render(raw, profiles, top_offset, width=252):
        image,lines,top,positions=original_render(raw,profiles,top_offset,width)
        # The trailing records consume encoded offsets but no display cells.
        # Their coordinates are derived from the final source glyph, never pixels.
        final=positions[len(raw)]
        last=max((offset for offset,code,flags in tokens(raw)),default=-1)
        for offset in range(last+1,len(raw)+1):
            positions.setdefault(offset,final)
        return image,lines,top,positions

    bible_rich.render_native=render
    original=bible_rich.verify_rich

    def verify(output, sidebar_reference):
        books=json.loads((output/'source.json').read_text())
        chapters=[chapter for book in books for chapter in book['chapters']]
        checks=json.loads((output/'checks.json').read_text())
        reports=[]
        for index,check in enumerate(checks,1):
            editor=(output/f'editor-{index:02}.bin').read_bytes()
            start,end=struct.unpack_from('>II',editor,40)
            raw=(output/f'chapter-{index:02}.bin').read_bytes()
            raw=raw[:start]+raw[end:]
            reports.append(validate_index(raw,chapters[check['chapter']],bible_rich.semantic))
        (output/'file-index-validation.json').write_text(json.dumps(reports,indent=2)+'\n')
        return original(output,sidebar_reference)

    bible_rich.verify_rich=verify
