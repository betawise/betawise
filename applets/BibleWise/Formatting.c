#include "Formatting.h"

#define ATOM_BYTES 64
#define NO_LAYOUT 65535

/* Formatting controls are atomic dictionary terminals: 02, 10|style, layout+1.
 * Text and controls share the chapter's grammar/Huffman stream. All working
 * state is local; missing font faces affect rendering, never source metadata. */
int BibleFormatChapter(const BibleFormatAssets* assets, unsigned chapter,
    BibleFormatOutput output, void* context) {
    BibleDecoder_t decoder;
    uint8_t atom_text[ATOM_BYTES], heading[256];
    unsigned length = 0, style = 0, layout = NO_LAYOUT, first = 1;
    unsigned default_layout;
    int character;
    BibleFormatEvent event;
    if(!BibleDecoderInit(&decoder, assets->bible, assets->bible_size) ||
        !BibleDecoderOpenChapter(&decoder, chapter)) return 0;
    default_layout = assets->bible[BIBLE_DEFAULT_LAYOUT_OFFSET];
    for(;;) {
        character = BibleDecoderReadByte(&decoder);
        if(length && (character < 0 || character == BIBLE_INLINE_FORMAT ||
            character == 3 || character == ' ' || character == '\n')) {
            event.kind = BIBLE_FORMAT_ATOM;
            event.style = style;
            event.layout = layout != NO_LAYOUT ? layout : first ? default_layout : 0;
            event.text = atom_text;
            event.length = length;
            if(!output(context, &event)) return 0;
            length = 0;
            layout = NO_LAYOUT;
            first = 0;
        }
        if(character == BIBLE_INLINE_FORMAT) {
            int state = BibleDecoderReadByte(&decoder);
            int next_layout = BibleDecoderReadByte(&decoder);
            if(state < 16 || state > 23 || next_layout < 1 || next_layout > 127) return 0;
            style = state & 7;
            layout = next_layout - 1;
        } else if(character == 3) {
            int level = BibleDecoderReadByte(&decoder);
            unsigned size = 0;
            if(level < 16 || level >= 32) return 0;
            while((character = BibleDecoderReadByte(&decoder)) >= 0 && character != 4) {
                if(size == sizeof(heading)) return 0;
                heading[size++] = character;
            }
            if(character != 4) return 0;
            event.kind = BIBLE_FORMAT_HEADING;
            event.style = BIBLE_STYLE_BOLD;
            event.layout = level & 15;
            event.text = heading;
            event.length = size;
            if(!output(context, &event)) return 0;
        } else if(character == ' ' || character == '\n') {
            event.kind = BIBLE_FORMAT_SPACE;
            event.style = event.layout = 0;
            event.text = atom_text;
            atom_text[0] = character;
            event.length = 1;
            if(!output(context, &event)) return 0;
            if(character == '\n') first = 1;
        } else if(character < 0) {
            break;
        } else {
            if((!IsBibleQuote(character) && (character < 32 || character > 126)) ||
                length == sizeof(atom_text)) return 0;
            atom_text[length++] = character;
        }
    }
    return character == -1 && !decoder.error;
}
