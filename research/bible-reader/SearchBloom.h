#ifndef BIBLE_SEARCH_BLOOM_H
#define BIBLE_SEARCH_BLOOM_H
#include "Decoder.h"
#define SEARCH_QUERY_BYTES 64
#define SEARCH_CHAPTERS 1189
#define SEARCH_FILTER_BYTES ((SEARCH_CHAPTERS+7)/8)
typedef struct {
 BibleDecoder decoder;
 const uint8_t *index,*records,*mapping,*chapter_offsets,*verses,*end;
 uint32_t words,mask[2];
 uint16_t chapter,verse,open,done,phrase_length,matched,word_count,hit_word,verse_index,verse_total;
 uint16_t query_ids[8];
 uint8_t offsets[8],prefix[8];
 char query[SEARCH_QUERY_BYTES];
} BibleBloomSearch;
/* Case-insensitive exact word sequence. Missing words produce an empty filter. */
int BloomSearchStart(BibleBloomSearch*,const uint8_t*,uint32_t,const uint8_t*,uint32_t,const char*);
/* Bounded terminal-symbol work. 1 = occurrence at chapter/verse/hit_word;
 * 0 = more work; -1 = end; -2 = error. hit_word is zero-based within its verse. */
int BloomSearchStep(BibleBloomSearch*,unsigned budget);
#endif
