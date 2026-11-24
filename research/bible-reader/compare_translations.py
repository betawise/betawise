#!/usr/bin/env python3
"""Compare local translation corpora with the refined, chapter-seekable codec.

Only aggregate results belong in the repository; encoded modern translations
and source text stay in the private experiment directory.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
from context_models import (dictionary_letters, decode_letter_dictionary,
    front_word, model_bytes, read_sequences, sequences_bytes, train)

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
TOKEN=re.compile(r" ?[A-Za-z]+(?:['’][A-Za-z]+)*|.",re.S)
FLAGS='plndcgesibr'
STYLE='sibr'
LAYOUT='plndcge'


def packed_json(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()


def front_dictionary(words):
    offsets,data=bytearray(),bytearray();previous=b''
    for i,word in enumerate(words):
        word=word.encode()
        assert b'\0'not in word
        if i%16==0:
            offsets.extend(struct.pack('>I',len(data)));previous=b''
        prefix=0
        while prefix<min(len(word),len(previous))and word[prefix]==previous[prefix]:prefix+=1
        assert prefix<256
        data.append(prefix);data.extend(word[prefix:]+b'\0');previous=word
    return bytes(offsets+data)


def compress_blocks(blocks,metadata,binary,out,label):
    out.mkdir(parents=True,exist_ok=True)
    tokenized=[TOKEN.findall(b.decode())for b in blocks]
    for original,tokens in zip(blocks,tokenized):assert ''.join(tokens).encode()==original
    words=sorted({t for ts in tokenized for t in ts});ids={w:i for i,w in enumerate(words)}
    assert len(words)<65535
    seqs=[[ids[t]for t in ts]for ts in tokenized]
    lexicon=front_dictionary(words)
    for i,w in enumerate(words):assert front_word(lexicon,i,len(words))==w.encode()
    letters=dictionary_letters(lexicon,len(words),out/'dictionary.bin')
    counts,candidates=train(seqs,len(words),1,exclusion=True,max_followers=512)
    model,context_bytes,contexts=model_bytes(counts,candidates,len(words),1,65536,exclusion=True)
    input_path=out/'input.symbols';input_path.write_bytes(sequences_bytes(seqs))
    model_path=out/'model.bin';model_path.write_bytes(model)
    arithmetic_path,decoded_path=out/'encoded.arith',out/'decoded.symbols'
    stats=json.loads(subprocess.check_output([str(binary),str(input_path),str(model_path),str(arithmetic_path),str(decoded_path)],text=True))
    assert decoded_path.read_bytes()==input_path.read_bytes()
    meta=packed_json(metadata);letter_blob=(out/'dictionary.bin').read_bytes();codec=arithmetic_path.read_bytes()
    image=struct.pack('>8s8I',b'KJVCTX02',len(meta),len(words),len(letter_blob),0,1,len(codec),sum(map(len,blocks)),len(blocks)).ljust(64,b'\0')+meta+letter_blob+codec
    path=out/'container.bin';path.write_bytes(image)
    # Verify from serialized resource bytes, independently of encoder objects.
    saved=path.read_bytes();_,ms,terminal_count,ls,ng,kind,cs,raw_size,nc=struct.unpack_from('>8s8I',saved)
    assert json.loads(saved[64:64+ms])==metadata and ng==0 and kind==1
    restored_lexicon=decode_letter_dictionary(saved[64+ms:64+ms+ls])
    restored_words=[front_word(restored_lexicon,i,terminal_count)for i in range(terminal_count)]
    stored_codec=saved[64+ms+ls:];assert len(stored_codec)==cs
    arithmetic_path.write_bytes(stored_codec)
    subprocess.run([str(binary),'--decode',str(arithmetic_path),str(decoded_path)],check=True)
    restored=read_sequences(decoded_path.read_bytes());assert len(restored)==nc==len(blocks)
    for i in reversed(range(nc)):assert b''.join(restored_words[s]for s in restored[i])==blocks[i],i
    result=dict(label=label,raw_bytes=sum(map(len,blocks)),bytes=len(saved),dictionary_bytes=len(letter_blob),model_bytes=len(model),context_bytes=context_bytes,contexts=contexts,payload_bytes=stats['payload_bytes'],framing_bytes=len(saved)-len(codec)-len(letter_blob)+16+16*nc,chapter_blocks=nc,tokens=sum(map(len,seqs)),dictionary_entries=terminal_count,max_token_utf8_bytes=max(len(w.encode())for w in words),dictionary_max_raw_block_bytes=letters['max_raw_block_bytes'],all_blocks_roundtrip_exact=True,sha256=hashlib.sha256(saved).hexdigest())
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    return result


def source_corpus(repo,version,book_records,canonical_counts):
    path=repo/'data'/version/(version+'.json')
    note_path=repo/'data'/version/(version+'-footnotes.json')
    rows=json.loads(path.read_bytes());notes=json.loads(note_path.read_bytes())
    baseline_counts=canonical_counts;canonical_counts=dict(canonical_counts)
    for row in rows:
        if 'h'in row:continue
        _,book,ch,v=row['r'].split(':');key=(book,int(ch))
        assert key in canonical_counts and int(v)>0
        canonical_counts[key]=max(canonical_counts[key],int(v))
    names=[b['book']for b in book_records]
    chapter_keys=[(b['book'],c)for b in book_records for c in range(1,b['numChapters']+1)]
    assert len(chapter_keys)==1189
    chapter_ids={key:i for i,key in enumerate(chapter_keys)}
    by_verse=defaultdict(list);headers=defaultdict(list);by_note=defaultdict(list)
    flag_counts=Counter();order_ids=set();paragraph_default=True
    for row in rows:
        assert set(row)<=set(['o','r','t','h']) and row['o']not in order_ids
        order_ids.add(row['o']);translation,book,chapter,verse=row['r'].split(':')
        assert translation==version and book in names
        key=(book,int(chapter));assert key in chapter_ids
        if 'h'in row:headers[key].append(row);continue
        assert 1<=int(verse)<=canonical_counts[key]
        plain=re.sub(r'\*[a-z]+','',row['t']);assert '*'not in plain and '\n'not in plain and '\0'not in plain
        masks=[]
        for token in row['t'].split():
            matches=re.findall(r'\*([a-z]+)',token);assert len(matches)<=1
            flags=''.join(matches);assert set(flags)<=set(FLAGS)
            flag_counts.update(flags);masks.append(sum(1<<FLAGS.index(c)for c in set(flags)))
        assert len(masks)==len(plain.split())
        if not masks or [i for i,m in enumerate(masks)if m&1]!=[0]:paragraph_default=False
        by_verse[key+(int(verse),)].append((row['o'],plain,masks))
    for note in notes:
        translation,book,chapter,verse=note['r'].split(':');assert translation==version
        key=(book,int(chapter));assert key in chapter_ids and note['o']in order_ids
        by_note[key].append(note)
    metadata=[];start=0
    for book in book_records:
        metadata.append([book['book'],start,book['numChapters']]);start+=book['numChapters']
    blocks,format_blocks,full_blocks=[],[],[]
    omitted=split=0;events_total=parts_total=0;omitted_refs=[]
    for key in chapter_keys:
        verses=[];parts=[];masks=[];verse_word_starts=[]
        for verse in range(1,canonical_counts[key]+1):
            records=by_verse.get(key+(verse,),[])
            if not records:omitted+=1;omitted_refs.append([key[0],key[1],verse])
            if len(records)>1:split+=1
            pieces=[];byte_offset=0;verse_word_starts.append(len(masks))
            for o,plain,flags in records:
                # Preserve source part boundaries/IDs for heading and note anchors.
                parts.append([o,verse,byte_offset,len(plain.encode()),len(flags)])
                byte_offset+=len(plain.encode())+1;pieces.append(plain);masks.extend(flags)
            verses.append(' '.join(pieces))
        blocks.append(('\n'.join(verses)+'\n').encode())
        # Word styles persist between events; layout flags apply at the event
        # word only. The paragraph default is included only when source-proven.
        state=previous=0;events=[]
        for word,mask in enumerate(masks):
            if paragraph_default:mask&=~1
            style=sum((1<<i)for i,c in enumerate(STYLE)if mask&(1<<FLAGS.index(c)))
            layout=sum((1<<i)for i,c in enumerate(LAYOUT)if mask&(1<<FLAGS.index(c)))
            if style!=state or layout:
                events.append([word-previous,style|(layout<<4)]);previous=word;state=style
        # Independently replay the semantic word flags, including defaults.
        decoded_events=[];word=0
        for delta,mask in events:word+=delta;decoded_events.append((word,mask))
        cursor=state=0;defaults=set(verse_word_starts)
        for word,expected in enumerate(masks):
            layout=0
            if cursor<len(decoded_events)and decoded_events[cursor][0]==word:
                value=decoded_events[cursor][1];state=value&15;layout=value>>4;cursor+=1
            restored=sum(1<<FLAGS.index(c)for i,c in enumerate(STYLE)if state&(1<<i))
            restored|=sum(1<<FLAGS.index(c)for i,c in enumerate(LAYOUT)if layout&(1<<i))
            if paragraph_default and word in defaults:restored|=1
            assert restored==expected,(version,key,word)
        formatting={'p':paragraph_default,'f':events,'h':headers[key],'parts':parts}
        full={**formatting,'notes':by_note[key]}
        format_blocks.append(packed_json(formatting));full_blocks.append(packed_json(full))
        assert json.loads(full_blocks[-1])==full
        events_total+=len(events);parts_total+=len(parts)
    for key,records in by_verse.items():
        i=chapter_ids[key[:2]];verse=key[2];expected=' '.join(r[1]for r in records)
        assert blocks[i].decode().split('\n')[verse-1]==expected
    hashes={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [path,note_path]}
    stats=dict(version=version,source_hashes=hashes,verse_records=parts_total,unique_present_verses=len(by_verse),verse_slots=sum(canonical_counts.values()),omitted_verse_slots=omitted,omitted_references=omitted_refs,extended_chapters=[[book,ch,n]for (book,ch),n in canonical_counts.items()if n!=baseline_counts[book,ch]],split_verses=split,headings=sum(map(len,headers.values())),annotation_records=len(notes),notes_with_text=sum(bool(n.get('t'))for n in notes),records_with_cross_references=sum(bool(n.get('c'))for n in notes),flag_counts=dict(flag_counts),format_events=events_total,paragraph_default=paragraph_default,semantic_format_roundtrip_exact=True)
    return blocks,format_blocks,full_blocks,metadata,stats


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo',type=Path,default=ROOT/'betawise/applets/BibleWise/upstream')
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--legacy',type=Path,default=ROOT/'.research-work/bible-compression/kjv.json')
    ap.add_argument('--resume',action='store_true',help='retain completed corpus results after a source-validation failure')
    args=ap.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=args.resume)
    prior=json.loads((out/'results.json').read_text())if args.resume and(out/'results.json').exists()else{}
    revision=subprocess.check_output(['git','-C',str(args.repo),'rev-parse','HEAD'],text=True).strip()
    assert revision=='93ff30bbb530c53cd2ab26e42ee555d3938ded14'
    books=json.loads((args.repo/'data/books.json').read_bytes())
    kjv_rows=json.loads((args.repo/'data/kjv/kjv.json').read_bytes());counts={}
    for row in kjv_rows:
        if'h'in row:continue
        _,book,ch,v=row['r'].split(':');key=(book,int(ch));counts[key]=max(counts.get(key,0),int(v))
    assert len(counts)==1189 and sum(counts.values())==31102
    binary=out/'context-codec'
    subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra',str(HERE/'context_codec.cpp'),'-o',str(binary)],check=True)
    results=prior.get('translations',[])
    legacy=json.loads(args.legacy.read_text(encoding='utf-8-sig'));meta=[];start=0
    for book in legacy:meta.append([book['name'],start,len(book['chapters'])]);start+=len(book['chapters'])
    control=prior.get('legacy_control')or compress_blocks([('\n'.join(c)+'\n').encode()for b in legacy for c in b['chapters']],meta,binary,out/'legacy','KJV original MAME corpus')
    assert control['bytes']==948662 and control['sha256']=='7d58ee4d28a80d530e1a1ca4c510cb55801ac387ba62927278ba4ab515a01c1c'
    for version in ['kjv','nkjv','esv']:
        text,formatting,full,metadata,stats=source_corpus(args.repo,version,books,counts)
        if any(r['version']==version for r in results):
            previous=next(r for r in results if r['version']==version)
            assert previous['source_hashes']==stats['source_hashes']
            previous.update({k:v for k,v in stats.items()if k not in previous})
            continue
        print('SOURCE '+json.dumps(stats),flush=True)
        text_result=compress_blocks(text,metadata,binary,out/version/'text',version+' verse text')
        format_result=compress_blocks(formatting,metadata,binary,out/version/'format',version+' formatting/headings/anchors')
        full_result=compress_blocks(full,metadata,binary,out/version/'annotations',version+' formatting/headings/anchors/notes')
        version_counts=dict(counts)
        for book,ch,n in stats['extended_chapters']:version_counts[book,ch]=n
        checkpoints=16+4*len(counts)+18*sum((n-1)//8 for n in version_counts.values())
        row=dict(**stats,text=text_result,formatting=format_result,annotations=full_result,text_plus_format_bytes=text_result['bytes']+format_result['bytes'],text_plus_all_annotations_bytes=text_result['bytes']+full_result['bytes'],eight_verse_seek_index_bytes=checkpoints)
        results.append(row)
        (out/'results.json').write_text(json.dumps(dict(upstream_revision=revision,codec=dict(context_budget=65536,max_followers=512,exclusion=True,independent_chapters=True),legacy_control=control,translations=results),indent=2)+'\n')
    print('PASS all translations, annotations and formatting round-tripped',flush=True)


if __name__=='__main__':main()
