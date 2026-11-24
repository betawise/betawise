#include "Decoder.h"
#include <string.h>

/* Serialized sections may begin at odd byte offsets. GCC otherwise recognizes
 * bytewise BE reads and folds them into faulting 68000 MOVE.W/MOVE.L loads. */
static uint16_t be16(const volatile uint8_t *p) { return ((uint16_t)p[0]<<8)|p[1]; }
static uint32_t be32(const volatile uint8_t *p) { return ((uint32_t)be16(p)<<16)|be16(p+2); }
static int fail(BibleDecoder *d) {d->error=1;return 0;}
#define FAIL(d) fail(d)
#define HALF UINT32_C(0x80000000)
#define Q1 UINT32_C(0x40000000)
#define Q3 UINT32_C(0xc0000000)

int BibleInit(BibleDecoder *d, const uint8_t *image, uint32_t size) {
    uint32_t meta, lex_size, codec_size, i, code=0, first=0, running=0;
    const uint8_t *codec, *lengths;
    memset(d,0,sizeof(*d));
    d->image=image;d->image_size=size;d->block_cache=UINT16_MAX;
    if(size<64 || memcmp(image,"KJVCTX02",8)) return FAIL(d);
    meta=be32(image+8);d->terminals=be32(image+12);lex_size=be32(image+16);
    codec_size=be32(image+28);d->chapters=be32(image+36);
    /* This prototype deliberately accepts only the measured word model. */
    if(be32(image+20)!=0 || be32(image+24)!=1 || !d->terminals || d->terminals>16384 || d->chapters!=1189 ||
       meta>size-64 || lex_size>size-64-meta || codec_size!=size-64-meta-lex_size) return FAIL(d);
    d->dictionary=image+64+meta;codec=d->dictionary+lex_size;
    if(codec_size<16 || memcmp(codec,"CTXAR001",8) || be32(codec+12)!=d->chapters) return FAIL(d);
    d->model=codec+16;
    if(be32(d->model)!=d->terminals || be32(d->model+4)!=513) return FAIL(d);
    d->contexts_count=be32(d->model+8);
    if(d->contexts_count>4096 || be32(codec+8)<12+2u*d->terminals+12*d->contexts_count ||
       be32(codec+8)>codec_size-16-16u*d->chapters) return FAIL(d);
    d->base=d->model+12;d->contexts=d->base+2u*d->terminals;
    d->entries=d->contexts+12*d->contexts_count;
    d->chapter_index=d->model+be32(codec+8);d->payload=d->chapter_index+16u*d->chapters;
    d->dict_blocks=be16(d->dictionary);d->dict_alphabet=be16(d->dictionary+2);
    if(d->dict_blocks!=(d->terminals+15)/16 || d->dict_alphabet>84 ||
       4u+2u*d->dict_alphabet+8u*d->dict_blocks>lex_size) return FAIL(d);
    d->dict_symbols=d->dictionary+4;lengths=d->dict_symbols+d->dict_alphabet;
    d->dict_index=lengths+d->dict_alphabet;d->dict_payload=d->dict_index+8u*d->dict_blocks;
    for(i=0;i<d->dict_alphabet;++i) {
        if(!lengths[i] || lengths[i]>16) return FAIL(d);
        ++d->h_count[lengths[i]];
    }
    for(i=1;i<=16;++i) {
        uint16_t j;
        code=(code+(i>1?d->h_count[i-1]:0))<<1;
        d->h_code[i]=code;d->h_first[i]=first;
        for(j=0;j<d->dict_alphabet;++j) if(lengths[j]==i) d->h_symbols[running++]=d->dict_symbols[j];
        first+=d->h_count[i];
    }
    return 1;
}

static unsigned bit(BibleDecoder *d) {
    if(!d->input_bits) {
        if(d->input<d->input_end) d->input_byte=*d->input++;
        else {d->input_byte=0;if(++d->padded_bits>4) d->error=1;}
        d->input_bits=8;
    }
    return (d->input_byte>>--d->input_bits)&1;
}

