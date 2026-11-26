#ifndef BIBLE_FORMATTING_H
#define BIBLE_FORMATTING_H
#include "Decoder.h"

#define BIBLE_STYLE_ITALIC 1
#define BIBLE_STYLE_BOLD 2
#define BIBLE_STYLE_SMALL_CAPS 4
#define BIBLE_FORMAT_ATOM 0
#define BIBLE_FORMAT_HEADING 1
#define BIBLE_FORMAT_SPACE 2
#define BIBLE_LAYOUT_PARAGRAPH 1
#define BIBLE_LAYOUT_LINE 2
#define BIBLE_LAYOUT_INDENT 4
#define BIBLE_LAYOUT_DOUBLE_INDENT 8
#define BIBLE_LAYOUT_CENTER 16
#define BIBLE_LAYOUT_RIGHT 32
#define BIBLE_LAYOUT_LEFT 64

typedef struct {
    const uint8_t* bible;
    uint32_t bible_size;
} BibleFormatAssets;
typedef struct {
    unsigned kind, style, layout, length;
    const uint8_t* text;
} BibleFormatEvent;
typedef int (*BibleFormatOutput)(void* context, const BibleFormatEvent* event);

/* Event text is borrowed until the callback returns. All scratch is on stack. */
int BibleFormatChapter(const BibleFormatAssets* assets, unsigned chapter,
    BibleFormatOutput output, void* context);
#endif
