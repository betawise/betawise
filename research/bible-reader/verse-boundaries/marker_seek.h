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

/* Synthesize the exact existing record; visibility has two allowed masks. */
static bool FindNumberedVerse(unsigned target, NumberedRecord* result) {
    uint8_t pattern[15] = {VERSE_FONT_BEGIN, VERSE_FONT_FACE_FLAGS,
        VERSE_FONT_BEGIN, VERSE_FONT_BEGIN, 0, VERSE_FONT_BEGIN};
    unsigned length = 6;
    if(target >= 100) pattern[length++] = '0' + target / 100;
    if(target >= 10) pattern[length++] = '0' + target / 10 % 10;
    pattern[length++] = '0' + target % 10;
    pattern[length++] = VERSE_FONT_END;
    unsigned mask = length++;
    pattern[length++] = VERSE_FONT_END;
    pattern[length++] = VERSE_FONT_END;
    pattern[length++] = VERSE_FONT_FACE_FLAGS;
    pattern[length++] = VERSE_FONT_END;
#ifdef MARKER_BMH
    uint8_t skips[256];
    memset(skips, length, sizeof(skips));
    unsigned index;
    for(index = 0; index + 1 < length; ++index) {
        if(index == 4 || index == mask) {
            skips[1] = skips[2] = length - 1 - index;
        } else skips[pattern[index]] = length - 1 - index;
    }
#endif
    BoundaryStream stream = {0};
    ReaderProbeSet(phase, 716);
    for(;;) {
        BoundaryFill(&stream);
        if(stream.available < length) break;
#ifndef MARKER_BMH
        unsigned skip = 0;
        while(skip + length <= stream.available && stream.look[skip] != VERSE_FONT_BEGIN) ++skip;
        if(skip) { BoundaryAdvance(&stream, skip); continue; }
#endif
        pattern[4] = pattern[mask] = stream.look[4];
        if((pattern[4] == 1 || pattern[4] == 2) && !memcmp(stream.look, pattern, length)) {
            result->position = stream.position;
            result->number = target;
            result->length = length;
            ReaderProbeSet(phase, 717);
            return !stream.failed;
        }
#ifdef MARKER_BMH
        BoundaryAdvance(&stream, skips[stream.look[length - 1]]);
#else
        BoundaryAdvance(&stream, 1);
#endif
    }
    ReaderProbeSet(phase, 717);
    return false;
}

static bool PreviousNumberedRecord(unsigned before, NumberedRecord* result) {
    unsigned window = 256;
    for(;;) {
        unsigned first = before > window ? before - window : 0;
        BoundaryStream stream = {0};
        stream.position = stream.loaded = first;
        NumberedRecord found;
        bool present = false;
        while(stream.position < before && NextNumberedRecord(&stream, &found)) {
            if(found.position >= before) break;
            *result = found;
            present = true;
        }
        if(stream.failed) return false;
        if(present) return true;
        if(!first) return false;
        window *= 2;
    }
}

static unsigned ReconstructBinaryBoundary(unsigned target, bool by_position) {
    int32_t saved = FileTell(READER_FILE);
    unsigned first = 1, start = 0;
    NumberedRecord marker, previous;
    ReaderProbeSet(phase, 710);
    if(!by_position && target > 1) {
        if(!FindNumberedVerse(target, &marker)) {
            ReaderProbeSet(error, 710);
            goto parse;
        }
        /* The preceding verse supplies the context for any intervening heading. */
        if(PreviousNumberedRecord(marker.position, &previous)) {
            first = previous.number;
            start = previous.position;
        }
    } else if(by_position) {
        BoundaryStream stream = {0};
        stream.position = stream.loaded = target;
        if(NextNumberedRecord(&stream, &marker)) {
            /* Target may be in the next verse's heading or in the current
             * number record. Start one additional predecessor back. */
            if(PreviousNumberedRecord(marker.position, &previous) &&
                PreviousNumberedRecord(previous.position, &marker)) {
                first = marker.number;
                start = marker.position;
            }
        } else if(PreviousNumberedRecord(target + 1, &marker) &&
                  PreviousNumberedRecord(marker.position, &previous)) {
            first = previous.number;
            start = previous.position;
        }
    }
parse:
    unsigned answer = ParseBoundary(first, target, by_position, start);
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
