#ifndef FORMAT_BENCH_H
#define FORMAT_BENCH_H
#include "Decoder.h"

typedef struct { const uint8_t* data; uint32_t size; } BenchBlob;
typedef struct {
    BenchBlob bible, normalization, font, layout, headings, prediction, layout_defaults;
    unsigned vocabulary_size;
    unsigned inline_data;
    unsigned heading_huffman;
    unsigned heading_shift;
    unsigned headings_inline;
} BenchAssets;
typedef struct {
    unsigned chapter, book, atoms;
    BenchBlob expected_styles, expected_layout, raw_headings;
} BenchCase;
typedef struct {
    uint32_t hash, bytes, atoms, headings, error;
} BenchResult;
/* 0 raw text; 1 predecoded formatting; 2 compressed sidecars; 3 inline controls.
 * The output is a canonical event stream, not a native-editor file. */
int BenchFormatChapter(const BenchAssets* assets, const BenchCase* chapter,
    unsigned mode, unsigned headings, BenchResult* result);
#endif
