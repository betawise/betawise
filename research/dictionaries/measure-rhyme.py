#!/usr/bin/env python3
"""Measure a streaming flash-index layout, not a production rhyming dictionary.

The local PocketSphinx dictionary lacks stress. Last-vowel grouping below is
ONLY a storage/phoneme demonstration; it is unsuitable for perfect rhyme in
general. Production keys must retain the final stressed vowel and its tail.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

VOWELS=set('AA AE AH AO AW AY EH ER EY IH IY OW OY UH UW AX AXR'.split())

def varint(n):
    assert n>=0
    b=bytearray()
    while n>=128:
        b.append((n&127)|128);n>>=7
    b.append(n);return b

def rhyme_key(phones):
    # Stress-bearing inputs: choose the last vowel carrying primary/secondary
    # stress, preserving all following phones but ignoring stress in the key.
    stressed=[i for i,p in enumerate(phones) if p[-1:] in ['1','2'] and p[:-1] in VOWELS]
    if not stressed:
        return None
    return tuple(re.sub('[012]$','',p) for p in phones[stressed[-1]:])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    p.add_argument('--source',type=Path,default=Path('/usr/share/pocketsphinx/model/en-us/cmudict-en-us.dict'))
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    raw=a.source.read_bytes();rows=raw.decode('utf-8').splitlines()
    pronunciations=defaultdict(set);allphones=set()
    for row in rows:
        fields=row.split()
        if len(fields)<2 or row.startswith('#'):continue
        word=re.sub(r'\(\d+\)$','',fields[0]).lower()
        word.encode('ascii')  # Fail rather than silently alter target spellings.
        phones=tuple(fields[1:]);pronunciations[word].add(phones);allphones.update(phones)
    assert not any(re.search('[012]$',p) for p in allphones),'this measurement expects the explicitly stressless local corpus'
    words=sorted(pronunciations);word_ids={w:i for i,w in enumerate(words)}
    keys=defaultdict(set);word_keys=defaultdict(set)
    for word,variants in pronunciations.items():
        for phones in variants:
            vowels=[i for i,p in enumerate(phones) if p in VOWELS]
            if not vowels:continue
            key=phones[vowels[-1]:];keys[key].add(word_ids[word]);word_keys[word].add(key)
    key_ids={k:i for i,k in enumerate(sorted(keys))}
    assert len(words)<1<<24 and len(keys)<1<<16 and len(allphones)<256
    strings=bytearray();block_offsets=bytearray();lookup=bytearray();lookup_offsets=bytearray()
    previous=b''
    for i,w in enumerate(words):
        b=w.encode('ascii')
        if i%16==0:
            block_offsets+=len(strings).to_bytes(3,'big');lookup_offsets+=len(lookup).to_bytes(3,'big');strings+=b+b'\0'
        else:
            n=0
            while n<min(len(b),len(previous)) and b[n]==previous[n]:n+=1
            assert n<256;strings+=bytes([n])+b[n:]+b'\0'
        previous=b
        refs=sorted(key_ids[k] for k in word_keys[w]);assert len(refs)<256
        lookup.append(len(refs))
        for r in refs:lookup+=r.to_bytes(2,'big')
    postings=bytearray();directory=bytearray();keybytes=bytearray();phone_ids={v:i for i,v in enumerate(sorted(allphones))}
    for key in sorted(keys):
        ids=sorted(keys[key]);directory+=len(postings).to_bytes(3,'big')+len(ids).to_bytes(3,'big')
        last=0
        for i in ids:postings+=varint(i-last);last=i
        keybytes+=bytes([len(key)])+bytes(phone_ids[v] for v in key)
    components={'header':bytes(64),'word_blocks':strings,'word_directory':block_offsets,
                'word_key_refs':lookup,'word_key_directory':lookup_offsets,
                'rhyme_directory':directory,'rhyme_keys':keybytes,'postings':postings}
    for name,data in components.items():(a.output/(name+'.bin')).write_bytes(data)
    def share(a,b):return bool(word_keys[a]&word_keys[b])
    for pair in [('cat','bat'),('rough','tough'),('though','dough'),('through','blue')]:assert share(*pair),pair
    for pair in [('rough','through'),('love','move')]:assert not share(*pair),pair
    # Independent stress fixtures distinguish a rhyme from matching spelling
    # and show why the measured stressless corpus is insufficient.
    fixture={'station':'S T EY1 SH AH0 N','nation':'N EY1 SH AH0 N','pigeon':'P IH1 JH AH0 N'}
    assert rhyme_key(fixture['station'].split())==rhyme_key(fixture['nation'].split())
    assert rhyme_key(fixture['station'].split())!=rhyme_key(fixture['pigeon'].split())
    assert share('station','pigeon'),'retain the known false positive as a limitation demonstration'
    result={'source':str(a.source),'source_sha256':hashlib.sha256(raw).hexdigest(),'source_bytes':len(raw),
            'pronunciation_rows':len(rows),'unique_words':len(words),'phone_symbols':len(allphones),
            'last_vowel_keys':len(keys),'stress_available':False,'production_rhyme_accuracy_qualified':False,
            'components':{k:len(v)for k,v in components.items()},'total_bytes':sum(map(len,components.values())),
            'examples':{w:[list(x)for x in sorted(pronunciations[w])]for w in ['rough','tough','through','blue','love','move']},
            'known_false_positive':['station','pigeon'],
            'scope':'storage baseline only; production must use a stress-preserving source and remeasure'}
    (a.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
