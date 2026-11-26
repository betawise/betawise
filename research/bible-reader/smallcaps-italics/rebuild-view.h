/* Research-only source anchors survive regenerated alignment padding. */
typedef struct {
    unsigned verse, word;
    int relative;
} RebuildPoint;

static void SaveRebuildPoint(unsigned position, RebuildPoint* point) {
    unsigned raw = position, origin;
    if(raw >= g_editor.gap_start) raw += g_editor.gap_end - g_editor.gap_start;
    point->verse = FindVerseAtOffset(raw);
    point->word = FindWordAtOffset(raw);
    if(!FindWordOffset(point->verse, point->word, false, &origin)) {
        point->word = READER_NO_WORD;
        origin = g_verse_ends[point->verse];
    }
    point->relative = (int)position - (int)origin;
}

static unsigned RestoreRebuildPoint(const RebuildPoint* point) {
    unsigned origin;
    if(point->word == READER_NO_WORD || !FindWordOffset(point->verse, point->word, false, &origin))
        origin = g_verse_ends[point->verse];
    return origin + point->relative;
}
