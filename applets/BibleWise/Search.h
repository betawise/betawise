#ifndef BIBLE_SEARCH_H
#define BIBLE_SEARCH_H

#include "Decoder.h"

#define BIBLE_SEARCH_QUERY_BYTES 64
#define BIBLE_SEARCH_MAX_TERMS 8
#define BIBLE_SEARCH_NEAR_WORDS 20
#define BIBLE_SEARCH_CHAPTER_BYTES ((BIBLE_CHAPTER_COUNT + 7) / 8)

typedef enum {
    BIBLE_SEARCH_SAME_VERSE,
    BIBLE_SEARCH_PHRASE,
    BIBLE_SEARCH_NEARBY
} BibleSearchMode_e;

typedef enum {
    BIBLE_SEARCH_ERROR = -2,
    BIBLE_SEARCH_COMPLETE = -1,
    BIBLE_SEARCH_PENDING = 0,
    BIBLE_SEARCH_FOUND = 1
} BibleSearchResult_e;

typedef struct {
    uint16_t chapter;
    uint16_t verse;
    uint16_t word;
} BibleSearchLocation_t;

typedef struct {
    uint32_t position;
    uint16_t verse;
    uint16_t word;
    uint16_t accepted_terms;
} BibleSearchOccurrence_t;

typedef struct {
    BibleDecoder_t decoder;
    const uint8_t* vocabulary_records;
    const uint8_t* normalization_map;
    const uint8_t* postings;
    const uint8_t* index_end;
    uint32_t vocabulary_size;
    uint16_t term_count;
    uint16_t term_first[BIBLE_SEARCH_MAX_TERMS];
    uint16_t term_end[BIBLE_SEARCH_MAX_TERMS];
    BibleSearchMode_e match_mode;
    uint16_t nearby_words;
    uint16_t wrap_enabled;
    uint16_t wrapped;
    BibleSearchLocation_t wrap_origin;
    uint8_t candidate_chapters[BIBLE_SEARCH_CHAPTER_BYTES];
    uint8_t matching_rules[BIBLE_MAX_GRAMMAR_RULES / 8];
    BibleSearchOccurrence_t assigned_occurrences[BIBLE_SEARCH_MAX_TERMS];
    uint16_t assigned_count;
    uint16_t verse_already_reported;
    uint32_t word_position;
    uint32_t reported_position;
    uint16_t phrase_state;
    uint16_t verse_word_count;
    uint16_t chapter;
    uint16_t verse;
    uint16_t matched_word;
    uint16_t matched_end_verse;
    uint16_t matched_end_word;
    uint16_t chapter_open;
    uint16_t complete;
    uint16_t restore_scan_verse;
    uint16_t resume_verse;
    BibleSearchLocation_t origin;
    BibleSearchLocation_t previous_match;
    BibleSearchLocation_t previous_match_end;
    uint16_t backward_chapter;
    uint16_t chapter_limit;
    int16_t direction;
    uint16_t has_origin;
    uint16_t previous_match_valid;
    uint16_t include_origin;
    uint16_t selection_origin;
} BibleSearch_t;

/* Terms are exact unless followed by *. Punctuation separates query words. */
int BibleSearchBegin(BibleSearch_t* search, const uint8_t* bible, uint32_t bible_size,
    const uint8_t* index, uint32_t index_size, const char* query, BibleSearchMode_e mode);
/* Search from a reading position without wrapping. Backward searches rescan one
 * candidate chapter at a time; direction is -1 (previous) or +1 (next). */
void BibleSearchSetOrigin(BibleSearch_t* search, unsigned chapter, unsigned verse,
    unsigned word, int direction, unsigned include_origin);
/* Mark an origin derived from a selection: compare final words for backward
 * search and exclude the current endpoint even after wrapping. */
void BibleSearchUseSelectionOrigin(BibleSearch_t* search);
/* Enable one wrap for the current directional operation; wrapped reports whether
 * the result crossed a Bible boundary. Enable after setting the origin. */
void BibleSearchEnableWrap(BibleSearch_t* search);
/* Nearby means an inclusive total window of 2..99 words; no index change. */
int BibleSearchSetNearbyWords(BibleSearch_t* search, unsigned words);
/* Bounded work; FOUND exposes chapter, first verse/word, and inclusive final
 * verse/word. Words are zero-based in the combined heading/body stream;
 * headings precede their following verse. Both endpoints are in one chapter. */
BibleSearchResult_e BibleSearchStep(BibleSearch_t* search, unsigned budget);

#endif
