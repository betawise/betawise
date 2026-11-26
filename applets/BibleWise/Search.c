#include "Search.h"
#include <string.h>

extern const uint8_t BibleGrammarSummary[];

#define NORMALIZED_VERSE_END 65534
#define NORMALIZED_PUNCTUATION 65535
#define POSTINGS_DELTA 0
#define POSTINGS_ELIAS_FANO 1
#define POSTINGS_BITMAP 2
#define POSTINGS_COMPLEMENT_DELTA 3
#define POSTINGS_COMPLEMENT_ELIAS_FANO 4
#define VOCABULARY_COMPARE_ERROR -32768

static unsigned ReadBit(const uint8_t* bytes, unsigned bit) {
    return (bytes[bit / 8] >> (bit & 7)) & 1;
}

static uint16_t ReadNormalizedWord(BibleSearch_t* search, unsigned terminal) {
    unsigned bit = 14u * terminal;
    const uint8_t* bytes = search->normalization_map + bit / 8;
    uint32_t packed = ((uint32_t)bytes[0] << 16) | ((uint32_t)bytes[1] << 8) | bytes[2];
    uint16_t word = (packed >> (10 - (bit & 7))) & 16383;
    if(word == search->vocabulary_size) {
        return NORMALIZED_VERSE_END;
    }
    if(word == search->vocabulary_size + 1) {
        return NORMALIZED_PUNCTUATION;
    }
    return word;
}

static unsigned ReadCanonicalTerminal(BibleSearch_t* search, unsigned word) {
    return ReadBigEndian32(search->vocabulary_records + 4u * word) >> 18;
}

static uint32_t ReadPostingOffset(BibleSearch_t* search, unsigned word) {
    return ReadBigEndian32(search->vocabulary_records + 4u * word) & 262143;
}

static void SetCandidateChapter(uint8_t* chapters, unsigned chapter, unsigned clear) {
    if(clear) {
        chapters[chapter / 8] &= ~(1 << (chapter & 7));
    } else {
        chapters[chapter / 8] |= 1 << (chapter & 7);
    }
}

/* Each word uses the smallest of delta, Elias-Fano, bitmap or complement lists.
 * This is one packed index format, not selectable alternative index policies. */
static int ReadWordPostings(BibleSearch_t* search, unsigned word, uint8_t* chapters) {
    const uint8_t* cursor = search->postings + ReadPostingOffset(search, word);
    const uint8_t* end = search->postings + ReadPostingOffset(search, word + 1);
    unsigned encoding;
    unsigned complement;
    int32_t chapter = -1;

    if(cursor >= end || end > search->index_end) {
        return 0;
    }
    encoding = *cursor++;
    if(encoding > POSTINGS_COMPLEMENT_ELIAS_FANO) {
        return 0;
    }
    complement = encoding >= POSTINGS_COMPLEMENT_DELTA;
    memset(chapters, complement ? 255 : 0, BIBLE_SEARCH_CHAPTER_BYTES);
    if(encoding == POSTINGS_BITMAP) {
        if(end - cursor != BIBLE_SEARCH_CHAPTER_BYTES) {
            return 0;
        }
        memcpy(chapters, cursor, BIBLE_SEARCH_CHAPTER_BYTES);
        return 1;
    }
    if(encoding == POSTINGS_ELIAS_FANO || encoding == POSTINGS_COMPLEMENT_ELIAS_FANO) {
        unsigned count;
        unsigned low_bits;
        unsigned low_bit_count;
        unsigned item = 0;
        unsigned bit;
        if(end - cursor < 3) {
            return 0;
        }
        count = ReadBigEndian16(cursor);
        low_bits = cursor[2];
        cursor += 3;
        if(low_bits > 10 || count > BIBLE_CHAPTER_COUNT) {
            return 0;
        }
        low_bit_count = count * low_bits;
        for(bit = low_bit_count; bit < (unsigned)(end - cursor) * 8 && item < count; ++bit) {
            if(ReadBit(cursor, bit)) {
                unsigned low_bit;
                unsigned value = 0;
                for(low_bit = 0; low_bit < low_bits; ++low_bit) {
                    value |= ReadBit(cursor, item * low_bits + low_bit) << low_bit;
                }
                value |= (bit - low_bit_count - item) << low_bits;
                if(value >= BIBLE_CHAPTER_COUNT) {
                    return 0;
                }
                SetCandidateChapter(chapters, value, complement);
                ++item;
            }
        }
        return item == count;
    }
    while(cursor < end) {
        uint32_t delta = 0;
        unsigned shift = 0;
        unsigned next_byte;
        do {
            if(cursor == end || shift > 21) {
                return 0;
            }
            next_byte = *cursor++;
            delta |= (uint32_t)(next_byte & 127) << shift;
            shift += 7;
        } while(next_byte & 128);
        if(!delta || delta > BIBLE_CHAPTER_COUNT) {
            return 0;
        }
        chapter += delta;
        if(chapter >= BIBLE_CHAPTER_COUNT) {
            return 0;
        }
        SetCandidateChapter(chapters, chapter, complement);
    }
    return 1;
}

