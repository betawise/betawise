#ifndef BIBLE_SEARCH_H
#define BIBLE_SEARCH_H
#include "Decoder.h"
#define SEARCH_SAME_VERSE 0
#define SEARCH_PHRASE 1
#define SEARCH_NEARBY 2
#define SEARCH_NEAR_WORDS 20
#define SEARCH_QUERY_BYTES 64
#define SEARCH_CHAPTERS 1189
#define SEARCH_FILTER_BYTES ((SEARCH_CHAPTERS+7)/8)
typedef struct {
 BibleDecoder decoder;
 const uint8_t *index,*records,*mapping,*postings,*end,*filter;
 uint32_t words;
#if BIBLE_VERSE_BOOST
 const uint8_t *verse_records,*verse_anchors,*verse_cursor;
 uint16_t verse_total,verse_next,verse_active;
 uint8_t verse_candidates[3888];
#endif
 uint16_t origin[3],previous[3],nav_chapter,stop_chapter;
 int16_t direction;
 uint16_t navigating,previous_valid,inclusive;
#if BIBLE_NOINDEX
 uint8_t char_state[8],char_failure[64],token_mask,token_length,token_open,quote;
 int16_t pending_byte;
#endif
 struct {uint32_t position;uint16_t verse,word,mask;} assigned[8];
 uint32_t position;
 uint16_t match_mode,rank,suppressed,restore_verse,resume_verse,query_prefixes;
 uint16_t kind,filter_count,filter_group,prefix_match;
#if BIBLE_PRUNE
 uint8_t contains[256];
#endif
 uint16_t chapter,verse,open,done,phrase_length,matched,word_count,hit_word;
 uint16_t query_ids[8],query_ends[8];
 uint8_t candidates[SEARCH_FILTER_BYTES],offsets[8];
 char query[SEARCH_QUERY_BYTES];
} BibleSearch;
/* Default: all exact words in the same verse. A trailing * expands a term. */
int SearchStart(BibleSearch*,const uint8_t*,uint32_t,const uint8_t*,uint32_t,const char*);
/* Legacy phrase API: all terms exact (0) or all prefixes (1). */
int SearchStartMode(BibleSearch*,const uint8_t*,uint32_t,const uint8_t*,uint32_t,const char*,unsigned prefix_match);
int SearchBegin(BibleSearch*,const uint8_t*,uint32_t,const uint8_t*,uint32_t,const char*,unsigned match_mode);
/* 1 = occurrence at chapter/verse/hit_word (zero-based word ordinal);
 * 0 = more bounded work; -1 = end; -2 = error. */
int SearchStep(BibleSearch*,unsigned budget);
/* Search relative to a reading position, no wrap. direction=-1 previous, +1 next.
 * inclusive includes a match beginning at the supplied word; previous rescans
 * one candidate chapter at a time, retaining only the latest qualifying hit. */
void SearchFrom(BibleSearch*,unsigned chapter,unsigned verse,unsigned word,int direction,unsigned inclusive);
#endif
