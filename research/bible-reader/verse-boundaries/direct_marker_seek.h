/* Direct-memory synthesized-record search; shared gap-safe reader/parser. */
static NumberedRecord FindPatternAnchor(unsigned target, const uint8_t* base) {
    NumberedRecord result = {0,0};
    if(target<=1) return result;
    --target;
    uint8_t pattern[15] __attribute__((aligned(2))) = {VERSE_FONT_BEGIN, VERSE_FONT_FACE_FLAGS,
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
    BoundaryStream stream;
    stream.base=base;stream.position=0;stream.failed=false;
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
            result.position = stream.position;
            result.number = target;
            ReaderProbeSet(phase, 717);
            return result;
        }
#ifdef MARKER_BMH
        BoundaryAdvance(&stream, skips[stream.look[length - 1]]);
#else
        BoundaryAdvance(&stream, 1);
#endif
    }
    ReaderProbeSet(phase, 717);
    ReaderProbeSet(error,710);
    return result;
}
