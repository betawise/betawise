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

/* Borrowed only for this synchronous lookup; no editor/file writes occur. */
typedef struct {
    const uint8_t* base;
    const uint8_t* look;
    unsigned position, available;
#ifndef DIRECT_CONTIGUOUS
    uint8_t seam[15];
#endif
    bool failed;
} BoundaryStream;

static void BoundaryFill(BoundaryStream* stream) {
#ifdef DIRECT_CONTIGUOUS
    stream->look = stream->base + stream->position;
    stream->available = g_chapter_file_bytes - stream->position;
#else
    unsigned position = stream->position;
    unsigned count = g_chapter_file_bytes - position;
    unsigned gap = g_editor.gap_end - g_editor.gap_start;
    unsigned raw = position;
    if(position >= g_editor.gap_start) raw += gap;
    else if(count > g_editor.gap_start - position) {
        unsigned before = g_editor.gap_start - position;
        if(before < sizeof(stream->seam)) {
            if(count > sizeof(stream->seam)) count = sizeof(stream->seam);
            unsigned index;
            for(index = 0; index < count; ++index)
                stream->seam[index] = stream->base[position + index +
                    (index >= before ? gap : 0)];
            stream->look = stream->seam;
            stream->available = count;
            return;
        }
        count = before;
    }
    stream->look = stream->base + raw;
    stream->available = count;
#endif
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
    stream.failed = false;
    VerseBounds current = {0};
    stream.position = start;
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


/* Seek existing numbered records; no additional markers or file index. */
typedef struct { unsigned position, number; } NumberedRecord;

static bool NextNumberedRecord(BoundaryStream* stream, NumberedRecord* result) {
    for(;;) {
        BoundaryFill(stream);
        if(!stream->available) return false;
        unsigned skip = 0;
        while(skip < stream->available && stream->look[skip] != VERSE_FONT_BEGIN) ++skip;
        if(skip) { BoundaryAdvance(stream, skip); continue; }
        unsigned length = 0;
        unsigned number = BoundaryMarker(stream, &length);
        if(number && number <= g_verse_count) {
            result->position = stream->position;
            result->number = number;
            BoundaryAdvance(stream, length);
            return true;
        }
        BoundaryAdvance(stream, 1);
    }
}

#ifndef DIRECT_LINEAR
/* Keep the last numbered record below the target as the parser anchor.
 * This removes backward-window scans and shares one search for both inputs. */
static NumberedRecord FindEarlierRecord(unsigned target, bool by_position, const uint8_t* base) {
    unsigned first = 0, stop = g_chapter_file_bytes;
    NumberedRecord anchor = {0, 0};
    while(first < stop) {
        unsigned middle = first + (stop - first) / 2;
        BoundaryStream stream;
        stream.base = base;
        stream.failed = false;
        stream.position = middle;
        NumberedRecord found;
        ReaderProbeSet(phase, 716);
        bool present = NextNumberedRecord(&stream, &found);
        ReaderProbeSet(phase, 717);
        if(stream.failed) { ReaderProbeSet(error, 710); break; }
        if(!present || (by_position ? found.position >= target : found.number >= target)) stop = middle;
        else {
            anchor = found;
            if(!by_position && found.number + 1 == target) break;
            first = stream.position;
        }
    }
    return anchor;
}

#endif

static unsigned ReconstructBinaryBoundary(unsigned target, bool by_position) {
    ReaderProbeSet(phase, 710);
#ifdef DIRECT_CONTIGUOUS
    if(g_editor.gap_start < g_chapter_file_bytes) {
        ReaderProbeSet(error, 710); ReaderProbeSet(phase, 711); return 1;
    }
#endif
    const uint8_t* base = FileBindState(READER_FILE, NULL, NULL, NULL, NULL);
    if(!base) { ReaderProbeSet(error, 710); ReaderProbeSet(phase, 711); return 1; }
#ifdef DIRECT_LINEAR
    unsigned answer = ParseBoundary(1, target, by_position, 0, base);
#else
    NumberedRecord anchor = FindEarlierRecord(target, by_position, base);
    if(by_position && anchor.number) anchor = FindEarlierRecord(anchor.number, false, base);
    unsigned answer = ParseBoundary(anchor.number ? anchor.number : 1,
        target, by_position, anchor.position, base);
#endif
    ReaderProbeSet(phase, 711);
    return answer;
}

static const VerseBounds* LookupBoundary(unsigned verse) {
    if(g_boundary_cache_verse != verse) ReconstructBinaryBoundary(verse, false);
    return &g_boundary_cache;
}

static unsigned FindBoundaryVerse(unsigned position) {
    if(g_boundary_cache_verse && position >= g_boundary_cache.search && position < g_boundary_cache_limit)
        return g_boundary_cache_verse;
    return ReconstructBinaryBoundary(position, true);
}

static void RecordSearchOffset(unsigned verse, unsigned offset) { (void)verse; (void)offset; }
static void ShiftSearchOffset(unsigned verse, unsigned base, unsigned padding) {
    (void)verse; (void)base; (void)padding;
}
