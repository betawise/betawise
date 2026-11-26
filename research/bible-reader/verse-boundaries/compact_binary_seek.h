/* Seek existing numbered records; no additional markers or file index. */
typedef struct { unsigned position, number, length; } NumberedRecord;

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
            result->length = length;
            BoundaryAdvance(stream, length);
            return true;
        }
        BoundaryAdvance(stream, 1);
    }
}

/* Keep the last numbered record below the target as the parser anchor.
 * This removes backward-window scans and shares one search for both inputs. */
static NumberedRecord FindEarlierRecord(unsigned target, bool by_position) {
    unsigned first = 0, stop = g_chapter_file_bytes;
    NumberedRecord anchor = {0, 0, 0};
    while(first < stop) {
        unsigned middle = first + (stop - first) / 2;
        BoundaryStream stream = {0};
        stream.position = stream.loaded = middle;
        NumberedRecord found;
        ReaderProbeSet(phase, 716);
        bool present = NextNumberedRecord(&stream, &found);
        ReaderProbeSet(phase, 717);
        if(stream.failed) { ReaderProbeSet(error, 710); break; }
        if(!present || (by_position ? found.position >= target : found.number >= target)) stop = middle;
        else {
            anchor = found;
            if(!by_position && found.number + 1 == target) break;
            first = found.position + found.length;
        }
    }
    return anchor;
}

static unsigned ReconstructBinaryBoundary(unsigned target, bool by_position) {
    int32_t saved = FileTell(READER_FILE);
    ReaderProbeSet(phase, 710);
    NumberedRecord anchor = FindEarlierRecord(target, by_position);
    /* A byte position can lie in a heading or number record. One earlier
     * verse supplies full formatting context for the local parser. */
    if(by_position && anchor.number) anchor = FindEarlierRecord(anchor.number, false);
    unsigned answer = ParseBoundary(anchor.number ? anchor.number : 1,
        target, by_position, anchor.number ? anchor.position : 0);
    FileSeek(READER_FILE, saved, FILE_SEEK_START);
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
