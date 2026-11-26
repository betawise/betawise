/* Exercise the private matcher without adding test entry points to production. */
#include "Search.c"
#include <stdio.h>

const uint8_t BibleGrammarSummary[6144] = {0};

int main(void) {
    BibleSearch_t search;
    unsigned terms;
    unsigned mode;
    unsigned accepted_terms;
    unsigned verse;
    unsigned word;
    memset(&search, 0, sizeof(search));
    if(scanf("%u %u", &terms, &mode) != 2) {
        return 1;
    }
    search.term_count = terms;
    search.match_mode = mode;
    ResetUnorderedMatch(&search);
    while(scanf("%u %u %u", &accepted_terms, &verse, &word) == 3) {
        if(mode == BIBLE_SEARCH_SAME_VERSE && search.verse != verse) {
            ResetUnorderedMatch(&search);
        }
        search.verse = verse;
        search.verse_word_count = word;
        if(AcceptWord(&search, accepted_terms)) {
            printf("%u %u\n", search.verse, search.matched_word);
        }
    }
    return 0;
}
