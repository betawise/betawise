/* Fixed-memory word/phrase Huffman comparison backend, ASCII-only resource. */
#include "Decoder.h"
#include <string.h>
#if BIBLE_WORK_PROFILE
volatile uint32_t g_decode_work[4]; /* calls, source bytes, chapter opens, restores */
#define BYTE_IMPL static int read_byte_impl
#else
#define BYTE_IMPL int BibleReadByte
#endif
#if BIBLE_FAST_BITS > 8
extern const uint8_t BibleFastHuffmanTable[];
#endif
static uint16_t be16(const volatile uint8_t*p){return ((uint16_t)p[0]<<8)|p[1];}
static uint32_t be32(const volatile uint8_t*p){return ((uint32_t)be16(p)<<16)|be16(p+2);}
static int fail(BibleDecoder*d){d->error=1;return 0;}

int BibleInit(BibleDecoder*d,const uint8_t*image,uint32_t size){
    uint32_t m,ls,ms,np;
#if !BIBLE_RAW_ONLY
    uint32_t i,code=0,first=0,running=0;const uint8_t*lengths;
#endif
    memset(d,0,sizeof(*d));d->image=image;d->image_size=size;d->block_cache=UINT16_MAX;
#if BIBLE_CHECKPOINTS
    d->point_tracking=1;
#endif
    if(size<64)return fail(d);
    if(be32(image+40)){uint32_t h=be32(image+40);if(h>size||size-h<1024)return fail(d);d->hot=image+h;}
    d->raw_dictionary=!memcmp(image,"KJVHUF02",8);
#if BIBLE_DENSE
    d->raw_dictionary=!memcmp(image,"KJVDNS01",8);
#endif
    if(!d->raw_dictionary&&memcmp(image,"KJVHUF01",8))return fail(d);
    m=be32(image+8);d->terminals=be32(image+12);ls=be32(image+16);ms=be32(image+20);
    d->chapters=be32(image+24);np=be32(image+32);d->maximum=be32(image+36);
    if(d->chapters!=1189||!d->terminals||d->terminals>63487||np>2048||!d->maximum||d->maximum>(BIBLE_DENSE?255:24)||
       m>size-64||ls>size-64-m||ms>size-64-m-ls)return fail(d);
    d->rule_count=np;d->alphabet=d->terminals+np;d->dictionary=image+64+m;d->model=d->dictionary+ls;
#if BIBLE_DENSE
    if(ms!=2u*d->alphabet)return fail(d);
    d->ordered=d->model;
#else
    if(be16(d->model)!=d->maximum||be16(d->model+2)!=d->alphabet||ms!=4+8u*d->maximum+2u*d->alphabet+1024)return fail(d);
    d->ordered=d->model+4+8u*d->maximum;d->fast=d->ordered+2u*d->alphabet;
#if BIBLE_FAST_BITS > 8
    d->fast=BibleFastHuffmanTable;
#endif
#endif
    d->grammar=d->model+ms;d->chapter_index=d->grammar+4*np;d->payload=d->chapter_index+16u*d->chapters;
    if(d->payload>image+size)return fail(d);
    if(d->raw_dictionary){
        d->dict_blocks=(d->terminals+15)/16;d->dict_index=d->dictionary;
        d->dict_payload=d->dict_index+4u*d->dict_blocks;
        return d->dict_payload<d->model;
    }
#if BIBLE_RAW_ONLY
    return fail(d);
#else
    d->dict_blocks=be16(d->dictionary);d->dict_alphabet=be16(d->dictionary+2);
    if(d->dict_blocks!=(d->terminals+15)/16||d->dict_alphabet>84)return fail(d);
    d->dict_symbols=d->dictionary+4;lengths=d->dict_symbols+d->dict_alphabet;
    d->dict_index=lengths+d->dict_alphabet;d->dict_payload=d->dict_index+8u*d->dict_blocks;
    if(d->dict_payload>d->model)return fail(d);
    for(i=0;i<d->dict_alphabet;++i){if(!lengths[i]||lengths[i]>16)return fail(d);++d->h_count[lengths[i]];}
    for(i=1;i<=16;++i){uint16_t j;code=(code+(i>1?d->h_count[i-1]:0))<<1;d->h_code[i]=code;d->h_first[i]=first;
        for(j=0;j<d->dict_alphabet;++j)if(lengths[j]==i)d->h_symbols[running++]=d->dict_symbols[j];
        first+=d->h_count[i];}
    return 1;
#endif
}
int BibleOpenChapter(BibleDecoder*d,uint16_t chapter){
#if BIBLE_WORK_PROFILE
 ++g_decode_work[2];
#endif
    const uint8_t*r;uint32_t a,n;
    if(d->error||chapter>=d->chapters)return fail(d);
    r=d->chapter_index+16u*chapter;a=be32(r);n=be32(r+4);
    if(a>(uint32_t)(d->image+d->image_size-d->payload)||n>(uint32_t)(d->image+d->image_size-d->payload)-a)return fail(d);
    d->input=d->payload+a;d->input_end=d->input+n;d->remaining=be32(r+8);d->decoded_symbols=0;
#if BIBLE_CHECKPOINTS
    d->anchor_bit=a*8u;d->anchor_symbol=d->anchor_skip=0;
#endif
    d->buffer=d->bits=d->padded=0;d->stack_count=d->word_pos=d->word_size=0;return 1;
}
static void refill(BibleDecoder*d,unsigned n){
    while(d->bits<n){unsigned byte=0;if(d->input<d->input_end)byte=*d->input++;else if(++d->padded>4)d->error=1;
        d->buffer=(d->buffer<<8)|byte;d->bits+=8;}
}
static int symbol(BibleDecoder*d){
#if BIBLE_DENSE
    uint16_t rank=0,base=0,range=d->maximum;unsigned c=256-d->maximum,n;
    for(n=0;n<3;++n){unsigned byte;if(d->input>=d->input_end){fail(d);return -2;}byte=*d->input++;
        if(byte<c){rank=rank*c+byte;base+=range;range*=c;}
        else{rank=base+rank*d->maximum+byte-c;if(rank>=d->alphabet){fail(d);return -2;}return be16(d->ordered+2u*rank);}}
    fail(d);return -2;
#else
    uint32_t prefix,entry,code;unsigned n;
    refill(d,BIBLE_FAST_BITS);prefix=(d->buffer>>(d->bits-BIBLE_FAST_BITS))&((1u<<BIBLE_FAST_BITS)-1);
#if defined(__m68k__) && BIBLE_FAST_NATIVE && BIBLE_FAST_BITS > 8
    /* The optional table is word-aligned, unlike arbitrary container offsets. */
    entry=*(const uint32_t*)(d->fast+4*prefix);
#else
    entry=be32(d->fast+4*prefix);
#endif
    if(entry){d->bits-=entry&31;return entry>>5;}
    code=prefix;d->bits-=BIBLE_FAST_BITS;
    for(n=BIBLE_FAST_BITS+1;n<=d->maximum;++n){const uint8_t*r=d->model+4+8u*(n-1);uint32_t first=be32(r);unsigned count=be16(r+6);
        refill(d,1);code=(code<<1)|((d->buffer>>--d->bits)&1);
        if(code>=first&&code-first<count)return be16(d->ordered+2u*(be16(r+4)+code-first));}
    fail(d);return -2;
#endif
}
static int spelling(BibleDecoder*d,uint16_t s){
    uint16_t block=s/16,i,pos=0,length=0;
    const uint8_t*data;
    if(d->hot){unsigned slot=(s^(s>>8))&255;const uint8_t*r=d->hot+4*slot;
        if(be16(r)==s){unsigned n=0;data=d->hot+1024+be16(r+2);
            while(data<d->image+d->image_size&&*data){if(n>=sizeof(d->word)-1)return fail(d);d->word[n++]=*data++;}
            if(data>=d->image+d->image_size)return fail(d);
            d->word[n]=0;d->word_size=n;d->word_pos=0;return 1;}}
    if(d->raw_dictionary){
        uint32_t offset=be32(d->dict_index+4u*block);
        const uint8_t*end=block+1<d->dict_blocks?d->dict_payload+be32(d->dict_index+4u*(block+1)):d->model;
        data=d->dict_payload+offset;
        if(data>=end||end>d->model||end-data>512)return fail(d);
        d->block_size=end-data;
    }else {
#if BIBLE_RAW_ONLY
        return fail(d);
#else
        data=d->block;
        if(d->block_cache!=block){
        const uint8_t*r=d->dict_index+8u*block,*p=d->dict_payload+be32(r),*end=p+be16(r+4);
        uint32_t bits=0;unsigned have=0;d->block_size=be16(r+6);
        if(d->block_size>sizeof(d->block)||end>d->model)return fail(d);
        for(i=0;i<d->block_size;++i){uint32_t code=0;uint16_t n;
            for(n=1;n<=16;++n){if(!have){if(p>=end)return fail(d);bits=*p++;have=8;}code=(code<<1)|((bits>>--have)&1);
                if(code>=d->h_code[n]&&code-d->h_code[n]<d->h_count[n])break;}
            if(n>16)return fail(d);
            d->block[i]=d->h_symbols[d->h_first[n]+code-d->h_code[n]];}
        d->block_cache=block;}
#endif
    }
    for(i=0;i<=s%16;++i){unsigned prefix;if(pos>=d->block_size)return fail(d);prefix=data[pos++];if(prefix>length)return fail(d);length=prefix;
        while(pos<d->block_size&&data[pos]){if(length>=sizeof(d->word)-1)return fail(d);d->word[length++]=data[pos++];}
        if(pos>=d->block_size)return fail(d);
        ++pos;d->word[length]=0;}
    d->word_size=length;d->word_pos=0;return 1;
}
int BibleReadNode(BibleDecoder*d){
    int s;if(d->error)return -2;
    if(d->stack_count)return d->stack[--d->stack_count];
    if(!d->remaining)return -1;
#if BIBLE_CHECKPOINTS
    if(d->point_tracking){d->anchor_bit=(uint32_t)(d->input-d->payload)*8u-d->bits;
    d->anchor_symbol=d->decoded_symbols;d->anchor_skip=0;}
#endif
    s=symbol(d);if(s<0)return -2;--d->remaining;++d->decoded_symbols;return s;
}
int BiblePushRule(BibleDecoder*d,unsigned s){
    const uint8_t*r;unsigned a,b;
    if(s<d->terminals||s>=d->alphabet||d->stack_count>30)return fail(d);
    r=d->grammar+4u*(s-d->terminals);a=be16(r);b=be16(r+2);
    if(a>=s||b>=s)return fail(d);
    d->stack[d->stack_count++]=b;d->stack[d->stack_count++]=a;return 1;
}
int BibleReadTerminal(BibleDecoder*d){
    int s=BibleReadNode(d);if(s<0)return s;
    while(s>=d->terminals){const uint8_t*r;unsigned a,b;
        if(s>=d->alphabet||d->stack_count>=32){fail(d);return -2;}
        r=d->grammar+4u*(s-d->terminals);a=be16(r);b=be16(r+2);
        if(a>=(unsigned)s||b>=(unsigned)s){fail(d);return -2;}
        d->stack[d->stack_count++]=b;s=a;}
    return s;
}
BYTE_IMPL(BibleDecoder*d){
    int s;if(d->error)return -2;
    if(d->word_pos<d->word_size){
#if BIBLE_CHECKPOINTS
        if(d->point_tracking)++d->anchor_skip;
#endif
        return d->word[d->word_pos++];}
    s=BibleReadTerminal(d);if(s<0)return s;
    if(!spelling(d,s)||!d->word_size){fail(d);return -2;}
#if BIBLE_CHECKPOINTS
    if(d->point_tracking)++d->anchor_skip;
#endif
    return d->word[d->word_pos++];
}
#if BIBLE_WORK_PROFILE
int BibleReadByte(BibleDecoder*d){int c;++g_decode_work[0];c=read_byte_impl(d);if(c>=0)++g_decode_work[1];return c;}
#endif
int BibleGetWord(BibleDecoder*d,uint16_t s,char*out,unsigned capacity){
    if(s>=d->terminals||!spelling(d,s)||capacity<=d->word_size)return 0;
    memcpy(out,d->word,d->word_size+1);return d->word_size;
}

