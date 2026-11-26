/* Candidate: one exit path handles next-record and end-of-file boundaries. */
static unsigned ParseBoundary(unsigned first, unsigned target, bool by_position, unsigned start, const uint8_t* base) {
    BoundaryStream stream;
    stream.base = base;
    stream.position = start;
    VerseBounds current = {0};
    unsigned verse = first - 1, heading = (unsigned)-1;
    bool in_heading = false;
    for(;;) {
        BoundaryFill(&stream);
        unsigned length = 0;
        unsigned number = stream.available ? BoundaryMarker(&stream, &length) : g_verse_count + 1;
        const uint8_t* bytes = stream.look;
        if(number) {
            unsigned search = stream.available ? (heading != (unsigned)-1 ? heading : stream.position) : g_chapter_file_bytes + 1;
            if(by_position && verse < first && target < search) target = search;
            if(!stream.available || (by_position ? target < search : target < number)) {
                unsigned answer = by_position ? verse : target;
                if(by_position && number > verse + 1 && target >= current.end) answer = number - 1;
                if(answer > verse) current.search = current.start = current.end;
                if(answer < first || answer > g_verse_count) {
                    ReaderProbeSet(error, 710);
                    answer = first;
                }
                g_cached_verse_limit = search;
                g_cached_bounds = current;
                g_cached_verse = answer;
                return answer;
            }
            verse = number;
            if(!by_position) in_heading = false;
            current.search = search;
            current.start = stream.position;
            current.end = stream.position + length;
            heading = (unsigned)-1;
        } else if(stream.available >= 3 && (bytes[0] == VERSE_FONT_BEGIN || bytes[0] == VERSE_FONT_END) && bytes[2] == bytes[0]) {
            length = 3;
            if(bytes[1] == 1 || bytes[1] == 2) {
                in_heading = bytes[0] == VERSE_FONT_BEGIN;
                if(in_heading && heading == (unsigned)-1) heading = stream.position;
            } else if(!in_heading && bytes[0] == VERSE_FONT_END && stream.position == current.end) current.end += 3;
        } else {
            const uint8_t* cursor = bytes;
            const uint8_t* limit = bytes + stream.available;
            if(!by_position && verse < target) {
                while(cursor < limit && *cursor != VERSE_FONT_BEGIN) ++cursor;
            } else {
                while(cursor < limit && *cursor != VERSE_FONT_BEGIN && *cursor != VERSE_FONT_END) ++cursor;
            }
            length = cursor - bytes;
            if(!in_heading && (by_position || verse >= target)) {
                while(cursor > bytes) {
                    unsigned character = cursor[-1];
                    if(character != ' ' && character != '\r' && character != '\n' && character != NATIVE_WRAP_SPACE) {
                        current.end = stream.position + (cursor - bytes);
                        break;
                    }
                    --cursor;
                }
            }
            if(!length) length = 1;
        }
        BoundaryAdvance(&stream, length);
    }
}
