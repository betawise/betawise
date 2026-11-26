"""Single-pass boundaries: skip body runs and trim only relevant run ends."""
from fast_boundaries import generate as generate_fast


def generate(here):
    text = generate_fast(here).read_text()
    start = text.index('            length = 0;\n            while(length < stream.available')
    stop = text.index('            if(!length) length = 1;', start)
    text = text[:start] + '''            const uint8_t* cursor = bytes;
            const uint8_t* limit = bytes + stream.available;
            while(cursor < limit && *cursor != VERSE_FONT_BEGIN && *cursor != VERSE_FONT_END) ++cursor;
            length = cursor - bytes;
            if(!in_heading && (by_position || verse >= target)) {
                while(cursor > bytes) {
                    unsigned character = cursor[-1];
                    if(character != ' ' && character != '\\r' && character != '\\n' &&
                        character != NATIVE_WRAP_SPACE) {
                        current.end = stream.position + (cursor - bytes);
                        break;
                    }
                    --cursor;
                }
            }
''' + text[stop:]
    output = here / 'build/linear-boundaries.h'
    output.write_text(text)
    return output