int BibleOpenChapter(BibleDecoder *d, uint16_t chapter) {
    const uint8_t *record;uint32_t offset, size;uint16_t i;
    if(d->error || chapter>=d->chapters) return FAIL(d);
    record=d->chapter_index+16u*chapter;offset=be32(record);size=be32(record+4);
    if(offset>(uint32_t)(d->image+d->image_size-d->payload) ||
       size>(uint32_t)(d->image+d->image_size-d->payload)-offset) return FAIL(d);
    d->input=d->payload+offset;d->input_end=d->input+size;
    d->remaining=be32(record+8);d->decoded_symbols=0;d->low=0;d->high=UINT32_MAX;d->value=0;
    d->input_byte=d->input_bits=d->padded_bits=0;d->have_previous=0;d->word_pos=d->word_size=0;
    for(i=0;i<32;++i) d->value=(d->value<<1)|bit(d);
    return !d->error;
}

int BibleSeekVerse(BibleDecoder *d,uint16_t chapter,uint16_t verse,
    const uint8_t *index,uint32_t size,uint16_t *restored_verse) {
    uint16_t group,first,count;uint32_t point;const uint8_t *record;
    if(!BibleOpenChapter(d,chapter)) return 0;
    if(size<16+4u*d->chapters || memcmp(index,"KJVSEEK1",8) ||
       be16(index+8)!=8 || be16(index+10)!=d->chapters) return FAIL(d);
    count=be16(index+16+4u*chapter+2);
    if(!verse || verse>count) return FAIL(d);
    group=(verse-1)/8;*restored_verse=1;
    if(!group) return 1;
    first=be16(index+16+4u*chapter);point=(uint32_t)first+group-1;
    if(point>=be32(index+12) || 18u*(point+1)>size-16-4u*d->chapters) return FAIL(d);
    record=index+16+4u*d->chapters+18u*point;
    d->low=be32(record);d->high=be32(record+4);d->value=be32(record+8);
    d->remaining=be16(record+12);first=be16(record+14);
    if(first>be32(d->chapter_index+16u*chapter+4) || d->remaining>be32(d->chapter_index+16u*chapter+8)) return FAIL(d);
    d->input=d->payload+be32(d->chapter_index+16u*chapter)+first;
    d->input_bits=record[16]&15;d->padded_bits=record[16]>>4;d->input_byte=record[17];
    if(d->input_bits>8 || d->padded_bits>4) return FAIL(d);
    d->decoded_symbols=be32(d->chapter_index+16u*chapter+8)-d->remaining;
    /* Newline is terminal ID zero in this pinned dictionary. Checkpoints are
     * immediately after that token, never in the middle of a spelling. */
    d->previous=0;d->have_previous=1;d->word_pos=d->word_size=0;
    *restored_verse=1+8*group;
    return 1;
}

