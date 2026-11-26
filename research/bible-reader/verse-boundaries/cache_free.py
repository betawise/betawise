"""Generate the same chapter-file index implementation with no A5 boundary cache."""


def generate(here):
    text=(here/'file_index.h').read_text()
    text=text.replace('static VerseBounds g_boundary_cache;\n','')
    text=text.replace('static uint16_t g_boundary_cache_verse, g_boundary_cache_limit;\n','')
    start=text.index('static void LoadFileBoundary(')
    end=text.index('static int StoreFileIndex(',start)
    text=text[:start]+'''static unsigned ReadBoundaryField(unsigned verse, unsigned field) {
    uint8_t bytes[6];
    int32_t saved = FileTell(READER_FILE);
    ReaderProbeSet(phase, 710);
    if(!ReadIndexValue(verse, bytes, sizeof(bytes))) {
        ReaderProbeSet(error, 710);
        memset(bytes, 0, sizeof(bytes));
    }
    FileSeek(READER_FILE, saved, FILE_SEEK_START);
    ReaderProbeSet(phase, 711);
    return ReadBigEndian16(bytes + field * 2);
}

static unsigned FindBoundaryVerse(unsigned position) {
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
    FileSeek(READER_FILE, saved, FILE_SEEK_START);
    ReaderProbeSet(phase, 711);
    return first;
}

'''+text[end:]
    output=here/'build/cache-free-index.h'
    output.write_text(text)
    return output
