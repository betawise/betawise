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
    uint8_t bytes[256], look[15];
    unsigned position, loaded, cursor, count, available;
    bool failed;
} BoundaryStream;

static int BoundaryRead(BoundaryStream* stream) {
    if(stream->cursor == stream->count) {
        unsigned raw = stream->loaded, count = g_chapter_file_bytes - stream->loaded;
        if(!count) return -1;
        if(raw < g_editor.gap_start && count > g_editor.gap_start - raw) count = g_editor.gap_start - raw;
        if(raw >= g_editor.gap_start) raw += g_editor.gap_end - g_editor.gap_start;
        if(count > sizeof(stream->bytes)) count = sizeof(stream->bytes);
        if(FileSeek(READER_FILE, raw, FILE_SEEK_START) < 0 ||
            FileReadBuffer(READER_FILE, stream->bytes, count) != (int)count) {
            stream->failed = true;
            return -1;
        }
        stream->loaded += count;
        stream->count = count;
        stream->cursor = 0;
    }
    return stream->bytes[stream->cursor++];
}

static void BoundaryAdvance(BoundaryStream* stream, unsigned count) {
    stream->position += count;
    stream->available -= count;
    memmove(stream->look, stream->look + count, stream->available);
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

static unsigned ScanBoundary(unsigned first, unsigned target, bool by_position) {
    BoundaryStream stream = {0};
    VerseBounds current = {0};
    unsigned verse = first - 1, heading = 0;
    bool in_heading = false, pending_heading = false;
#ifndef RESEARCH_BOUNDARY_NONE
    stream.position = stream.loaded = g_boundary_index[(first - 1) / BOUNDARY_STRIDE];
#endif
    int32_t saved = FileTell(READER_FILE);
    unsigned answer = first;
    ReaderProbeSet(phase, 710);
    for(;;) {
        while(stream.available < sizeof(stream.look)) {
            int byte = BoundaryRead(&stream);
            if(byte < 0) break;
            stream.look[stream.available++] = byte;
        }
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
            length = 1;
            if(!in_heading && verse >= first && bytes[0] != ' ' && bytes[0] != '\r' &&
                bytes[0] != '\n' && bytes[0] != NATIVE_WRAP_SPACE) current.end = stream.position + 1;
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
    FileSeek(READER_FILE, saved, FILE_SEEK_START);
    if(stream.failed || answer < first || answer > g_verse_count) {
        ReaderProbeSet(error, 710);
        answer = first;
    }
    g_boundary_cache = current;
    g_boundary_cache_verse = answer;
    ReaderProbeSet(phase, 711);
    return answer;
}

static const VerseBounds* LookupBoundary(unsigned verse) {
    if(g_boundary_cache_verse != verse)
#ifdef RESEARCH_BOUNDARY_NONE
        ScanBoundary(1, verse, false);
#else
        ScanBoundary(((verse - 1) / BOUNDARY_STRIDE) * BOUNDARY_STRIDE + 1, verse, false);
#endif
    return &g_boundary_cache;
}

static void RecordSearchOffset(unsigned verse, unsigned offset) {
#ifndef RESEARCH_BOUNDARY_NONE
    if((verse - 1) % BOUNDARY_STRIDE == 0) g_boundary_index[(verse - 1) / BOUNDARY_STRIDE] = offset;
#else
    (void)verse; (void)offset;
#endif
}

static void ShiftSearchOffset(unsigned verse, unsigned base, unsigned padding) {
#ifndef RESEARCH_BOUNDARY_NONE
    if((verse - 1) % BOUNDARY_STRIDE == 0 && g_boundary_index[(verse - 1) / BOUNDARY_STRIDE] >= base)
        g_boundary_index[(verse - 1) / BOUNDARY_STRIDE] += padding;
#else
    (void)verse; (void)base; (void)padding;
#endif
}

static unsigned FindBoundaryVerse(unsigned position) {
#ifdef RESEARCH_BOUNDARY_NONE
    if(g_boundary_cache_verse && position >= g_boundary_cache.search && position < g_boundary_cache_limit)
        return g_boundary_cache_verse;
    return ScanBoundary(1, position, true);
#else
    unsigned index = 0;
    if(position < g_boundary_index[0]) return 1;
    while((index + 1) * BOUNDARY_STRIDE < g_verse_count && g_boundary_index[index + 1] <= position) ++index;
#if BOUNDARY_STRIDE == 1
    return index + 1;
#else
    /* The cache cannot safely classify the following heading; stop at end. */
    if(g_boundary_cache_verse && position >= g_boundary_cache.search && position < g_boundary_cache_limit)
        return g_boundary_cache_verse;
    return ScanBoundary(index * BOUNDARY_STRIDE + 1, position, true);
#endif
#endif
}
