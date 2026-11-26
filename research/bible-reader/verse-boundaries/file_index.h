/* Research-only binary index in opaque B8 records at the chapter-file tail. */
#define FILE_INDEX_RECORD 0xB8
#define FILE_INDEX_ITEMS 32
#define FILE_INDEX_STRIDE (6 * FILE_INDEX_ITEMS + 4)
typedef struct { uint16_t search, start, end; } VerseBounds;
static VerseBounds g_boundary_cache;
static uint16_t g_boundary_cache_verse, g_boundary_cache_limit;
static int AppendChapterBytes(const void* bytes, unsigned count);

static unsigned FileIndexBytes(void) {
    return 6u * g_verse_count + 4u * ((g_verse_count + FILE_INDEX_ITEMS - 1) / FILE_INDEX_ITEMS);
}

static int ReadIndexValue(unsigned verse, void* output, unsigned count) {
    unsigned item = verse - 1;
    unsigned raw = g_chapter_file_bytes - FileIndexBytes() +
        (item / FILE_INDEX_ITEMS) * FILE_INDEX_STRIDE + 2 + (item % FILE_INDEX_ITEMS) * 6;
    if(raw >= g_editor.gap_start) raw += g_editor.gap_end - g_editor.gap_start;
    return FileSeek(READER_FILE, raw, FILE_SEEK_START) >= 0 &&
        FileReadBuffer(READER_FILE, output, count) == (int)count;
}

static void LoadFileBoundary(unsigned verse) {
    uint8_t bytes[6], next[2];
    int32_t saved = FileTell(READER_FILE);
    if(!ReadIndexValue(verse, bytes, sizeof(bytes))) goto failed;
    g_boundary_cache.search = ReadBigEndian16(bytes);
    g_boundary_cache.start = ReadBigEndian16(bytes + 2);
    g_boundary_cache.end = ReadBigEndian16(bytes + 4);
    g_boundary_cache_limit = g_chapter_file_bytes + 1;
    if(verse < g_verse_count) {
        if(!ReadIndexValue(verse + 1, next, sizeof(next))) goto failed;
        g_boundary_cache_limit = ReadBigEndian16(next);
    }
    g_boundary_cache_verse = verse;
    FileSeek(READER_FILE, saved, FILE_SEEK_START);
    return;
failed:
    ReaderProbeSet(error, 710);
    g_boundary_cache_verse = 0;
    FileSeek(READER_FILE, saved, FILE_SEEK_START);
}

static const VerseBounds* LookupBoundary(unsigned verse) {
    if(g_boundary_cache_verse != verse) {
        ReaderProbeSet(phase, 710);
        LoadFileBoundary(verse);
        ReaderProbeSet(phase, 711);
    }
    return &g_boundary_cache;
}

static unsigned FindBoundaryVerse(unsigned position) {
    if(g_boundary_cache_verse && position >= g_boundary_cache.search && position < g_boundary_cache_limit)
        return g_boundary_cache_verse;
    ReaderProbeSet(phase, 710);
    unsigned first = 1, stop = g_verse_count + 1;
    int32_t saved = FileTell(READER_FILE);
    while(first + 1 < stop) {
        unsigned middle = (first + stop) / 2;
        uint8_t bytes[2];
        if(!ReadIndexValue(middle, bytes, sizeof(bytes))) { ReaderProbeSet(error, 710); break; }
        if(ReadBigEndian16(bytes) <= position) first = middle;
        else stop = middle;
    }
    LoadFileBoundary(first);
    FileSeek(READER_FILE, saved, FILE_SEEK_START);
    ReaderProbeSet(phase, 711);
    return first;
}

static int StoreFileIndex(const VerseBounds* bounds) {
    uint8_t record[FILE_INDEX_STRIDE];
    ReaderProbeSet(phase, 714);
    for(unsigned verse = 1; verse <= g_verse_count;) {
        unsigned count = g_verse_count - verse + 1;
        if(count > FILE_INDEX_ITEMS) count = FILE_INDEX_ITEMS;
        unsigned length = count * 6 + 4;
        record[0] = record[length - 1] = FILE_INDEX_RECORD;
        record[1] = record[length - 2] = length;
        for(unsigned item = 0; item < count; ++item, ++verse) {
            const uint16_t values[] = {bounds[verse].search, bounds[verse].start, bounds[verse].end};
            for(unsigned field = 0; field < 3; ++field) {
                record[2 + item * 6 + field * 2] = values[field] >> 8;
                record[3 + item * 6 + field * 2] = values[field];
            }
        }
        if(!AppendChapterBytes(record, length)) return 0;
    }
    ReaderProbeSet(phase, 715);
    return 1;
}
