#ifndef BIBLE_FORMAT_H
#define BIBLE_FORMAT_H

#include <stdint.h>

#define BIBLE_BOOK_COUNT 66
#define BIBLE_CHAPTER_COUNT 1189
#define BIBLE_CONTAINER_HEADER_SIZE 64
#define BIBLE_CONTAINER_MAGIC "KJVHUF03"
/* Chapter records: three big-endian uint32 fields, then uint16 native-output
 * capacity and uint16 source length. Bounds include markup, not the editor gap. */
#define BIBLE_CHAPTER_RECORD_BYTES 16u
#define BIBLE_CHAPTER_CAPACITY_OFFSET 12
#define BIBLE_CHAPTER_SOURCE_BYTES_OFFSET 14
#define BIBLE_DICTIONARY_BLOCK_WORDS 16
#define BIBLE_MAX_WORD_BYTES 64
#define BIBLE_MAX_GRAMMAR_RULES 2048
#define BIBLE_HUFFMAN_LOOKUP_BITS 8
#define BIBLE_LEFT_SINGLE_QUOTE 0x91
#define BIBLE_RIGHT_SINGLE_QUOTE 0x92
#define BIBLE_LEFT_DOUBLE_QUOTE 0x93
#define BIBLE_RIGHT_DOUBLE_QUOTE 0x94

static inline unsigned IsBibleQuote(unsigned character) {
    return character >= BIBLE_LEFT_SINGLE_QUOTE && character <= BIBLE_RIGHT_DOUBLE_QUOTE;
}

static inline unsigned IsBibleApostrophe(unsigned character) {
    return character == '\'' || (uint8_t)character == BIBLE_RIGHT_SINGLE_QUOTE;
}

/* Container fields can start at odd ROM addresses. Read bytes explicitly on 68000. */
static inline uint16_t ReadBigEndian16(const volatile uint8_t* bytes) {
    return ((uint16_t)bytes[0] << 8) | bytes[1];
}

static inline uint32_t ReadBigEndian32(const volatile uint8_t* bytes) {
    return ((uint32_t)ReadBigEndian16(bytes) << 16) | ReadBigEndian16(bytes + 2);
}

static inline unsigned IsBibleLetter(unsigned character) {
    return (character >= 'a' && character <= 'z') ||
        (character >= 'A' && character <= 'Z');
}

static inline unsigned LowercaseBibleLetter(unsigned character) {
    character = (uint8_t)character;
    if(character == BIBLE_RIGHT_SINGLE_QUOTE) return '\'';
    return character >= 'A' && character <= 'Z' ? character + 'a' - 'A' : character;
}

#endif
