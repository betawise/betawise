/* Research-only streaming reconstruction of nonempty KJV/NKJV chapters.
 * Never included in release builds. It compares rebuilt tables with the
 * decoder's originals without replacing them or retaining scratch storage. */
typedef struct {
    uint8_t buffer[256], look[15];
    unsigned consumed, loaded, at, size, available;
} OffsetProbeStream;

static int OffsetProbeRead(OffsetProbeStream* stream) {
    if(stream->at == stream->size) {
        unsigned raw = stream->loaded, count = g_chapter_file_bytes - stream->loaded;
        if(!count) return -1;
        if(raw < g_editor.gap_start && count > g_editor.gap_start - raw)
            count = g_editor.gap_start - raw;
        if(raw >= g_editor.gap_start) raw += g_editor.gap_end - g_editor.gap_start;
        if(count > sizeof(stream->buffer)) count = sizeof(stream->buffer);
        if(FileSeek(READER_FILE, raw, FILE_SEEK_START) < 0) return -1;
        int read = FileReadBuffer(READER_FILE, stream->buffer, count);
        if(read <= 0) return -1;
        stream->loaded += read;
        stream->size = read;
        stream->at = 0;
    }
    return stream->buffer[stream->at++];
}

static void OffsetProbeAdvance(OffsetProbeStream* stream, unsigned count) {
    stream->consumed += count;
    stream->available -= count;
    memmove(stream->look, stream->look + count, stream->available);
}

static bool ProbeVerseOffsetRange(unsigned first, unsigned stop,
    unsigned begin_phase, unsigned end_phase) {
    uint16_t starts[BIBLE_MAX_CHAPTER_VERSES + 1] = {0};
    uint16_t searches[BIBLE_MAX_CHAPTER_VERSES + 1] = {0};
    uint16_t ends[BIBLE_MAX_CHAPTER_VERSES + 1] = {0};
    OffsetProbeStream stream = {0};
    unsigned verse = first - 1, body_end = 0, heading_start = 0;
    unsigned range_start = g_search_offsets[first];
    stream.consumed = stream.loaded = range_start;
    unsigned wanted = FindVerseAtOffset(g_editor.caret_offset);
    bool in_heading = false, pending_heading = false, valid = true;
    int32_t saved = FileTell(READER_FILE);
    ReaderProbeSet(phase, begin_phase);
    for(;;) {
        while(stream.available < sizeof(stream.look)) {
            int byte = OffsetProbeRead(&stream);
            if(byte < 0) break;
            stream.look[stream.available++] = byte;
        }
        if(!stream.available) break;
        const uint8_t* bytes = stream.look;
        unsigned pos = stream.consumed, count = 0, number = 0;
        if(stream.available >= 13 && bytes[0] == VERSE_FONT_BEGIN &&
            bytes[1] == VERSE_FONT_FACE_FLAGS && bytes[2] == VERSE_FONT_BEGIN &&
            bytes[3] == VERSE_FONT_BEGIN && (bytes[4] == 1 || bytes[4] == 2) &&
            bytes[5] == VERSE_FONT_BEGIN) {
            unsigned index = 6;
            while(index < stream.available && index < 9 && bytes[index] >= '0' && bytes[index] <= '9')
                number = number * 10 + bytes[index++] - '0';
            if(index > 6 && index + 6 <= stream.available && bytes[index] == VERSE_FONT_END &&
                bytes[index+1] == bytes[4] && bytes[index+2] == VERSE_FONT_END &&
                bytes[index+3] == VERSE_FONT_END && bytes[index+4] == VERSE_FONT_FACE_FLAGS &&
                bytes[index+5] == VERSE_FONT_END) count = index + 6;
        }
        if(count) {
            if(number != verse + 1 || number > g_verse_count) { valid = false; break; }
            if(verse) ends[verse] = body_end;
            if(verse == wanted) ReaderProbeSet(phase, 652);
            if(verse == stop) break;
            verse = number;
            starts[verse] = pos;
            searches[verse] = pending_heading ? heading_start : pos;
            pending_heading = false;
            body_end = pos + count;
        } else if(stream.available >= 3 && (bytes[0] == VERSE_FONT_BEGIN || bytes[0] == VERSE_FONT_END) && bytes[2] == bytes[0]) {
            count = 3;
            if(bytes[1] == 1 || bytes[1] == 2) {
                in_heading = bytes[0] == VERSE_FONT_BEGIN;
                if(in_heading && !pending_heading) { heading_start = pos; pending_heading = true; }
            } else if(!in_heading && bytes[0] == VERSE_FONT_END && pos == body_end) body_end += 3;
        } else {
            count = 1;
            if(!in_heading && verse && bytes[0] != ' ' && bytes[0] != '\r' &&
                bytes[0] != '\n' && bytes[0] != NATIVE_WRAP_SPACE) body_end = pos + 1;
        }
        OffsetProbeAdvance(&stream, count);
    }
    if(verse) ends[verse] = body_end;
    if(verse == wanted) ReaderProbeSet(phase, 652);
    if(verse != stop) valid = false;
    for(unsigned index = first; valid && index <= verse; ++index)
        if(starts[index] != g_verse_offsets[index] || searches[index] != g_search_offsets[index] ||
            ends[index] != g_verse_ends[index]) valid = false;
    FileSeek(READER_FILE, saved, FILE_SEEK_START);
    ReaderProbeSet(rebuild_bytes, stream.consumed - range_start);
    ReaderProbeSet(rebuild_ok, valid);
    ReaderProbeSet(phase, end_phase);
    return valid;
}

static void ProbeRebuildVerseOffsets(void) {
    unsigned wanted = FindVerseAtOffset(g_editor.caret_offset);
    unsigned checkpoint = ((wanted - 1) / 16) * 16 + 1;
    bool full = ProbeVerseOffsetRange(1, g_verse_count, 650, 651);
    bool sparse = ProbeVerseOffsetRange(checkpoint, wanted, 660, 661);
    ReaderProbeSet(rebuild_ok, full && sparse);
}
