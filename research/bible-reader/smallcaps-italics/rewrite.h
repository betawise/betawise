/* Research-only alternatives to the persistent private-face aliases. */
#if BIBLEWISE_ITALICS_PROTOTYPE != 3
typedef struct {
    uint8_t bytes[READER_IO_BYTES];
    unsigned start, count, cursor, raw, dirty;
    int failed;
    NativeTextFilter filter;
} SmallCapFileScan;

static int FlushSmallCapBlock(SmallCapFileScan* scan) {
    if(!scan->dirty) return 1;
    scan->dirty = 0;
    return FileSeek(READER_FILE, scan->raw, FILE_SEEK_START) >= 0 &&
        FileWriteBuffer(READER_FILE, scan->bytes, scan->count, FILE_WRITE_OVERWRITE) == (int)scan->count;
}

static int NextSmallCap(SmallCapFileScan* scan, uint8_t* source) {
    for(;;) {
        if(scan->cursor == scan->count) {
            if(!FlushSmallCapBlock(scan)) { scan->failed = 1; return 0; }
            scan->start += scan->count;
            if(scan->start >= g_chapter_file_bytes) return 0;
            scan->raw = scan->start;
            scan->count = g_chapter_file_bytes - scan->start;
            if(scan->count > sizeof(scan->bytes)) scan->count = sizeof(scan->bytes);
            if(scan->start < g_editor.gap_start && scan->count > g_editor.gap_start - scan->start)
                scan->count = g_editor.gap_start - scan->start;
            if(scan->start >= g_editor.gap_start) scan->raw += g_editor.gap_end - g_editor.gap_start;
            if(FileSeek(READER_FILE, scan->raw, FILE_SEEK_START) < 0 ||
                FileReadBuffer(READER_FILE, scan->bytes, scan->count) != (int)scan->count) {
                scan->failed = 1;
                return 0;
            }
            scan->cursor = 0;
        }
        unsigned code = scan->bytes[scan->cursor++];
        if(NativeTextCharacter(&scan->filter, code) >= 0 && (scan->filter.flags & 12) == 12 &&
            NeoSmallCapsDecodeByte(code, source) && NeoSmallCapsCanonicalSource(*source)) return 1;
    }
}

static void ReplaceSmallCap(SmallCapFileScan* scan, unsigned source, bool italic) {
    uint8_t code;
    if(NeoSmallCapsEncodeByte(source, italic ? NEO_SMALLCAPS_ITALIC : NEO_SMALLCAPS_REGULAR, &code) &&
        scan->bytes[scan->cursor - 1] != code) {
        scan->bytes[scan->cursor - 1] = code;
        scan->dirty = 1;
    }
}

#if BIBLEWISE_ITALICS_PROTOTYPE == 1
static int RestoreSmallCapEvent(void* context, const BibleFormatEvent* event) {
    SmallCapFileScan* scan = context;
    if(event->kind != BIBLE_FORMAT_ATOM || !(event->style & BIBLE_STYLE_SMALL_CAPS)) return 1;
    for(unsigned index = 0; index < event->length; ++index) {
        uint8_t source = event->text[index], actual;
        if(!NeoSmallCapsCanonicalSource(source)) continue;
        if(!NextSmallCap(scan, &actual) || actual != source) return 0;
        if(!(event->style & BIBLE_STYLE_BOLD)) ReplaceSmallCap(scan, source, event->style & BIBLE_STYLE_ITALIC);
    }
    return 1;
}
#endif

#endif

static bool RewriteSmallCapItalics(bool enabled) {
    if(!g_rich_typography || !g_private_font) return true;
#if BIBLEWISE_ITALICS_PROTOTYPE == 3
    int32_t saved = FileTell(READER_FILE);
    bool okay = true;
    for(unsigned index = 0; index < g_italic_offset_count; ++index) {
        unsigned raw = g_italic_offsets[index];
        if(raw >= g_editor.gap_start) raw += g_editor.gap_end - g_editor.gap_start;
        uint8_t code, source;
        if(FileSeek(READER_FILE, raw, FILE_SEEK_START) < 0 || FileReadBuffer(READER_FILE, &code, 1) != 1 ||
            !NeoSmallCapsDecodeByte(code, &source) ||
            !NeoSmallCapsEncodeByte(source, enabled ? NEO_SMALLCAPS_ITALIC : NEO_SMALLCAPS_REGULAR, &code) ||
            FileSeek(READER_FILE, raw, FILE_SEEK_START) < 0 ||
            FileWriteBuffer(READER_FILE, &code, 1, FILE_WRITE_OVERWRITE) != 1) { okay = false; break; }
    }
#else
    unsigned index;
#if BIBLEWISE_ITALICS_PROTOTYPE == 2
    for(index = 0; index != ITALIC_RESEARCH_RANGE_COUNT && g_italic_ranges[index].chapter != g_current_chapter; ++index) {}
    if(index == ITALIC_RESEARCH_RANGE_COUNT) return true;
#else
    for(index = 0; index != ITALIC_RESEARCH_CHAPTER_COUNT && g_italic_chapters[index] != g_current_chapter; ++index) {}
    if(index == ITALIC_RESEARCH_CHAPTER_COUNT) return true;
#endif
    SmallCapFileScan scan;
    memset(&scan, 0, sizeof(scan));
    int32_t saved = FileTell(READER_FILE);
    uint8_t source;
    bool okay = true;
#if BIBLEWISE_ITALICS_PROTOTYPE == 1
    if(enabled) {
        BibleFormatAssets assets;
        unsigned vocabulary = ReadBigEndian16(BibleSearchData + 8);
        assets.bible = BibleData;
        assets.bible_size = BibleDataEnd - BibleData;
        assets.styles = BibleStyles;
        assets.layouts = BibleLayouts;
        assets.vocabulary_size = vocabulary;
        assets.normalization = BibleSearchData + 20 + 4u * (vocabulary + 1);
        okay = BibleFormatChapter(&assets, g_current_chapter, FindBookForChapter(g_current_chapter), RestoreSmallCapEvent, &scan);
    } else while(NextSmallCap(&scan, &source)) {
        uint8_t regular;
        NeoSmallCapsEncodeByte(source, NEO_SMALLCAPS_REGULAR, &regular);
        if(scan.bytes[scan.cursor - 1] == NeoSmallCapsItalicFromRegular(regular)) ReplaceSmallCap(&scan, source, false);
    }
#elif BIBLEWISE_ITALICS_PROTOTYPE == 2
    unsigned ordinal = 0;
    while(NextSmallCap(&scan, &source)) {
        while(index != ITALIC_RESEARCH_RANGE_COUNT && g_italic_ranges[index].chapter == g_current_chapter &&
            ordinal >= g_italic_ranges[index].first + g_italic_ranges[index].count) ++index;
        if(index != ITALIC_RESEARCH_RANGE_COUNT && g_italic_ranges[index].chapter == g_current_chapter &&
            ordinal >= g_italic_ranges[index].first) ReplaceSmallCap(&scan, source, enabled);
        ++ordinal;
    }
#elif BIBLEWISE_ITALICS_PROTOTYPE == 4
    while(NextSmallCap(&scan, &source)) if(scan.filter.flags & 0x10) ReplaceSmallCap(&scan, source, enabled);
#endif
    okay = okay && !scan.failed && FlushSmallCapBlock(&scan);
#endif
    FileSeek(READER_FILE, saved, FILE_SEEK_START);
    return okay;
}
