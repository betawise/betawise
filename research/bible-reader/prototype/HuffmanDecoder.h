#ifndef BIBLE_HUFFMAN_DECODER_H
#define BIBLE_HUFFMAN_DECODER_H
#ifndef BIBLE_DENSE
#define BIBLE_DENSE 0
#endif
#ifndef BIBLE_PRUNE
#define BIBLE_PRUNE 0
#endif
#ifndef BIBLE_CHECKPOINTS
#define BIBLE_CHECKPOINTS 0
#endif
#ifndef BIBLE_FAST_BITS
#define BIBLE_FAST_BITS 8
#endif
#include <stdint.h>
#include <stddef.h>
typedef struct {
    const uint8_t *image,*dictionary,*model,*ordered,*fast,*grammar,*hot;
    const uint8_t *chapter_index,*payload,*input,*input_end;
    const uint8_t *dict_symbols,*dict_index,*dict_payload;
    uint32_t image_size,remaining,decoded_symbols,buffer,bits,padded;
#if BIBLE_CHECKPOINTS
    uint32_t anchor_bit,anchor_symbol;
    uint16_t anchor_skip,point_tracking;
#endif
    uint16_t terminals,chapters,maximum,alphabet,rule_count,error,block_cache,raw_dictionary;
    uint16_t stack[32],stack_count;
#if !BIBLE_RAW_ONLY
    uint16_t h_count[17],h_first[17];uint32_t h_code[17];
    uint8_t h_symbols[84],block[512];
#endif
    uint8_t word[64];
    uint16_t dict_alphabet,dict_blocks,block_size,word_size,word_pos;
} BibleDecoder;
typedef struct {uint32_t bit,symbol;uint16_t skip;} BiblePoint;
#if BIBLE_CHECKPOINTS
void BibleSavePoint(BibleDecoder*,BiblePoint*);
int BibleRestorePoint(BibleDecoder*,uint16_t,const BiblePoint*);
#endif
int BibleInit(BibleDecoder*,const uint8_t*,uint32_t);
int BibleOpenChapter(BibleDecoder*,uint16_t);
int BibleReadByte(BibleDecoder*);
int BibleReadTerminal(BibleDecoder*);
int BibleReadNode(BibleDecoder*);
int BiblePushRule(BibleDecoder*,unsigned);
/* Verse restart: caller stops at its first LF; bit offsets refer to the chapter. */
int BibleOpenVerse(BibleDecoder*,uint16_t,uint32_t,unsigned);
int BibleGetWord(BibleDecoder*,uint16_t,char*,unsigned);
#endif
