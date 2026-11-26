#include "Search.h"
#include <stdio.h>
#include <stdlib.h>

static uint8_t* LoadFile(const char* path, uint32_t* size) {
    FILE* file = fopen(path, "rb");
    uint8_t* data;
    if(!file) {
        exit(1);
    }
    fseek(file, 0, SEEK_END);
    *size = ftell(file);
    rewind(file);
    data = malloc(*size + 1);
    if(!data || fread(data, 1, *size, file) != *size) {
        exit(1);
    }
    fclose(file);
    return data;
}

int main(int argc, char** argv) {
    uint32_t bible_size;
    uint32_t index_size;
    uint8_t* bible = LoadFile(argv[1], &bible_size);
    uint8_t* index = LoadFile(argv[2], &index_size);
    BibleSearch_t search;
    BibleSearchResult_e result;
    if(!BibleSearchBegin(&search, bible, bible_size, index, index_size, argv[3], atoi(argv[4]))) {
        return 2;
    }
    if(argc > 11 && !BibleSearchSetNearbyWords(&search, atoi(argv[11]))) return 2;
    if(argc > 5) {
        BibleSearchSetOrigin(&search, atoi(argv[5]), atoi(argv[6]), atoi(argv[7]),
            atoi(argv[8]), atoi(argv[9]));
    }
    if(argc > 12 && atoi(argv[12])) BibleSearchUseSelectionOrigin(&search);
    if(argc > 10 && atoi(argv[10])) BibleSearchEnableWrap(&search);
    while((result = BibleSearchStep(&search, 7)) != BIBLE_SEARCH_COMPLETE) {
        if(result == BIBLE_SEARCH_ERROR) {
            return 3;
        }
        if(result == BIBLE_SEARCH_FOUND) {
            if(argc > 10) printf("%u %u %u %u\n", search.chapter, search.verse,
                search.matched_word, search.wrapped);
            else printf("%u %u %u\n", search.chapter, search.verse, search.matched_word);
            if(argc > 5) {
                break;
            }
        }
    }
    free(bible);
    free(index);
    return 0;
}
