/* Host-only driver. Decoder.c itself performs no allocations or file I/O. */
#include "Decoder.h"
#include <stdio.h>
#include <stdlib.h>
static void put32(FILE *f,uint32_t n) {int i;for(i=24;i>=0;i-=8) fputc(n>>i,f);}
int main(int argc,char **argv) {
    FILE *f,*out;long n;uint8_t *blob;BibleDecoder decoder;int i,c;
    if(argc!=3 || !(f=fopen(argv[1],"rb"))) return 1;
    fseek(f,0,SEEK_END);n=ftell(f);rewind(f);blob=malloc(n);
    if(!blob || fread(blob,1,n,f)!=(size_t)n) return 2;
    fclose(f);if(!BibleInit(&decoder,blob,n)) return 3;
    out=fopen(argv[2],"wb");if(!out) return 4;
    put32(out,decoder.chapters);
    for(i=decoder.chapters-1;i>=0;--i) {
        uint32_t count=0;long where;
        if(!BibleOpenChapter(&decoder,i)) return 5;
        put32(out,i);where=ftell(out);put32(out,0);
        while((c=BibleReadByte(&decoder))>=0) {fputc(c,out);++count;}
        if(c!=-1) {fprintf(stderr,"decode failed chapter=%d symbols=%u\n",i,decoder.decoded_symbols);return 6;}
        fseek(out,where,SEEK_SET);put32(out,count);fseek(out,0,SEEK_END);
    }
    fclose(out);printf("host workspace=%lu chapters=%u\n",(unsigned long)sizeof(decoder),decoder.chapters);free(blob);return 0;
}
