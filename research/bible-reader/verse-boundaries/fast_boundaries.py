"""Generate a buffered version of the same boundary parser without per-byte moves."""
from pathlib import Path


def generate(here):
    text=(here/'boundaries.h').read_text()
    start=text.index('typedef struct {\n    uint8_t bytes[256]')
    stop=text.index('static unsigned BoundaryMarker',start)
    text=text[:start]+'''typedef struct {
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

'''+text[stop:]
    old='''        while(stream.available < sizeof(stream.look)) {
            int byte = BoundaryRead(&stream);
            if(byte < 0) break;
            stream.look[stream.available++] = byte;
        }'''
    assert old in text
    text=text.replace(old,'        BoundaryFill(&stream);')
    old='''            length = 1;
            if(!in_heading && verse >= first && bytes[0] != ' ' && bytes[0] != '\\r' &&
                bytes[0] != '\\n' && bytes[0] != NATIVE_WRAP_SPACE) current.end = stream.position + 1;'''
    new='''            length = 0;
            while(length < stream.available && bytes[length] != VERSE_FONT_BEGIN && bytes[length] != VERSE_FONT_END) {
                unsigned character = bytes[length++];
                if(!in_heading && verse >= first && character != ' ' && character != '\\r' &&
                    character != '\\n' && character != NATIVE_WRAP_SPACE) current.end = stream.position + length;
            }
            /* A partial record at physical EOF must still make progress. */
            if(!length) length = 1;'''
    assert old in text
    text=text.replace(old,new)
    output=here/'build/fast-boundaries.h'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(text)
    return output
