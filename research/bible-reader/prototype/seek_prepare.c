/* Host-only checkpoint builder. Snapshots reproduce the exact existing stream. */
#include "Decoder.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void p16(uint8_t *p,unsigned n) {p[0]=n>>8;p[1]=n;}
static void p32(uint8_t *p,uint32_t n) {p16(p,n>>16);p16(p+2,n);}
int main(int argc,char **argv) {
    FILE *f,*out;uint8_t *blob,*buffer;long size;BibleDecoder d,saved;
    uint8_t points[4096][18],directory[1189][4],header[16];unsigned count=0,chapter;
    if(argc!=3 || !(f=fopen(argv[1],"rb"))) return 1;
    fseek(f,0,SEEK_END);size=ftell(f);rewind(f);blob=malloc(size);
    if(!blob || fread(blob,1,size,f)!=(size_t)size) return 2;
    fclose(f);if(!BibleInit(&d,blob,size)) return 3;
    for(chapter=0;chapter<d.chapters;++chapter) {
        unsigned verse=1,n=0;int c;const uint8_t *start;
        if(!BibleOpenChapter(&d,chapter)) return 4;
        start=d.input-4; /* Open preloads four bytes into the arithmetic value. */
        p16(directory[chapter],count);
        while((c=BibleReadByte(&d))>=0) {
            if(c!='\n') continue;
            ++n;++verse;
            if((verse-1)%8==0 && d.remaining) {
                uint8_t *p;
                if(count>=4096 || d.previous!=0 || d.word_pos!=d.word_size || d.remaining>65535 || d.input-start>65535) return 5;
                p=points[count++];
                p32(p,d.low);p32(p+4,d.high);p32(p+8,d.value);p16(p+12,d.remaining);p16(p+14,d.input-start);
                p[16]=(d.padded_bits<<4)|d.input_bits;p[17]=d.input_byte;
            }
        }
        if(c!=-1) return 6;
        p16(directory[chapter]+2,n);
    }
    memcpy(header,"KJVSEEK1",8);p16(header+8,8);p16(header+10,d.chapters);p32(header+12,count);
    out=fopen(argv[2],"wb");if(!out) return 7;
    fwrite(header,1,16,out);fwrite(directory,1,sizeof(directory),out);fwrite(points,18,count,out);fclose(out);
    /* Replay every checkpoint and compare its complete chapter suffix with a
     * separate sequential decode. This checks all stored arithmetic states. */
    size=16+sizeof(directory)+18*count;buffer=malloc(size);f=fopen(argv[2],"rb");
    if(!buffer || !f || fread(buffer,1,size,f)!=(size_t)size) return 8;
    fclose(f);
    for(chapter=0;chapter<d.chapters;++chapter) {
        unsigned verse=1;int c;
        if(!BibleOpenChapter(&d,chapter)) return 9;
        while((c=BibleReadByte(&d))>=0) {
            if(c!='\n') continue;
            ++verse;
            if((verse-1)%8==0 && d.remaining) {
                uint16_t restored;BibleDecoder replay;
                saved=d;
                replay=saved;
                if(!BibleSeekVerse(&replay,chapter,verse,buffer,size,&restored) || restored!=verse) return 10;
                for(;;) {int a=BibleReadByte(&d),b=BibleReadByte(&replay);if(a!=b) return 11;if(a==-1) break;if(a<0) return 12;}
                d=saved;
            }
        }
        if(c!=-1) return 13;
    }
    printf("checkpoint bytes=%ld points=%u; all suffixes replayed exactly\n",size,count);
    free(buffer);free(blob);return 0;
}