static int CompareVocabularyWord(BibleSearch_t* search, unsigned word,
    const char* query_word, unsigned prefix) {
    char spelling[BIBLE_MAX_WORD_BYTES];
    unsigned spelling_offset = 0;
    unsigned query_offset = 0;
    if(!BibleDecoderGetWord(&search->decoder, ReadCanonicalTerminal(search, word),
        spelling, sizeof(spelling))) {
        return VOCABULARY_COMPARE_ERROR;
    }
    if(spelling[0] == ' ') {
        ++spelling_offset;
    }
    while(spelling[spelling_offset] && query_word[query_offset]) {
        int difference = (unsigned char)query_word[query_offset] -
            (int)LowercaseBibleLetter(spelling[spelling_offset]);
        if(difference) {
            return difference;
        }
        ++spelling_offset;
        ++query_offset;
    }
    if(prefix && !query_word[query_offset]) {
        return 0;
    }
    return (unsigned char)query_word[query_offset] -
        (int)LowercaseBibleLetter(spelling[spelling_offset]);
}

/* All completions of a prefix occupy a contiguous normalized vocabulary range. */
static uint32_t FindVocabularyBound(BibleSearch_t* search, const char* word,
    unsigned prefix, unsigned upper_bound) {
    uint32_t first = 0;
    uint32_t end = search->vocabulary_size;
    while(first < end) {
        uint32_t middle = (first + end) / 2;
        int comparison = CompareVocabularyWord(search, middle, word, prefix);
        if(comparison == VOCABULARY_COMPARE_ERROR) {
            return UINT32_MAX;
        }
        if(comparison > 0 || (upper_bound && !comparison)) {
            first = middle + 1;
        } else {
            end = middle;
        }
    }
    return first;
}

static int FilterCandidateChapters(BibleSearch_t* search, unsigned term,
    const char* word, unsigned prefix) {
    uint32_t first = FindVocabularyBound(search, word, prefix, 0);
    uint32_t end = FindVocabularyBound(search, word, prefix, 1);
    uint8_t matching_chapters[BIBLE_SEARCH_CHAPTER_BYTES];
    uint8_t word_chapters[BIBLE_SEARCH_CHAPTER_BYTES];
    unsigned word_id;
    unsigned byte;

    if(first == UINT32_MAX || end == UINT32_MAX) {
        return 0;
    }
    search->term_first[term] = first;
    search->term_end[term] = end;
    memset(matching_chapters, 0, sizeof(matching_chapters));
    for(word_id = first; word_id < end; ++word_id) {
        if(!ReadWordPostings(search, word_id, word_chapters)) {
            return 0;
        }
        for(byte = 0; byte < sizeof(matching_chapters); ++byte) {
            matching_chapters[byte] |= word_chapters[byte];
        }
    }
    for(byte = 0; byte < sizeof(matching_chapters); ++byte) {
        search->candidate_chapters[byte] &= matching_chapters[byte];
    }
    return 1;
}

static unsigned AcceptedTerms(BibleSearch_t* search, unsigned word) {
    unsigned term;
    unsigned accepted = 0;
    for(term = 0; term < search->term_count; ++term) {
        if(word >= search->term_first[term] && word < search->term_end[term]) {
            accepted |= 1u << term;
        }
    }
    return accepted;
}

