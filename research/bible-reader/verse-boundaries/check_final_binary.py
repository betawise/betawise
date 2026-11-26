#!/usr/bin/env python3
"""Exhaustively compare production binary anchors with a full linear parse."""
from pathlib import Path
import json,struct,subprocess
root=Path(__file__).resolve().parents[3];folder=root/'research/bible-reader/verse-boundaries/build';header=root/'applets/BibleWise/ChapterPositions.h'
c='''#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#define VERSE_FONT_BEGIN 0xb1
#define VERSE_FONT_END 0xb2
#define VERSE_FONT_FACE_FLAGS 12
#define NATIVE_WRAP_SPACE 0x81
#define READER_FILE 1
#define ReaderProbeSet(a,b) ((void)0)
static unsigned g_chapter_file_bytes,g_verse_count;
static struct {unsigned gap_start;} g_editor;
static uint8_t data[65536];
static void* FileBindState(unsigned a,void*b,void*c,void*d,void*e){return data;}
'''+ '#include "'+str(header)+'"\n'+'''
int main(int argc,char**argv){
 FILE*f=fopen(argv[1],"rb");assert(f);g_chapter_file_bytes=fread(data,1,sizeof(data),f);fclose(f);
 g_verse_count=atoi(argv[2]);g_editor.gap_start=g_chapter_file_bytes;
 for(unsigned mode=0;mode<2;++mode) for(unsigned t=mode?0:1;t<(mode?g_chapter_file_bytes:g_verse_count+1);++t){
  unsigned want=ParseBoundary(1,t,mode,0,data),limit=g_cached_verse_limit;VerseBounds bounds=g_cached_bounds;
  unsigned got=ReconstructBinaryBoundary(t,mode);
  if(got!=want || limit!=g_cached_verse_limit || bounds.search!=g_cached_bounds.search || bounds.start!=g_cached_bounds.start || bounds.end!=g_cached_bounds.end){
   fprintf(stderr,"mode%u target%u verse%u/%u bounds %u %u %u / %u %u %u limit%u/%u\\n",mode,t,want,got,bounds.search,bounds.start,bounds.end,g_cached_bounds.search,g_cached_bounds.start,g_cached_bounds.end,limit,g_cached_verse_limit);return 1;
  }
 }
 puts("PASS all byte positions and verse numbers");
}
'''
source=folder/'test-production-binary.c';source.write_text(c);binary=folder/'test-production-binary'
subprocess.run(['cc','-O2','-std=c99',str(source),'-o',str(binary)],check=True)
seen=set()
for directory in ('final-binary-reader','final-binary-interactions','final-binary-usage'):
 p=folder/directory
 if not(p/'checks.json').exists():continue
 checks=json.loads((p/'checks.json').read_text());books=json.loads((p/'source.json').read_text());chapters=[chapter for book in books for chapter in book['chapters']]
 for i,check in enumerate(checks,1):
  editor=p/f'editor-{i:02}.bin';chapter=p/f'chapter-{i:02}.bin'
  if not editor.exists() or not chapter.exists() or check.get('mode'):continue
  raw=chapter.read_bytes();a,b=struct.unpack_from('>II',editor.read_bytes(),40);raw=raw[:a]+raw[b:];key=(check['chapter'],raw)
  if key in seen:continue
  seen.add(key);tmp=folder/'binary-input.bin';tmp.write_bytes(raw)
  r=subprocess.run([str(binary),str(tmp),str(len(chapters[check['chapter']]))],capture_output=True,text=True)
  assert not r.returncode,(directory,i,check['name'],r.stderr)
 print(directory,'validated',len(seen),'unique chapter/settings combinations',flush=True)
