#ifndef BIBLE_DECODER_H
#define BIBLE_DECODER_H
#if BIBLE_HUFFMAN
#include "HuffmanDecoder.h"
#else
#include <stdint.h>
#include <stddef.h>

/* Fixed workspace; ROM tables are never copied into RAM. Little-endian host
 * tests and two-byte-aligned 68000 placement use the same byte readers. */
typedef struct {
    const uint8_t *image, *dictionary, *model, *base, *contexts, *entries;
    const uint8_t *chapter_index, *payload, *input, *input_end;
    const uint8_t *dict_symbols, *dict_index, *dict_payload;
    uint32_t image_size, low, high, value, remaining, decoded_symbols;
    uint32_t input_byte, input_bits, padded_bits, contexts_count;
    uint16_t terminals, chapters, dict_blocks, dict_alphabet;
    uint16_t previous, have_previous, error, block_cache;
    uint16_t removed[512];
    uint16_t h_count[17], h_first[17];
    uint32_t h_code[17];
    uint8_t h_symbols[84], block[160], word[18];
    uint16_t block_size, word_size, word_pos;
} BibleDecoder;

int BibleInit(BibleDecoder *d, const uint8_t *image, uint32_t size);
int BibleOpenChapter(BibleDecoder *d, uint16_t chapter);
int BibleSeekVerse(BibleDecoder *d,uint16_t chapter,uint16_t verse,
    const uint8_t *index,uint32_t size,uint16_t *restored_verse);
int BibleReadByte(BibleDecoder *d); /* source UTF-8, -1 EOF, -2 malformed */
#endif
#endif