static void BuildGrammarFilter(BibleSearch_t* search) {
    unsigned rule;
    unsigned terminals = search->decoder.dictionary_word_count;
    for(rule = 0; rule < search->decoder.grammar_rule_count; ++rule) {
        const uint8_t* children = search->decoder.grammar_rules + 4u * rule;
        unsigned child;
        unsigned matches = 0;
        for(child = 0; child < 2; ++child) {
            unsigned symbol = ReadBigEndian16(children + 2 * child);
            if(symbol >= terminals) {
                matches |= ReadBit(search->matching_rules, symbol - terminals);
            } else {
                unsigned word = ReadNormalizedWord(search, symbol);
                if(search->match_mode == BIBLE_SEARCH_PHRASE) {
                    matches |= word >= search->term_first[0] && word < search->term_end[0];
                } else {
                    matches |= AcceptedTerms(search, word);
                }
            }
        }
        if(matches) {
            search->matching_rules[rule / 8] |= 1 << (rule & 7);
        }
    }
}

/* Only initialization needs spellings and wildcard flags. Ongoing searches
 * retain vocabulary ranges, candidate chapters and grammar pruning instead. */
typedef struct {
    char query[BIBLE_SEARCH_QUERY_BYTES];
    uint8_t term_offsets[BIBLE_SEARCH_MAX_TERMS];
    uint16_t prefix_terms;
} SearchPreparation;

static int ParseQuery(BibleSearch_t* search, const char* query, SearchPreparation* preparation) {
    unsigned input = 0;
    unsigned output = 0;
    while(query[input]) {
        while(query[input] && !IsBibleLetter(query[input])) {
            if(query[input] == '*') {
                return 0;
            }
            ++input;
        }
        if(!query[input]) {
            break;
        }
        if(search->term_count == BIBLE_SEARCH_MAX_TERMS) {
            return 0;
        }
        preparation->term_offsets[search->term_count++] = output;
        while(IsBibleLetter(query[input]) || (IsBibleApostrophe(query[input]) &&
            output > preparation->term_offsets[search->term_count - 1] &&
            IsBibleLetter(query[input + 1]))) {
            if(output >= sizeof(preparation->query) - 2) {
                return 0;
            }
            preparation->query[output++] = LowercaseBibleLetter(query[input++]);
        }
        if(query[input] == '*') {
            preparation->prefix_terms |= 1u << (search->term_count - 1);
            ++input;
            if(IsBibleLetter(query[input]) || query[input] == '*' || IsBibleApostrophe(query[input])) {
                return 0;
            }
        }
        preparation->query[output++] = 0;
    }
    return search->term_count != 0;
}

int BibleSearchBegin(BibleSearch_t* search, const uint8_t* bible, uint32_t bible_size,
    const uint8_t* index, uint32_t index_size, const char* query, BibleSearchMode_e mode) {
    unsigned terminals;
    unsigned term;
    uint32_t posting_size;
    SearchPreparation preparation = {0};

    memset(search, 0, sizeof(*search));
    search->verse = 1;
    search->match_mode = mode;
    search->chapter_limit = BIBLE_CHAPTER_COUNT;
    if(mode > BIBLE_SEARCH_NEARBY || !BibleDecoderInit(&search->decoder, bible, bible_size) ||
        index_size < 20 || memcmp(index, "IDXEXP02", 8) || ReadBigEndian32(index + 12) != 1) {
        return 0;
    }
    search->vocabulary_size = ReadBigEndian16(index + 8);
    terminals = ReadBigEndian16(index + 10);
    posting_size = ReadBigEndian32(index + 16);
    if(search->vocabulary_size + 2 >= 16384 || terminals != search->decoder.dictionary_word_count) {
        return 0;
    }
    search->vocabulary_records = index + 20;
    search->index_end = index + index_size;
    search->normalization_map = search->vocabulary_records + 4u * (search->vocabulary_size + 1);
    search->postings = search->normalization_map + (14u * terminals + 7) / 8;
    if(search->postings > search->index_end || (uint32_t)(search->index_end - search->postings) != posting_size) {
        return 0;
    }
    memset(search->candidate_chapters, 255, sizeof(search->candidate_chapters));
    if(!ParseQuery(search, query, &preparation)) {
        return 0;
    }
    for(term = 0; term < search->term_count; ++term) {
        if(!FilterCandidateChapters(search, term,
            preparation.query + preparation.term_offsets[term],
            (preparation.prefix_terms >> term) & 1)) {
            return 0;
        }
    }
    BuildGrammarFilter(search);
    return 1;
}