int BibleOpenVerse(BibleDecoder*d,uint16_t chapter,uint32_t bit,unsigned skip){
    unsigned i;if(!BibleOpenChapter(d,chapter))return 0;
    if(bit>=(uint32_t)(d->input_end-d->input)*8u)return fail(d);
    d->input+=bit/8;
    if(bit&7){refill(d,8);d->bits-=bit&7;}
    d->remaining=UINT32_MAX;
    for(i=0;i<skip;++i)if(BibleReadTerminal(d)<0)return fail(d);
    return 1;
}

#if BIBLE_CHECKPOINTS
void BibleSavePoint(BibleDecoder*d,BiblePoint*p){p->bit=d->anchor_bit;p->symbol=d->anchor_symbol;p->skip=d->anchor_skip;}
int BibleRestorePoint(BibleDecoder*d,uint16_t chapter,const BiblePoint*p){unsigned i;
#if BIBLE_WORK_PROFILE
 ++g_decode_work[3];
#endif
 if(!BibleOpenChapter(d,chapter))return 0;
 if(p->symbol>d->remaining||p->bit/8>(uint32_t)(d->input_end-d->payload))return fail(d);
 d->input=d->payload+p->bit/8;d->remaining-=p->symbol;d->decoded_symbols=p->symbol;
 d->anchor_bit=p->bit;d->anchor_symbol=p->symbol;d->anchor_skip=0;
 if(p->bit&7){refill(d,8);d->bits-=p->bit&7;}
 for(i=0;i<p->skip;++i)if(BibleReadByte(d)<0)return fail(d);
 return 1;
}
#endif
