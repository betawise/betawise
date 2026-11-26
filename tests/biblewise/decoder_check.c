#include "Decoder.h"
#include <stdio.h>
#include <stdlib.h>

static void Write32(uint32_t value) {
    int shift;
    for(shift = 24; shift >= 0; shift -= 8) {
        putchar(value >> shift);
    }
}

int main(int argc, char** argv) {
    FILE* file;
    long size;
    uint8_t* image;
    BibleDecoder_t decoder;
    int chapter;
    if(argc != 2 || !(file = fopen(argv[1], "rb"))) {
        return 1;
    }
    fseek(file, 0, SEEK_END);
    size = ftell(file);
    rewind(file);
    image = malloc(size);
    if(!image || fread(image, 1, size, file) != (size_t)size) {
        return 2;
    }
    fclose(file);
    if(!BibleDecoderInit(&decoder, image, size)) {
        return 3;
    }
    Write32(decoder.chapter_count);
    for(chapter = decoder.chapter_count - 1; chapter >= 0; --chapter) {
        int character;
        if(!BibleDecoderOpenChapter(&decoder, chapter)) {
            return 4;
        }
        Write32(chapter);
        Write32(ReadBigEndian16(decoder.chapter_records + BIBLE_CHAPTER_RECORD_BYTES * chapter + BIBLE_CHAPTER_SOURCE_BYTES_OFFSET));
        while((character = BibleDecoderReadByte(&decoder)) >= 0) {
            putchar(character);
        }
        if(character != -1) {
            return 5;
        }
    }
    free(image);
    return 0;
}
