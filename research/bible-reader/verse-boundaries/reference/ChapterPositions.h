/* Internal chapter-position implementation, included only by BibleWise.c.
 * The native gap is kept at EOF; the borrowed file pointer is local to a lookup.
 * No per-verse index is retained. */
typedef struct { uint16_t search, start, end; } VerseBounds;
static VerseBounds g_cached_bounds;
static uint16_t g_cached_verse;
static uint16_t g_cached_verse_limit;

/* Borrowed only for this synchronous lookup; no editor/file writes occur. */
typedef struct {
    const uint8_t* base;
    const uint8_t* look;
    unsigned position, available;
} BoundaryStream;

static void BoundaryFill(BoundaryStream* stream) {
    stream->look = stream->base + stream->position;
    stream->available = g_chapter_file_bytes - stream->position;
}

static void BoundaryAdvance(BoundaryStream* stream, unsigned count) {
    stream->position += count;
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

static unsigned ParseBoundary(unsigned first, unsigned target, bool by_position, unsigned start, const uint8_t* base) {
    BoundaryStream stream;
    stream.base = base;
    VerseBounds current = {0};
    stream.position = start;
    unsigned verse = first - 1, heading = 0;
    bool in_heading = false, pending_heading = false;
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
                g_cached_verse_limit = search;
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
    g_cached_verse_limit = g_chapter_file_bytes + 1;
    answer = verse;
    if((!by_position && target > verse) || (by_position && verse < g_verse_count && target >= current.end)) {
        answer = by_position ? g_verse_count : target;
        current.search = current.start = current.end;
    }
found:
    if(answer < first || answer > g_verse_count) {
        ReaderProbeSet(error, 710);
        answer = first;
    }
    g_cached_bounds = current;
    g_cached_verse = answer;
    return answer;
}


/* Seek existing numbered records; no additional markers or file index. */
typedef struct { unsigned position, number; } NumberedRecord;

/* Scan backward from each midpoint to a complete numbered record. */
static NumberedRecord FindEarlierRecord(unsigned target, bool by_position, const uint8_t* base) {
    unsigned first = 0, stop = g_chapter_file_bytes;
    NumberedRecord anchor = {0, 1};
    while(first < stop) {
        unsigned middle = first + (stop - first) / 2;
        BoundaryStream stream;
        stream.base = base;
        stream.position = middle;
        unsigned length, number;
        for(;;) {
            BoundaryFill(&stream);
            number = BoundaryMarker(&stream, &length);
            if(number || !stream.position) break;
            --stream.position;
        }
        if(number && (by_position ? stream.position >= target : number >= target)) stop = stream.position;
        else {
            if(number) { anchor.position = stream.position; anchor.number = number; }
            first = middle + 1;
        }
    }
    return anchor;
}

static unsigned ReconstructBinaryBoundary(unsigned target, bool by_position) {
    ReaderProbeSet(phase, 710);
    if(g_editor.gap_start != g_chapter_file_bytes) {
        ReaderProbeSet(error, 710); ReaderProbeSet(phase, 711); return 1;
    }
    const uint8_t* base = FileBindState(READER_FILE, NULL, NULL, NULL, NULL);
    if(!base) { ReaderProbeSet(error, 710); ReaderProbeSet(phase, 711); return 1; }
    NumberedRecord anchor = FindEarlierRecord(target, by_position, base);
    if(by_position) anchor = FindEarlierRecord(anchor.number, false, base);
    unsigned answer = ParseBoundary(anchor.number, target, by_position, anchor.position, base);
    ReaderProbeSet(phase, 711);
    return answer;
}

static const VerseBounds* GetVerseBounds(unsigned verse) {
    if(g_cached_verse != verse) ReconstructBinaryBoundary(verse, false);
    return &g_cached_bounds;
}

static unsigned FindChapterVerse(unsigned position) {
    if(g_cached_verse && position >= g_cached_bounds.search && position < g_cached_verse_limit)
        return g_cached_verse;
    return ReconstructBinaryBoundary(position, true);
}