static void ResetUnorderedMatch(BibleSearch_t* search) {
    search->assigned_count = search->verse_already_reported = 0;
    search->reported_position = UINT32_MAX;
    memset(search->assigned_occurrences, 0, sizeof(search->assigned_occurrences));
}

/* Alternating paths give each term a distinct occurrence. Retaining the newest
 * independent occurrences also handles nested prefixes such as "be* bel*". */
static int AssignOccurrence(BibleSearch_t* search, unsigned accepted_terms,
    unsigned verse, unsigned word, uint32_t position, unsigned* visited_terms) {
    unsigned term;
    for(term = 0; term < search->term_count; ++term) {
        BibleSearchOccurrence_t* assigned = search->assigned_occurrences + term;
        if((accepted_terms & (1u << term)) && !(*visited_terms & (1u << term))) {
            *visited_terms |= 1u << term;
            if(!assigned->accepted_terms || AssignOccurrence(search, assigned->accepted_terms,
                assigned->verse, assigned->word, assigned->position, visited_terms)) {
                assigned->accepted_terms = accepted_terms;
                assigned->verse = verse;
                assigned->word = word;
                assigned->position = position;
                return 1;
            }
        }
    }
    return 0;
}

static int AcceptWord(BibleSearch_t* search, unsigned accepted_terms) {
    unsigned term;
    unsigned visited_terms = 0;
    unsigned oldest_term = BIBLE_SEARCH_MAX_TERMS;
    uint32_t position = search->word_position++;
    ++search->verse_word_count;

    if(search->match_mode == BIBLE_SEARCH_PHRASE) {
        search->phrase_state = ((search->phrase_state << 1) | 1) & accepted_terms;
        if(search->phrase_state & (1u << (search->term_count - 1))) {
            search->matched_word = search->verse_word_count - search->term_count;
            search->matched_end_verse = search->verse;
            search->matched_end_word = search->verse_word_count - 1;
            return 1;
        }
        return 0;
    }
    if(search->verse_already_reported) {
        return 0;
    }
    if(search->match_mode == BIBLE_SEARCH_NEARBY) {
        for(term = 0; term < search->term_count; ++term) {
            BibleSearchOccurrence_t* assigned = search->assigned_occurrences + term;
            if(assigned->accepted_terms && position - assigned->position >= (search->nearby_words ? search->nearby_words : BIBLE_SEARCH_NEAR_WORDS)) {
                assigned->accepted_terms = 0;
                --search->assigned_count;
            }
        }
    }
    if(!accepted_terms) {
        return 0;
    }
    if(AssignOccurrence(search, accepted_terms, search->verse,
        search->verse_word_count - 1, position, &visited_terms)) {
        ++search->assigned_count;
    } else {
        for(term = 0; term < search->term_count; ++term) {
            if((visited_terms & (1u << term)) && (oldest_term == BIBLE_SEARCH_MAX_TERMS ||
                search->assigned_occurrences[term].position <
                search->assigned_occurrences[oldest_term].position)) {
                oldest_term = term;
            }
        }
        if(oldest_term < BIBLE_SEARCH_MAX_TERMS) {
            search->assigned_occurrences[oldest_term].accepted_terms = 0;
            visited_terms = 0;
            if(!AssignOccurrence(search, accepted_terms, search->verse,
                search->verse_word_count - 1, position, &visited_terms)) {
                return 0;
            }
        }
    }
    if(search->assigned_count < search->term_count) {
        return 0;
    }
    oldest_term = 0;
    for(term = 1; term < search->term_count; ++term) {
        if(search->assigned_occurrences[term].position <
            search->assigned_occurrences[oldest_term].position) {
            oldest_term = term;
        }
    }
    uint32_t first_position = search->assigned_occurrences[oldest_term].position;
    if(search->match_mode == BIBLE_SEARCH_NEARBY && first_position == search->reported_position) {
        return 0;
    }
    search->reported_position = first_position;
    search->matched_end_verse = search->verse;
    search->matched_end_word = search->verse_word_count - 1;
    search->matched_word = search->assigned_occurrences[oldest_term].word;
    search->resume_verse = search->verse;
    search->verse = search->assigned_occurrences[oldest_term].verse;
    search->restore_scan_verse = 1;
    if(search->match_mode != BIBLE_SEARCH_NEARBY) {
        ResetUnorderedMatch(search);
    }
    if(search->match_mode == BIBLE_SEARCH_SAME_VERSE) {
        search->verse_already_reported = 1;
    }
    return 1;
}

