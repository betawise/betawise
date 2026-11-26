#include "Formatting.h"
#include <stdio.h>
#include <stdlib.h>

static uint8_t* Load(const char* directory, const char* name, unsigned* size) {
    char path[1024]; FILE* file; uint8_t* bytes;
    snprintf(path, sizeof(path), "%s/%s", directory, name);
    file = fopen(path, "rb"); if(!file) exit(2);
    fseek(file, 0, SEEK_END); *size = ftell(file); rewind(file);
    bytes = malloc(*size + 2); if(!bytes || fread(bytes, 1, *size, file) != *size) exit(3);
    bytes[*size] = bytes[*size + 1] = 0; fclose(file); return bytes;
}
static int Output(void* context, const BibleFormatEvent* event) {
    unsigned i; (void)context;
    putchar(event->kind); putchar(event->style); putchar(event->layout);
    putchar(event->length >> 8); putchar(event->length);
    for(i = 0; i < event->length; ++i) putchar(event->text[i]);
    return 1;
}
int main(int argc, char** argv) {
    BibleFormatAssets assets; unsigned chapter = 0, book;
    static const unsigned chapters[] = {50,40,27,36,34,24,21,4,31,24,22,25,29,36,10,13,10,42,150,31,12,8,66,52,5,48,12,14,3,9,1,4,7,3,3,3,2,14,4,28,16,24,21,28,16,16,13,6,6,4,4,5,3,6,4,3,1,13,5,5,3,5,1,1,1,22};
    if(argc != 2) return 1;
    assets.bible = Load(argv[1], "container.bin", &assets.bible_size);
    for(book = 0; book < 66; ++book) {
        unsigned i;
        for(i = 0; i < chapters[book]; ++i, ++chapter) {
            if(!BibleFormatChapter(&assets, chapter, Output, NULL)) return 4;
            putchar(255);
        }
    }
    free((void*)assets.bible);
    return 0;
}
