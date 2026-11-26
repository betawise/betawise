#ifndef BIBLE_DECODER_H
#define BIBLE_DECODER_H

#include "BibleFormat.h"

/* All dictionaries, grammar rules and lookup tables remain in ROM. */
typedef struct {
    const uint8_t* image;
    const uint8_t* dictionary;
    const uint8_t* huffman_model;
    const uint8_t* huffman_symbols;
    const uint8_t* huffman_lookup;
    const uint8_t* grammar_rules;
    const uint8_t* frequent_words;
    const uint8_t* chapter_records;
    const uint8_t* chapter_payload;
    const uint8_t* input_cursor;
    const uint8_t* input_end;
    const uint8_t* dictionary_offsets;
    const uint8_t* dictionary_text;
    uint32_t image_size;
    uint32_t remaining_symbols;
    uint32_t bit_buffer;
    uint32_t buffered_bits;
    uint32_t padding_bytes;
    uint16_t dictionary_word_count;
    uint16_t chapter_count;
    uint16_t max_code_bits;
    uint16_t symbol_count;
    uint16_t grammar_rule_count;
    uint16_t error;
    uint16_t pending_symbols[32];
    uint16_t pending_symbol_count;
    uint16_t dictionary_block_count;
    uint8_t word_buffer[BIBLE_MAX_WORD_BYTES];
    uint16_t word_length;
    uint16_t word_cursor;
} BibleDecoder_t;

int BibleDecoderInit(BibleDecoder_t* decoder, const uint8_t* image, uint32_t size);
int BibleDecoderOpenChapter(BibleDecoder_t* decoder, uint16_t chapter);
/* Read methods return -1 at chapter end, -2 on corrupt input. */
int BibleDecoderReadByte(BibleDecoder_t* decoder);
int BibleDecoderReadNode(BibleDecoder_t* decoder);
int BibleDecoderReadTerminal(BibleDecoder_t* decoder);
int BibleDecoderExpandRule(BibleDecoder_t* decoder, unsigned symbol);
int BibleDecoderGetWord(BibleDecoder_t* decoder, uint16_t terminal,
    char* output, unsigned capacity);

#endif