static BibleSearchResult_e ReadNextMatch(BibleSearch_t* search, unsigned budget) {
    if(search->restore_scan_verse) {
        search->verse = search->resume_verse;
        search->restore_scan_verse = 0;
    }
    if(search->complete) {
        return BIBLE_SEARCH_COMPLETE;
    }
    while(budget--) {
        int terminal;
        uint16_t word;
        if(!search->chapter_open) {
            while(search->chapter < search->chapter_limit &&
                !ReadBit(search->candidate_chapters, search->chapter)) {
                ++search->chapter;
            }
            if(search->chapter >= search->chapter_limit) {
                search->complete = 1;
                return BIBLE_SEARCH_COMPLETE;
            }
            if(!BibleDecoderOpenChapter(&search->decoder, search->chapter)) {
                return BIBLE_SEARCH_ERROR;
            }
            search->chapter_open = 1;
            search->verse = 1;
            search->phrase_state = search->verse_word_count = 0;
            search->word_position = 0;
            ResetUnorderedMatch(search);
        }
        terminal = BibleDecoderReadNode(&search->decoder);
        if(terminal >= search->decoder.dictionary_word_count) {
            unsigned rule = terminal - search->decoder.dictionary_word_count;
            if((search->match_mode != BIBLE_SEARCH_PHRASE || !search->phrase_state) &&
                !ReadBit(search->matching_rules, rule)) {
                const uint8_t* summary = BibleGrammarSummary + 3u * rule;
                search->word_position += summary[0];
                search->verse += summary[1];
                search->verse_word_count = summary[1] ? summary[2] :
                    search->verse_word_count + summary[0];
                if(summary[1] && search->match_mode == BIBLE_SEARCH_SAME_VERSE) {
                    ResetUnorderedMatch(search);
                }
                continue;
            }
            if(!BibleDecoderExpandRule(&search->decoder, terminal)) {
                return BIBLE_SEARCH_ERROR;
            }
            continue;
        }
        if(terminal < -1) {
            return BIBLE_SEARCH_ERROR;
        }
        if(terminal == -1) {
            search->chapter_open = 0;
            ++search->chapter;
            continue;
        }
        word = ReadNormalizedWord(search, terminal);
        if(word == NORMALIZED_VERSE_END) {
            ++search->verse;
            search->verse_word_count = search->phrase_state = 0;
            if(search->match_mode == BIBLE_SEARCH_SAME_VERSE) {
                ResetUnorderedMatch(search);
            }
            continue;
        }
        if(word != NORMALIZED_PUNCTUATION && AcceptWord(search, AcceptedTerms(search, word))) {
            return BIBLE_SEARCH_FOUND;
        }
    }
    return BIBLE_SEARCH_PENDING;
}

static int CompareLocation(unsigned chapter, unsigned verse, unsigned word,
    const BibleSearchLocation_t* location) {
    if(chapter != location->chapter) {
        return chapter < location->chapter ? -1 : 1;
    }
    if(verse != location->verse) {
        return verse < location->verse ? -1 : 1;
    }
    return word < location->word ? -1 : word > location->word;
}

void BibleSearchSetOrigin(BibleSearch_t* search, unsigned chapter, unsigned verse,
    unsigned word, int direction, unsigned include_origin) {
    unsigned reuse_decoder = direction > 0 && search->has_origin && search->direction > 0 &&
        !search->complete && search->chapter == chapter && search->verse == verse &&
        search->matched_word == word && !include_origin;

    search->wrap_enabled = search->wrapped = 0;
    search->origin.chapter = chapter;
    search->origin.verse = verse;
    search->origin.word = word;
    search->direction = direction < 0 ? -1 : 1;
    search->include_origin = !!include_origin;
    search->selection_origin = 0;
    search->has_origin = 1;
    search->previous_match_valid = 0;
    search->chapter_limit = direction < 0 ? chapter + 1 : BIBLE_CHAPTER_COUNT;
    search->backward_chapter = chapter;
    if(!reuse_decoder) {
        search->chapter = chapter;
        search->chapter_open = search->complete = search->restore_scan_verse = 0;
    }
}