static uint32_t target(BibleDecoder *d, uint32_t total) {
    if(!total || d->value<d->low || d->value>d->high) return FAIL(d);
    return (((uint64_t)d->value-d->low+1)*total-1)/((uint64_t)d->high-d->low+1);
}
static void consume(BibleDecoder *d,uint32_t a,uint32_t b,uint32_t total) {
    uint64_t range=(uint64_t)d->high-d->low+1;
    if(a>=b || b>total || !total) {d->error=1;return;}
    d->high=d->low+range*b/total-1;d->low=d->low+range*a/total;
    for(;;) {
        if(d->high<HALF) {}
        else if(d->low>=HALF) {d->low-=HALF;d->high-=HALF;d->value-=HALF;}
        else if(d->low>=Q1 && d->high<Q3) {d->low-=Q1;d->high-=Q1;d->value-=Q1;}
        else break;
        d->low<<=1;d->high=(d->high<<1)|1;d->value=(d->value<<1)|bit(d);
    }
}
static uint32_t excluded_end(BibleDecoder *d,const uint8_t *entries,uint16_t n,uint16_t s) {
    uint16_t a=0,b=n;
    while(a<b) {uint16_t m=(a+b)/2;if(be16(entries+4u*m)<=s) a=m+1;else b=m;}
    return be16(d->base+2u*s)-(a?d->removed[a-1]:0);
}
static int symbol(BibleDecoder *d) {
    uint32_t a=0,b=d->contexts_count,t,total,key;
    const uint8_t *context=0,*entries=0;uint16_t n=0,s;
    if(d->have_previous) {
        key=(uint32_t)d->terminals+d->previous+2;
        while(a<b) {uint32_t m=(a+b)/2;if(be32(d->contexts+12*m)<key) a=m+1;else b=m;}
        if(a<d->contexts_count && be32(d->contexts+12*a)==key) context=d->contexts+12*a;
    }
    if(context) {
        uint32_t offset=be32(context+4);n=be16(context+8);
        if(!n || n>513 || offset>(uint32_t)(d->chapter_index-d->entries) || 4u*n>(uint32_t)(d->chapter_index-d->entries)-offset) return FAIL(d),-2;
        entries=d->entries+offset;total=be16(context+10);t=target(d,total);a=0;b=n;
        while(a<b) {uint16_t m=(a+b)/2;if(be16(entries+4u*m+2)<=t) a=m+1;else b=m;}
        if(a>=n) return FAIL(d),-2;
        s=be16(entries+4*a);consume(d,a?be16(entries+4*a-2):0,be16(entries+4*a+2),total);
        if(s<d->terminals) goto done;
        if(s!=d->terminals || a!=(uint32_t)n-1) return FAIL(d),-2;
        --n;total=0;
        for(a=0;a<n;++a) {
            uint16_t v=be16(entries+4*a);
            if(v>=d->terminals) return FAIL(d),-2;
            total+=be16(d->base+2u*v)-(v?be16(d->base+2u*v-2):0);
            if(total>65535) return FAIL(d),-2;
            d->removed[a]=total;
        }
    }
    total=be16(d->base+2u*d->terminals-2)-(n?d->removed[n-1]:0);
    t=target(d,total);a=0;b=d->terminals;
    while(a<b) {
        uint16_t m=(a+b)/2;uint32_t end=n?excluded_end(d,entries,n,m):be16(d->base+2u*m);
        if(end<=t) a=m+1;else b=m;
    }
    if(a>=d->terminals) return FAIL(d),-2;
    s=a;consume(d,s?(n?excluded_end(d,entries,n,s-1):be16(d->base+2u*s-2)):0,
        n?excluded_end(d,entries,n,s):be16(d->base+2u*s),total);
done:
    d->previous=s;d->have_previous=1;++d->decoded_symbols;--d->remaining;
    return d->error?-2:s;
}

static int spelling(BibleDecoder *d,uint16_t s) {
    uint16_t block=s/16, i, pos=0, length=0;
    if(d->block_cache!=block) {
        const uint8_t *record=d->dict_index+8u*block,*p=d->dict_payload+be32(record),*end=p+be16(record+4);
        uint32_t bits=0;unsigned have=0;
        d->block_size=be16(record+6);
        if(d->block_size>sizeof(d->block) || end>d->model-16) return FAIL(d);
        for(i=0;i<d->block_size;++i) {
            uint32_t code=0;uint16_t n;
            for(n=1;n<=16;++n) {
                if(!have) {if(p>=end) return FAIL(d);bits=*p++;have=8;}
                code=(code<<1)|((bits>>--have)&1);
                if(code>=d->h_code[n] && code-d->h_code[n]<d->h_count[n]) break;
            }
            if(n>16) return FAIL(d);
            d->block[i]=d->h_symbols[d->h_first[n]+code-d->h_code[n]];
        }
        d->block_cache=block;
    }
    for(i=0;i<=s%16;++i) {
        uint16_t prefix;
        if(pos>=d->block_size) return FAIL(d);
        prefix=d->block[pos++];if(prefix>length) return FAIL(d);length=prefix;
        while(pos<d->block_size && d->block[pos]) {
            if(length>=sizeof(d->word)-1) return FAIL(d);
            d->word[length++]=d->block[pos++];
        }
        if(pos>=d->block_size) return FAIL(d);
        ++pos;d->word[length]=0;
    }
    d->word_size=length;d->word_pos=0;
    return 1;
}

int BibleReadByte(BibleDecoder *d) {
    int s;
    if(d->error) return -2;
    if(d->word_pos<d->word_size) return d->word[d->word_pos++];
    if(!d->remaining) return -1;
    s=symbol(d);if(s<0 || !spelling(d,s)) return -2;
    if(!d->word_size) return FAIL(d),-2;
    return d->word[d->word_pos++];
}
