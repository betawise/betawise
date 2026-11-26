static void CopySelectedVerses(void) {
    ReaderProbeSet(phase, 900);
    RestoreTransientDisplay();
    unsigned first_verse = FindVerseAtOffset(g_editor.caret_offset);
    unsigned last_verse = first_verse;
    unsigned start = VerseTextOffset(first_verse);
    unsigned end = VerseTextEnd(last_verse);
    char citation[88];
    if(g_editor.selection_state && g_editor.selection_anchor != g_editor.caret_offset) {
        unsigned a = FileOffsetWithoutGap(g_editor.caret_offset);
        unsigned b = FileOffsetWithoutGap(g_editor.selection_anchor);
        start = a < b ? a : b;
        end = a < b ? b : a;
        first_verse = FindVerseAtOffset(a < b ? g_editor.caret_offset : g_editor.selection_anchor);
        last_verse = FindVerseAtOffset((a < b ? g_editor.selection_anchor : g_editor.caret_offset) - 1);
        while(first_verse <= last_verse && start >= VerseTextEnd(first_verse)) ++first_verse;
        while(last_verse >= first_verse && end <= VerseTextOffset(last_verse)) --last_verse;
        if(first_verse > last_verse) { ShowStatusMessage("Select Bible text", 2000); return; }
    }
    bool omitted_start = start > VerseTextOffset(first_verse);
    bool omitted_end = end < VerseTextEnd(last_verse);
    unsigned context_start = GetVerseBounds(first_verse)->search;
    unsigned encoded = end - context_start;
    unsigned skip = start - context_start;
    FormatCitation(citation, g_current_chapter, first_verse);
    if(last_verse > first_verse) {
        unsigned book = FindBookForChapter(g_current_chapter);
        sprintf(citation, "%s %u:%u-%u (%s)", g_books[book].name,
            g_current_chapter - g_books[book].first + 1, first_verse, last_verse, BIBLE_VERSION);
    }
    unsigned citation_size = strlen(citation);
    unsigned capacity = encoded + 9 + citation_size;
    ReaderProbeCopyBegin();
    if(FileSeek(READER_FILE, context_start, FILE_SEEK_START) < 0) goto failed;
    ReaderProbeCopyWrite(false);
    int copied = ClipboardCopy(encoded, 1);
    ReaderProbeCopyWrite(true);
    if(copied != (int)encoded) goto failed;
    ReaderProbeCopyWrite(false);
    unsigned granted = ClipboardResize(capacity);
    ReaderProbeCopyWrite(true);
    if(granted != capacity) goto failed;
    /* All growth precedes borrowing the clipboard pointer. Converting in place
     * contracts the encoded stream; citation/ellipsis space is reserved above. */
    uint8_t* bytes = ClipboardGetData();
    if(!bytes) goto failed;
    NativeTextFilter filter = {0, 0};
    unsigned read = 0, written = 0;
    bool has_text = false, pending_space = false;
    while(read < skip) NativeTextCharacter(&filter, bytes[read++]);
    if(omitted_start) { memcpy(bytes, "... ", 4); written = 4; }
    while(read < encoded) {
        int character = NativeTextCharacter(&filter, bytes[read++]);
        if(character < 0 || (filter.flags & 1)) continue;
        if((filter.flags & 12) == 12 && character >= VERSE_DIGIT_CHARACTER &&
            character < VERSE_DIGIT_CHARACTER + 10) continue;
        if(!IsBibleQuote(character) && !NeoSmallCapsCanonicalSource(character) &&
            (character < 32 || character > 126)) {
            if(character != '\r') continue;
            character = ' ';
        }
        if(character == ' ') { pending_space = has_text; continue; }
        if(pending_space) bytes[written++] = ' ';
        pending_space = false;
        bytes[written++] = character;
        has_text = true;
    }
    if(omitted_end) { memcpy(bytes + written, " ...", 4); written += 4; }
    bytes[written++] = '\r';
    memcpy(bytes + written, citation, citation_size);
    written += citation_size;
    ReaderProbeCopyWrite(false);
    unsigned final_size = ClipboardResize(written);
    ReaderProbeCopyWrite(true);
    if(final_size != written) goto failed;
    ReaderProbeSet(copied, written);
    ReaderProbeSet(phase, 901);
    ShowStatusMessage("Copied", 2000);
    return;
failed:
    ClipboardClear();
    ShowNotice("Not enough clipboard memory");
}