void BibleSearchUseSelectionOrigin(BibleSearch_t* search) {
    search->selection_origin = 1;
}

static int CompareMatchToLocation(const BibleSearch_t* search, const BibleSearchLocation_t* location) {
    unsigned final_word = search->direction < 0 && search->selection_origin;
    return CompareLocation(search->chapter,
        final_word ? search->matched_end_verse : search->verse,
        final_word ? search->matched_end_word : search->matched_word, location);
}

static BibleSearchResult_e ReadDirectionalMatch(BibleSearch_t* search, unsigned budget) {
    if(!search->has_origin) {
        return ReadNextMatch(search, budget);
    }
    if(search->complete) {
        return BIBLE_SEARCH_COMPLETE;
    }
    while(budget--) {
        BibleSearchResult_e result = ReadNextMatch(search, 1);
        int comparison;
        if(result == BIBLE_SEARCH_ERROR) {
            return result;
        }
        if(result == BIBLE_SEARCH_FOUND) {
            comparison = CompareMatchToLocation(search, &search->origin);
            if(search->direction > 0) {
                if(comparison > 0 || (!comparison && search->include_origin)) {
                    return result;
                }
            } else if(comparison < 0 || (!comparison && search->include_origin)) {
                search->previous_match.chapter = search->chapter;
                search->previous_match.verse = search->verse;
                search->previous_match.word = search->matched_word;
                search->previous_match_end.verse = search->matched_end_verse;
                search->previous_match_end.word = search->matched_end_word;
                search->previous_match_valid = 1;
            } else {
                result = BIBLE_SEARCH_COMPLETE;
            }
        }
        if(result == BIBLE_SEARCH_COMPLETE) {
            if(search->direction > 0) {
                return result;
            }
            if(search->previous_match_valid) {
                search->chapter = search->previous_match.chapter;
                search->verse = search->previous_match.verse;
                search->matched_word = search->previous_match.word;
                search->matched_end_verse = search->previous_match_end.verse;
                search->matched_end_word = search->previous_match_end.word;
                search->complete = 1;
                return BIBLE_SEARCH_FOUND;
            }
            if(!search->backward_chapter) {
                search->complete = 1;
                return BIBLE_SEARCH_COMPLETE;
            }
            search->chapter = --search->backward_chapter;
            search->chapter_limit = search->chapter + 1;
            search->chapter_open = search->complete = search->restore_scan_verse = 0;
        }
    }
    return BIBLE_SEARCH_PENDING;
}

void BibleSearchEnableWrap(BibleSearch_t* search) {
    search->wrap_enabled = 1;
    search->wrapped = 0;
    search->wrap_origin = search->origin;
}

int BibleSearchSetNearbyWords(BibleSearch_t* search, unsigned words) {
    if(words < 2 || words > 99) return 0;
    search->nearby_words = words;
    return 1;
}

BibleSearchResult_e BibleSearchStep(BibleSearch_t* search, unsigned budget) {
    BibleSearchResult_e result = ReadDirectionalMatch(search, budget);
    if(!search->wrap_enabled || !search->has_origin) return result;
    if(result == BIBLE_SEARCH_COMPLETE && !search->wrapped) {
        BibleSearchLocation_t origin = search->wrap_origin;
        int direction = search->direction;
        unsigned selection_origin = search->selection_origin;
        if(direction > 0) BibleSearchSetOrigin(search, 0, 1, 0, direction, 1);
        else BibleSearchSetOrigin(search, BIBLE_CHAPTER_COUNT - 1,
            UINT16_MAX, UINT16_MAX, direction, 1);
        search->selection_origin = selection_origin;
        search->wrap_origin = origin;
        search->wrap_enabled = search->wrapped = 1;
        return BIBLE_SEARCH_PENDING;
    }
    if(result == BIBLE_SEARCH_FOUND && search->wrapped) {
        int comparison = CompareMatchToLocation(search, &search->wrap_origin);
        if((search->direction > 0 && (comparison > 0 || (!comparison && search->selection_origin))) ||
            (search->direction < 0 && (comparison < 0 || (!comparison && search->selection_origin)))) {
            search->complete = 1;
            return BIBLE_SEARCH_COMPLETE;
        }
    }
    return result;
}
