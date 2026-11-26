#!/usr/bin/env python3
"""Exercise the actual C formatter/writer against every generated capacity bound."""
from pathlib import Path
import argparse
import json
import re
import struct
import subprocess
from prepare import prepare, HERE, ROOT, APP, BUILD


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--version',choices=('KJV','NKJV'),required=True);p.add_argument('--production',action='store_true');a=p.parse_args()
    app=ROOT/'applets/BibleWise' if a.production else BUILD/'direct-decode/app'
    source=(app/'BibleWise.c').read_text()
    helper=source[source.index('static int BufferVerseNumber(') if a.production else source.index('static int BufferChapterByte('):source.index('static unsigned VerseTextOffset(')]
    writer=source[source.index('typedef struct {\n    uint8_t* bytes;'):source.index('static int DecodeChapterToFile(')]
    constants='\n'.join(line for line in source.splitlines()if re.match(r'^#define (?:READER|VERSE|NATIVE)_\w+ (?!\()',line) and not 'Message_e' in line)
    prefix='''#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "Formatting.h"
#include "charsets/neo-smallcaps.h"
typedef struct { unsigned max_width; const uint8_t* width_table; } FontHeader_t;
static FontHeader_t fonts[4],g_verse_font;
static FontHeader_t* g_body_fonts[4]={fonts,fonts+1,fonts+2,fonts+3};
static bool g_rich_typography;
static unsigned g_verse_count;
static struct {bool verse_numbers,italics,headings;}g_settings={true,true,true};
static unsigned GlyphWidth(FontHeader_t*font,unsigned c){return font->width_table?font->width_table[c]:font->max_width;}
static unsigned HeadingRegionFlags(void){return g_settings.headings?2:1;}
'''
    main_c=r'''
static uint8_t* load(const char* directory,const char*name,unsigned*length){
 char path[4096];snprintf(path,sizeof(path),"%s/%s",directory,name);FILE*f=fopen(path,"rb");assert(f);
 fseek(f,0,SEEK_END);*length=ftell(f);rewind(f);uint8_t*p=malloc(*length);assert(p);assert(fread(p,1,*length,f)==*length);fclose(f);return p;
}
int main(int argc,char**argv){
 assert(argc==2);unsigned size,n;BibleFormatAssets assets;
 assets.bible=load(argv[1],"container.bin",&size);assets.bible_size=size;
 assets.styles=load(argv[1],"styles.bin",&n);assets.layouts=load(argv[1],"layouts.bin",&n);
 uint8_t*index=load(argv[1],"search.bin",&n);assets.vocabulary_size=ReadBigEndian16(index+8);assets.normalization=index+20+4*(assets.vocabulary_size+1);
 uint8_t*verses=load(argv[1],"verses.bin",&n);
 const uint8_t*records=assets.bible+64+ReadBigEndian32(assets.bible+8)+ReadBigEndian32(assets.bible+16)+ReadBigEndian32(assets.bible+20)+4*ReadBigEndian32(assets.bible+32);
 uint8_t widths[256],output[66000];unsigned calls=0,maximum=0,minimum_margin=65535;
 /* Zero and one pixel spaces exercise maximal padding; 255 exercises no padding.
  * Rich/plain typography and both italic preferences exercise all face variants. */
 unsigned trials[4][2]={{0,0},{1,0},{1,6},{255,255}};
 for(unsigned trial=0;trial<4;++trial){
  memset(widths,trials[trial][1],sizeof(widths));widths[' ']=trials[trial][0];
  for(unsigned i=0;i<4;++i){fonts[i].width_table=widths;fonts[i].max_width=trials[trial][1];}g_verse_font=fonts[0];
  for(unsigned rich=0;rich<2;++rich)for(unsigned italic=0;italic<2;++italic){
   g_rich_typography=rich;g_settings.italics=italic;
   for(unsigned chapter=0,book=0;chapter<1189;++chapter){
    while(book<65 && g_books[book+1].first<=chapter)++book;
    unsigned bound=ReadBigEndian16(records+16*chapter+12);g_verse_count=ReadBigEndian16(verses+2*chapter);
    memset(output,0xcc,sizeof(output));ChapterOutput out={0};out.bytes=output;out.capacity=bound;out.verse=out.first_atom=out.line_start=1;
    if(!BibleFormatChapter(&assets,chapter,book,WriteChapterEvent,&out)||!FlushAlignedLine(&out)||out.verse!=g_verse_count+1){
     fprintf(stderr,"underbound/error chapter=%u trial=%u rich=%u italic=%u written=%u bound=%u\n",chapter,trial,rich,italic,out.written,bound);return 1;
    }
    assert(out.written<=bound);for(unsigned j=bound;j<bound+16;++j)assert(output[j]==0xcc);
    if(out.written>maximum)maximum=out.written;if(bound-out.written<minimum_margin)minimum_margin=bound-out.written;++calls;
   }
  }
 }
 printf("{\"status\":\"passed\",\"chapter_profiles\":%u,\"max_written\":%u,\"min_margin\":%u}\n",calls,maximum,minimum_margin);
}
'''
    if a.production:
        main_c = main_c.replace(' assets.styles=load(argv[1],"styles.bin",&n);assets.layouts=load(argv[1],"layouts.bin",&n);\n', '')
        main_c = main_c.replace(' uint8_t*index=load(argv[1],"search.bin",&n);assets.vocabulary_size=ReadBigEndian16(index+8);assets.normalization=index+20+4*(assets.vocabulary_size+1);\n', '')
        main_c = main_c.replace('&assets,chapter,book,WriteChapterEvent', '&assets,chapter,WriteChapterEvent')
    # Include the generated navigation to select the correct per-book profiles.
    body=prefix+'\n#include "Navigation.h"\n'+constants+'\n'+helper+writer+main_c
    path=BUILD/(('production-' if a.production else '')+'bound-check-'+a.version+'.c');path.write_text(body);exe=path.with_suffix('')
    subprocess.run(['cc','-O2','-std=c99','-I'+str(app),'-I'+str(ROOT/'os3k'),'-I'+str(app/'build/data'/a.version.lower()),str(path),str(app/'Formatting.c'),str(app/'Decoder.c'),'-o',str(exe)],check=True)
    r=subprocess.run([str(exe),str(app/'build/data'/a.version.lower())],text=True,capture_output=True,check=True)
    (BUILD/(('production-' if a.production else '')+'bound-check-'+a.version+'.json')).write_text(r.stdout);print(r.stdout)


if __name__=='__main__':main()
