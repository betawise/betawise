/* Research-only boundary reconstruction from the existing native chapter file. */
#define BOUNDARY_STRIDE RESEARCH_BOUNDARY_STRIDE
#define BOUNDARY_INDEX_COUNT ((BIBLE_MAX_CHAPTER_VERSES + BOUNDARY_STRIDE - 1) / BOUNDARY_STRIDE)
typedef struct { uint16_t search, start, end; } VerseBounds;
#ifndef RESEARCH_BOUNDARY_NONE
static uint16_t g_boundary_index[BOUNDARY_INDEX_COUNT];
#endif
static VerseBounds g_boundary_cache;
static uint16_t g_boundary_cache_verse;
#if BOUNDARY_STRIDE > 1
static uint16_t g_boundary_cache_limit;
#endif

typedef struct {
    uint8_t bytes[256];
    const uint8_t* look;
    unsigned position, loaded, cursor, count, available;
    bool failed;
} BoundaryStream;

static void BoundaryFill(BoundaryStream* stream) {
    unsigned remaining = stream->count - stream->cursor;
    if(remaining < 15 && stream->loaded < g_chapter_file_bytes) {
        if(remaining) memmove(stream->bytes, stream->bytes + stream->cursor, remaining);
        stream->count = remaining;
        stream->cursor = 0;
        while(stream->count < sizeof(stream->bytes) && stream->loaded < g_chapter_file_bytes) {
            unsigned raw = stream->loaded, count = g_chapter_file_bytes - stream->loaded;
            if(count > sizeof(stream->bytes) - stream->count) count = sizeof(stream->bytes) - stream->count;
            if(raw < g_editor.gap_start && count > g_editor.gap_start - raw) count = g_editor.gap_start - raw;
            if(raw >= g_editor.gap_start) raw += g_editor.gap_end - g_editor.gap_start;
            if(FileSeek(READER_FILE, raw, FILE_SEEK_START) < 0 ||
                FileReadBuffer(READER_FILE, stream->bytes + stream->count, count) != (int)count) {
                stream->failed = true;
                break;
            }
            stream->loaded += count;
            stream->count += count;
        }
    }
    stream->look = stream->bytes + stream->cursor;
    stream->available = stream->count - stream->cursor;
}

static void BoundaryAdvance(BoundaryStream* stream, unsigned count) {
    stream->position += count;
    stream->cursor += count;
}

static unsigned BoundaryMarker(const BoundaryStream* stream, unsigned* length) {
    const uint8_t* bytes = stream->look;
    if(stream->available < 13 || bytes[0] != VERSE_FONT_BEGIN || bytes[1] != VERSE_FONT_FACE_FLAGS ||
        bytes[2] != VERSE_FONT_BEGIN || bytes[3] != VERSE_FONT_BEGIN ||
        (bytes[4] != 1 && bytes[4] != 2) || bytes[5] != VERSE_FONT_BEGIN) return 0;
    unsigned index = 6, number = 0;
    while(index < 9 && bytes[index] >= '0' && bytes[index] <= '9') number = number * 10 + bytes[index++] - '0';
    if(index == 6 || index + 6 > stream->available || bytes[index] != VERSE_FONT_END ||
        bytes[index+1] != bytes[4] || bytes[index+2] != VERSE_FONT_END ||
        bytes[index+3] != VERSE_FONT_END || bytes[index+4] != VERSE_FONT_FACE_FLAGS ||
        bytes[index+5] != VERSE_FONT_END) return 0;
    *length = index + 6;
    return number;
}

static unsigned ParseBoundary(unsigned first, unsigned target, bool by_position, unsigned start) {
    BoundaryStream stream;
    stream.cursor = stream.count = 0;
    stream.failed = false;
    VerseBounds current = {0};
    stream.position = stream.loaded = start;
    unsigned verse = first - 1, heading = 0;
    bool in_heading = false, pending_heading = false;
#ifndef RESEARCH_BOUNDARY_NONE
    stream.position = stream.loaded = g_boundary_index[(first - 1) / BOUNDARY_STRIDE];
#endif
    unsigned answer = first;
    for(;;) {
        BoundaryFill(&stream);
        if(!stream.available) break;
        unsigned length = 0, number = BoundaryMarker(&stream, &length);
        const uint8_t* bytes = stream.look;
        if(number) {
            unsigned search = pending_heading ? heading : stream.position;
            if(by_position && verse < first && target < search) target = search;
            if((by_position && target < search) || (!by_position && target < number)) {
                answer = verse;
                if((!by_position && target > verse) ||
                    (by_position && number > verse + 1 && target >= current.end)) {
                    answer = by_position ? number - 1 : target;
                    current.search = current.start = current.end;
                }
#if BOUNDARY_STRIDE > 1
                g_boundary_cache_limit = search;
#endif
                goto found;
            }
            verse = number;
            if(!by_position) in_heading = false;
            current.search = search;
            current.start = stream.position;
            current.end = stream.position + length;
            pending_heading = false;
        } else if(stream.available >= 3 && (bytes[0] == VERSE_FONT_BEGIN || bytes[0] == VERSE_FONT_END) && bytes[2] == bytes[0]) {
            length = 3;
            if(bytes[1] == 1 || bytes[1] == 2) {
                in_heading = bytes[0] == VERSE_FONT_BEGIN;
                if(in_heading && !pending_heading) { heading = stream.position; pending_heading = true; }
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
                    if(character != ' ' && character != '\r' && character != '\n' &&
                        character != NATIVE_WRAP_SPACE) {
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
#if BOUNDARY_STRIDE > 1
    g_boundary_cache_limit = g_chapter_file_bytes + 1;
#endif
    answer = verse;
    if((!by_position && target > verse) || (by_position && verse < g_verse_count && target >= current.end)) {
        answer = by_position ? g_verse_count : target;
        current.search = current.start = current.end;
    }
found:
    if(stream.failed || answer < first || answer > g_verse_count) {
        ReaderProbeSet(error, 710);
        answer = first;
    }
    g_boundary_cache = current;
    g_boundary_cache_verse = answer;
    return answer;
}


#include "tiny_binary_seek.h"
