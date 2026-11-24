#include "os3k.h"
#include "Decoder.h"
#include "Search.h"
#include "Navigation.h"
#include "Superscript.h"
#if BIBLEWISE_TEST
#include "../../tests/mame/asneo/BibleWiseProbe.h"
#else
#define ReaderProbeSet(field, value) ((void)0)
#define ReaderProbeAdd(field, value) ((void)0)
#define ReaderProbeSavedPosition(status, chapter, numbered) ((void)0)
#define ReaderProbeConfigureFonts(fonts) 1
#endif
#include <string.h>

/* Neo 3.21 editor notifications; these remain private until the SDK names them. */
#define READER_REDRAW_MESSAGE ((Message_e)0x1b)
enum {
    READER_RELOAD_FONTS = 0xfc,
    READER_REFRESH_CARET = 0xfe,
    READER_FILE = 1,
    READER_MAX_FILE_BYTES = 65500,
    READER_NO_WORD = UINT16_MAX,
    READER_SEARCH_SLICE_MS = 200,
    READER_SEARCH_BLOCK = 64,
    VERSE_DIGIT_CHARACTER = 0x90,
    VERSE_FONT_BEGIN = 0xb1,
    VERSE_FONT_END = 0xb2,
    VERSE_FONT_FACE_FLAGS = 0x0c
};

typedef enum {
    INPUT_NONE,
    INPUT_SEARCH = 2
} ReaderInput_e;

APPLET_HEADER_BEGIN
    APPLET_ID(0xA1B1)
    APPLET_NAME(BIBLE_APP_NAME)
    APPLET_INFO("Find words or verses; Option-Up/Down chapters")
    APPLET_FLAGS(APPLET_FLAG_ALLOW_FONT_DIALOG)
    .fileCount = 1,
    APPLET_VERSION(0, 2, "a")
    APPLET_LANGUAGE_EN_US
APPLET_HEADER_END

extern const uint8_t BibleData[], BibleDataEnd[];
extern const uint8_t BibleSearchData[], BibleSearchDataEnd[], BibleVerseCounts[];

static BibleDecoder_t g_decoder;
static BibleSearch_t g_search;
static TextEditor_t g_editor;
static FontHeader_t* g_body_fonts[4];
static FontHeader_t g_verse_font;
static FontHeader_t* g_ui_font;
static uint16_t g_verse_offsets[256];
static uint8_t g_write_buffer[256];
static uint32_t g_chapter_file_bytes;
static uint16_t g_current_chapter;
static uint16_t g_verse_count;
static uint16_t g_requested_word = READER_NO_WORD;
static bool g_ready;
static bool g_chapter_loaded;
static bool g_show_verse_numbers = 1;
static bool g_rendered_verse_numbers;
static bool g_notice_visible;
static bool g_status_visible;
static uint32_t g_notice_deadline;
static bool g_busy_visible;
static uint32_t g_busy_updated;
static bool g_search_active;
static bool g_have_query;
static bool g_search_has_results;
static ReaderInput_e g_input_kind;
static BibleSearchMode_e g_search_mode = BIBLE_SEARCH_NEARBY;
static unsigned g_input_length;
static unsigned g_find_cursor;
static char g_find_cells[35];
static unsigned g_find_cell_cursor;
static const char* g_find_error;
static unsigned g_busy_dots;
static unsigned g_busy_dot_x;
static char g_status_text[88];
static char g_input[BIBLE_SEARCH_QUERY_BYTES];
static unsigned FindBookForChapter(unsigned chapter) {
    unsigned book = 0;
    while(book < BIBLE_BOOK_COUNT - 1 && g_books[book + 1].first <= chapter) {
        ++book;
    }
    return book;
}

static unsigned FileOffsetWithoutGap(unsigned offset) {
    if(offset >= g_editor.gap_end) {
        return offset - (g_editor.gap_end - g_editor.gap_start);
    }
    return offset > g_editor.gap_start ? g_editor.gap_start : offset;
}

static unsigned FindVerseAtOffset(unsigned offset) {
    unsigned position = FileOffsetWithoutGap(offset);
    unsigned verse = 1;
    while(verse < g_verse_count && g_verse_offsets[verse + 1] <= position) {
        ++verse;
    }
    return verse;
}

static void ObserveReaderForTesting(void) {
#if BIBLEWISE_TEST
    g_reader.chapter = g_current_chapter;
    g_reader.verse = g_chapter_loaded ? FindVerseAtOffset(g_editor.caret_offset) : 1;
    g_reader.bytes = g_chapter_file_bytes;
    g_reader.status = g_status_visible;
    g_reader.mode = g_input_kind ? g_input_kind : g_notice_visible ? 3 : 0;
    g_reader.searching = g_search_active;
    g_reader.numbered = g_show_verse_numbers;
    g_reader.phase = 4;
    ++g_reader.serial;
#endif
}

static FontHeader_t* SystemFont(void) {
    if(!g_ui_font) {
        CallSysInt(0, SYS_INT_GET_SYSTEM_FONT_PTR, &g_ui_font);
    }
    return g_ui_font;
}

static void DrawSystemText(unsigned x, unsigned y, const char* text) {
    FontHeader_t* font = SystemFont();
    while(*text) {
        unsigned character = (uint8_t)*text++;
        unsigned width = font->width_table ? font->width_table[character] : font->max_width;
        unsigned offset = font->offset_table ? font->offset_table[character] : character * font->max_bytes;
        if(x + width > 264) break;
        DrawBitmap(x, y, width, font->height, font->bitmap_data + offset);
        x += width;
    }
}

static void DrawSystemLine(unsigned row, const char* text) {
    DrawSystemText(0, row * SystemFont()->height, text);
}

static FontHeader_t* StatusFont(void) {
    return g_body_fonts[0] ? g_body_fonts[0] : SystemFont();
}

static unsigned StatusTextWidth(const char* text) {
    unsigned width = 0;
    while(*text) width += StatusFont()->width_table ?
        StatusFont()->width_table[(uint8_t)*text++] : (text++, StatusFont()->max_width);
    return width;
}

static void DrawStatusText(unsigned x, unsigned y, const char* text, bool inverse) {
    FontHeader_t* font = StatusFont();
    while(*text) {
        unsigned character = (uint8_t)*text++;
        unsigned width = font->width_table ? font->width_table[character] : font->max_width;
        unsigned offset = font->offset_table ? font->offset_table[character] : character * font->max_bytes;
        if(x + width > 264) break;
        if(inverse) RasterOp(x, y, width, font->height,
            (uint8_t*)font->bitmap_data + offset, ROP_NOTSRCCOPY);
        else DrawBitmap(x, y, width, font->height, font->bitmap_data + offset);
        x += width;
    }
}

static unsigned StatusTop(void) { return 65 - StatusFont()->height; }

static void DrawStatusMessage(const char* text) {
    unsigned width = StatusTextWidth(text);
    RasterOp(0, StatusTop(), 264, StatusFont()->height, 0, ROP_BLACKNESS);
    DrawStatusText(width < 260 ? (264 - width) / 2 : 2, StatusTop(), text, true);
}

static void DrawBusyFrame(void) {
    unsigned dot_width = StatusTextWidth(".");
    if(g_busy_dots == 3) {
        RasterOp(g_busy_dot_x + dot_width, StatusTop(), 2 * dot_width,
            StatusFont()->height, 0, ROP_BLACKNESS);
        g_busy_dots = 1;
    } else {
        DrawStatusText(g_busy_dot_x + g_busy_dots * dot_width, StatusTop(), ".", true);
        ++g_busy_dots;
    }
    g_busy_updated = GetUptimeMilliseconds();
}

static void RestoreTransientDisplay(void);

static void ShowBusy(const char* verb) {
    uint8_t strip[264];
    unsigned top, column;
    RestoreTransientDisplay();
    SetCursorMode(CURSOR_MODE_HIDE);
    if(!g_busy_visible) {
        for(top = 0; top < StatusTop(); top += 8) {
            unsigned height = StatusTop() - top;
            if(height > 8) height = 8;
            RasterOp(0, top, 264, height, strip, ROP_CAPTURE);
            for(column = 0; column < 264; ++column) strip[column] &= column & 1 ? 0x55 : 0xaa;
            DrawBitmap(0, top, 264, height, strip);
        }
    }
    g_busy_visible = 1;
    strncpy(g_status_text, verb, sizeof(g_status_text) - 1);
    g_status_text[sizeof(g_status_text) - 1] = 0;
    RasterOp(0, StatusTop(), 264, StatusFont()->height, 0, ROP_BLACKNESS);
    DrawStatusText(2, StatusTop(), g_status_text, true);
    g_busy_dot_x = 2 + StatusTextWidth(g_status_text);
    g_busy_dots = 0;
    DrawBusyFrame();
}

static void UpdateBusy(void) {
    if(g_busy_visible && GetUptimeMilliseconds() - g_busy_updated >= 400) DrawBusyFrame();
}

static void ShowStatusMessage(const char* text, unsigned milliseconds) {
    RestoreTransientDisplay();
    SaveScreen();
    SetCursorMode(CURSOR_MODE_HIDE);
    if(text != g_status_text) {
        strncpy(g_status_text, text, sizeof(g_status_text) - 1);
        g_status_text[sizeof(g_status_text) - 1] = 0;
    }
    DrawStatusMessage(g_status_text);
    g_status_visible = 1;
    g_notice_deadline = GetUptimeMilliseconds() + milliseconds;
    ObserveReaderForTesting();
}

static void RestoreTransientDisplay(void) {
    if(g_notice_deadline) {
        g_notice_deadline = 0;
        g_notice_visible = 0;
        g_status_visible = 0;
        RestoreScreen();
        ObserveReaderForTesting();
    }
}

static void CloseFind(void) {
    g_input_kind = INPUT_NONE;
}

static void ShowNotice(const char* text) {
    CloseFind();
    g_notice_deadline = 0;
    g_status_visible = 0;
    g_busy_visible = 0;
    g_input_kind = INPUT_NONE;
    ClearScreen();
    SetCursorMode(CURSOR_MODE_HIDE);
    DrawSystemText(12, 0, text);
    DrawSystemLine(2, "  Find: words or a verse reference");
    DrawSystemLine(3, "  Press esc to return.");
    g_notice_visible = 1;
    ObserveReaderForTesting();
}

static void FormatChapterLabel(char* text, unsigned chapter, bool abbreviated) {
    unsigned book = FindBookForChapter(chapter);
    char name[24];
    const char* source = abbreviated ? g_books[book].name : g_books[book].name;
    unsigned count = 0;
    if(abbreviated) {
        /* A short canonical prefix retains numbered-book distinctions. */
        while(*source && count < 4) {
            if(*source != ' ') name[count++] = *source;
            ++source;
        }
        name[count] = 0;
    } else strcpy(name, source);
    sprintf(text, "%s %u", name, chapter - g_books[book].first + 1);
}

static void ShowLocation(bool include_verse) {
    char location[48], left[48] = "", right[48] = "", neighbor[40];
    unsigned book = FindBookForChapter(g_current_chapter);
    unsigned chapter = g_current_chapter - g_books[book].first + 1;
    unsigned x, width;
    RestoreTransientDisplay();
    if(include_verse) sprintf(location, "%s %u:%u", g_books[book].name, chapter,
        FindVerseAtOffset(g_editor.caret_offset));
    else sprintf(location, "%s %u", g_books[book].name, chapter);
    width = StatusTextWidth(location);
    x = width <= 260 ? (264 - width) / 2 : 2;
    if(g_current_chapter) {
        unsigned previous = g_current_chapter - 1;
        if(FindBookForChapter(previous) == book) sprintf(neighbor, "Ch %u", chapter - 1);
        else FormatChapterLabel(neighbor, previous, false);
        sprintf(left, "[:%s", neighbor);
        if(StatusTextWidth(left) + 6 > x) {
            FormatChapterLabel(neighbor, previous, true);
            sprintf(left, "[:%s", neighbor);
        }
    }
    if(g_current_chapter + 1 < BIBLE_CHAPTER_COUNT) {
        unsigned next = g_current_chapter + 1;
        if(FindBookForChapter(next) == book) sprintf(neighbor, "Ch %u", chapter + 1);
        else FormatChapterLabel(neighbor, next, false);
        sprintf(right, "%s:]", neighbor);
        if(StatusTextWidth(right) + 6 > 264 - x - width) {
            FormatChapterLabel(neighbor, next, true);
            sprintf(right, "%s:]", neighbor);
        }
    }
    SaveScreen();
    SetCursorMode(CURSOR_MODE_HIDE);
    RasterOp(0, StatusTop(), 264, StatusFont()->height, 0, ROP_BLACKNESS);
    if(StatusTextWidth(left) + 4 <= x) DrawStatusText(2, StatusTop(), left, true);
    DrawStatusText(x, StatusTop(), location, true);
    if(width <= 260 && StatusTextWidth(right) + 4 <= 264 - x - width)
        DrawStatusText(262 - StatusTextWidth(right), StatusTop(), right, true);
    strcpy(g_status_text, location);
    g_status_visible = 1;
    g_notice_deadline = GetUptimeMilliseconds() + 1500;
    ObserveReaderForTesting();
}

static void RedrawChapter(void) {
    CloseFind();
    g_status_visible = 0;
    g_notice_deadline = 0;
    g_busy_visible = 0;
    int32_t status = 0;
    g_notice_visible = 0;
    g_input_kind = INPUT_NONE;
    ClearScreen();
    SetCursorMode(CURSOR_MODE_SHOW);
    TextEditorHandleMessage(&g_editor, READER_REDRAW_MESSAGE, READER_REFRESH_CARET, 0, &status);
    ReaderProbeSet(error, status);
    ObserveReaderForTesting();
}

static void FormatCitation(char* output, unsigned chapter, unsigned verse) {
    unsigned book = FindBookForChapter(chapter);
    sprintf(output, "%s %u:%u (%s)", g_books[book].name,
        chapter - g_books[book].first + 1, verse, BIBLE_VERSION);
}

/* Face four is private to this editor. Sparse digit slots never register an
 * installed font or change AlphaWord's fonts. Body faces stay native. */
static int ConfigureVerseFont(void) {
    unsigned height = g_body_fonts[0]->height;
    if(!height || height > 64) {
        return 0;
    }
    g_verse_font.height = height;
    g_verse_font.max_width = 4;
    g_verse_font.max_bytes = 32;
    g_verse_font.width_table = superscript_widths;
    g_verse_font.offset_table = superscript_offsets;
    g_verse_font.bitmap_data = superscript_bitmaps[height == 11 ? 8 : (height - 1) / 8];
    return 1;
}

static int AppendChapterBytes(const void* bytes, unsigned count) {
    UpdateBusy();
    if(FileWriteBuffer(READER_FILE, bytes, count, FILE_WRITE_APPEND) != (int)count) {
        return 0;
    }
    g_chapter_file_bytes += count;
    return 1;
}

static int BufferChapterByte(uint8_t byte, unsigned* buffered) {
    g_write_buffer[(*buffered)++] = byte;
    if(*buffered == sizeof(g_write_buffer)) {
        if(!AppendChapterBytes(g_write_buffer, *buffered)) {
            return 0;
        }
        *buffered = 0;
    }
    return 1;
}

static int BufferVerseNumber(unsigned verse, unsigned* buffered) {
    uint8_t marker[12];
    uint8_t digits[3];
    unsigned marker_size = 0;
    unsigned digit_count = 0;
    unsigned index;
    do {
        digits[digit_count++] = VERSE_DIGIT_CHARACTER + verse % 10;
        verse /= 10;
    } while(verse);
    marker[marker_size++] = VERSE_FONT_BEGIN;
    marker[marker_size++] = VERSE_FONT_FACE_FLAGS;
    marker[marker_size++] = VERSE_FONT_BEGIN;
    while(digit_count) {
        marker[marker_size++] = digits[--digit_count];
    }
    marker[marker_size++] = VERSE_FONT_END;
    marker[marker_size++] = VERSE_FONT_FACE_FLAGS;
    marker[marker_size++] = VERSE_FONT_END;
    for(index = 0; index < marker_size; ++index) {
        if(!BufferChapterByte(marker[index], buffered)) {
            return 0;
        }
    }
    return 1;
}

static unsigned VerseTextOffset(unsigned verse) {
    unsigned offset = g_verse_offsets[verse];
    if(g_show_verse_numbers) {
        unsigned digits = 1;
        unsigned number = verse;
        while(number >= 10) {
            ++digits;
            number /= 10;
        }
        offset += 6 + digits;
    }
    return offset;
}

static int MoveCaretToOffset(unsigned position) {
    TextScan_t scan;
    int32_t status = 0;
    if(g_editor.selection_state) {
        TextEditorHandleMessage(&g_editor, MSG_KEY, KEY_LEFT, 0, &status);
    }
    if(TextScanInit(&g_editor, &scan, TEXT_POSITION_START)) {
        return 0;
    }
    if(position && position >= g_editor.gap_start) {
        position += g_editor.gap_end - g_editor.gap_start;
    }
    TextScanRead(&scan, position, 0, false, TEXT_BYTES_ENCODED,
        false, false, false, true, 0);
    if(!g_busy_visible) {
        ClearScreen();
    }
    /* The editor repaints its viewport, not the unused margin. Clear old
     * overlays/stipple there, including COMS after a Small-font chapter. */
    if(g_editor.height < 65) {
        RasterOp(0, g_editor.height, 264, 65 - g_editor.height, 0, ROP_WHITENESS);
    }
    if(TextEditorSetScanPosition(&scan, true)) {
        return 0;
    }
    g_busy_visible = 0;
    SetCursorMode(CURSOR_MODE_SHOW);
    g_notice_visible = 0;
    g_input_kind = INPUT_NONE;
    ObserveReaderForTesting();
    return 1;
}

static int SeekToVerse(unsigned verse) {
    if(verse < 1 || verse > g_verse_count) {
        return 0;
    }
    ReaderProbeSet(word, READER_NO_WORD);
    return MoveCaretToOffset(g_verse_offsets[verse]);
}

static int SeekToWord(unsigned verse, unsigned target_word) {
    unsigned position = VerseTextOffset(verse);
    unsigned end = verse < g_verse_count ? (unsigned)g_verse_offsets[verse + 1] - 1 :
        FileQuerySize(READER_FILE) - (g_editor.gap_end - g_editor.gap_start);
    unsigned ordinal = 0;
    unsigned word_state = 0;
    int32_t saved_position = FileTell(READER_FILE);

    while(position < end) {
        unsigned raw_position = position + (position >= g_editor.gap_start ?
            g_editor.gap_end - g_editor.gap_start : 0);
        unsigned count = end - position;
        int bytes_read;
        unsigned index;
        if(position < g_editor.gap_start && count > g_editor.gap_start - position) {
            count = g_editor.gap_start - position;
        }
        if(count > sizeof(g_write_buffer)) {
            count = sizeof(g_write_buffer);
        }
        if(FileSeek(READER_FILE, raw_position, FILE_SEEK_START) < 0) {
            return 0;
        }
        bytes_read = FileReadBuffer(READER_FILE, g_write_buffer, count);
        if(bytes_read <= 0) {
            return 0;
        }
        for(index = 0; index < (unsigned)bytes_read; ++index) {
            unsigned character = g_write_buffer[index];
            if(IsBibleLetter(character)) {
                if(!word_state && ordinal++ == target_word) {
                    FileSeek(READER_FILE, saved_position, FILE_SEEK_START);
                    ReaderProbeSet(word, target_word);
                    return MoveCaretToOffset(position + index);
                }
                word_state = 1;
            } else if(character == '\'' && word_state == 1) {
                word_state = 2;
            } else {
                word_state = 0;
            }
        }
        position += bytes_read;
    }
    FileSeek(READER_FILE, saved_position, FILE_SEEK_START);
    return 0;
}

static int DecodeChapterToFile(void) {
    unsigned buffered = 0;
    unsigned verse = 1;
    int character;
    if(!BibleDecoderOpenChapter(&g_decoder, g_current_chapter)) {
        return 0;
    }
    g_verse_offsets[1] = 0;
    if(g_show_verse_numbers && !BufferVerseNumber(verse, &buffered)) {
        return 0;
    }
    while((character = BibleDecoderReadByte(&g_decoder)) >= 0) {
        if(character == '\n') {
            if(++verse > g_verse_count) {
                break;
            }
            if(!BufferChapterByte(' ', &buffered) ||
                g_chapter_file_bytes + buffered > READER_MAX_FILE_BYTES) {
                return 0;
            }
            g_verse_offsets[verse] = g_chapter_file_bytes + buffered;
            if(g_show_verse_numbers && !BufferVerseNumber(verse, &buffered)) {
                return 0;
            }
        } else if(character < 32 || character > 126 ||
            !BufferChapterByte(character, &buffered)) {
            return 0;
        }
    }
    if(buffered && !AppendChapterBytes(g_write_buffer, buffered)) {
        return 0;
    }
    return !g_decoder.error && verse == (unsigned)g_verse_count + 1;
}

static void OpenChapter(unsigned chapter, unsigned verse) {
    bool updating = g_chapter_file_bytes && chapter == g_current_chapter;
    g_notice_deadline = 0;
    g_status_visible = 0;
    unsigned target_word = g_requested_word;
    int32_t status = 0;
    g_requested_word = READER_NO_WORD;
    ReaderProbeSet(phase, 1);
    ReaderProbeSet(error, 0);
    if(chapter >= BIBLE_CHAPTER_COUNT || verse < 1 ||
        verse > ReadBigEndian16(BibleVerseCounts + 2 * chapter)) {
        ShowNotice("Invalid chapter or verse");
        return;
    }
    if(g_chapter_loaded && chapter == g_current_chapter &&
        g_rendered_verse_numbers == g_show_verse_numbers) {
        if(FileOpen(READER_FILE, FILE_OPEN_KEEP_POSITION) < 0 ||
            TextEditorRefresh(&g_editor) ||
            !(target_word == READER_NO_WORD ? SeekToVerse(verse) : SeekToWord(verse, target_word))) {
            goto failed;
        }
        ShowLocation(target_word != READER_NO_WORD);
        return;
    }

    g_chapter_file_bytes = 0;
    g_current_chapter = chapter;
    g_verse_count = ReadBigEndian16(BibleVerseCounts + 2 * chapter);
    g_chapter_loaded = 0;
    FileClose();
    if(FileOpen(READER_FILE, FILE_OPEN_REWIND) < 0 || FileEraseCurrent() < 0) {
        goto failed;
    }
    /* Initialize an empty file and install fonts before any chapter text can
     * paint. The native editable descriptor is needed for font replacement;
     * ProcessMessage never forwards text-changing commands. */
    SetCursorMode(CURSOR_MODE_SHOW);
    status = TextEditorInit(&g_editor, READER_FILE, TEXT_EDITOR_EDITABLE,
        READER_MAX_FILE_BYTES, 0, 0, 264, 64);
    if(status) {
        goto failed;
    }
    if(!g_body_fonts[0]) {
        unsigned face;
        for(face = 0; face < 4; ++face) {
            g_body_fonts[face] = g_editor.fonts[face];
        }
        if(!ReaderProbeConfigureFonts(g_body_fonts)) {
            goto failed;
        }
    }
    if(!ConfigureVerseFont()) {
        goto failed;
    }
    status = TextEditorSetFonts(&g_editor, g_body_fonts[0], g_body_fonts[1],
        g_body_fonts[2], &g_verse_font, false);
    if(status) {
        goto failed;
    }
    /* AlphaWord fits six Small rows: the sixth descender is on LCD row 65.
     * Its eleventh (blank) glyph row falls just beyond the physical panel. */
    g_editor.height = g_body_fonts[0]->height == 11 ? 66 :
        (65 / g_body_fonts[0]->height) * g_body_fonts[0]->height;
    g_editor.layout_height = g_editor.height;
    ShowBusy(updating ? "Updating" : "Loading");
    ReaderProbeSet(phase, 3);
    if(!DecodeChapterToFile()) {
        goto failed;
    }
    ReaderProbeSet(phase, 2);
    g_chapter_loaded = 1;
    g_rendered_verse_numbers = g_show_verse_numbers;
    ReaderProbeSet(phase, 6);
    /* SetScanPosition handles the required layout. Avoid a redundant refresh. */
    if(!(target_word == READER_NO_WORD ? SeekToVerse(verse) : SeekToWord(verse, target_word))) {
        goto failed;
    }
    ShowLocation(target_word != READER_NO_WORD);
    return;

failed:
    ReaderProbeSet(error, status ? status : 1);
    ReaderProbeSet(phase, 5);
    SetCursorMode(CURSOR_MODE_HIDE);
    DrawSystemLine(0, "Unable to open Bible chapter");
}

static void SaveReadingPosition(void) {
    int32_t status;
    ReaderProbeSet(phase, 15);
    status = TextEditorSavePosition(&g_editor);
    ReaderProbeSavedPosition(status, g_current_chapter, g_show_verse_numbers);
    (void)status;
    FileClose();
    ReaderProbeSet(phase, 16);
}

/* AlphaWord-style four-line form. Keep field state in A5 and repaint only
 * the changed row; font-dialog templates repaint unrelated regions on typing. */
static void DrawFindField(void) {
    unsigned start = g_find_cursor >= 35 ? g_find_cursor - 34 : 0;
    unsigned cursor_cell = g_find_cursor - start;
    for(unsigned cell = 0; cell < 35; ++cell) {
        char glyph[2] = {start + cell < g_input_length ? g_input[start + cell] : ' ', 0};
        if(g_find_cells[cell] != glyph[0] || cell == cursor_cell || cell == g_find_cell_cursor) {
            DrawSystemText((7 + cell) * 6, 0, glyph);
            if(cell == cursor_cell) RasterOp((7 + cell) * 6, 0, 6, 16, 0, ROP_DSTINVERT);
            g_find_cells[cell] = glyph[0];
        }
    }
    g_find_cell_cursor = cursor_cell;
}

static void DrawFindFooter(const char* error) {
    g_find_error = error;
    RasterOp(0, 48, 264, 16, 0, ROP_WHITENESS);
    DrawSystemLine(3, error ? error : " John 3:16 = verse   Enter=find Esc=exit");
    ObserveReaderForTesting();
}

static void OpenFind(void) {
    ReaderProbeSet(phase, 20);
    RestoreTransientDisplay();
    CloseFind();
    ClearScreen();
    SetCursorMode(CURSOR_MODE_HIDE);
    g_input_kind = INPUT_SEARCH;
    g_notice_visible = 0;
    g_input_length = 0;
    g_find_cursor = 0;
    g_input[0] = 0;
    memset(g_find_cells, 0, sizeof(g_find_cells));
    DrawSystemLine(0, " Find:[                                   ]");
    DrawSystemLine(1, " \"faith works\" = exact phrase");
    DrawSystemLine(2, " faith work* = nearby (20 words)");
    DrawFindField();
    DrawFindFooter(0);
}

/* Canonical prefixes are supplemented by common non-prefix abbreviations. */
static const char* const g_book_aliases[BIBLE_BOOK_COUNT] = {
    "gen ge gn", "exod ex", "lev lv", "num nm", "deut dt", "josh jos", "judg jdg", "ruth ru",
    "1sam 1sa", "2sam 2sa", "1kgs 1ki", "2kgs 2ki", "1chr 1ch", "2chr 2ch", "ezra ezr", "neh ne",
    "esth est", "job jb", "ps psalm pss", "prov pr", "eccl ecc", "song sos cant", "isa is", "jer je",
    "lam la", "ezek eze", "dan da", "hos ho", "joel jl", "amos am", "obad ob", "jonah jon",
    "mic mi", "nah na", "hab hb", "zeph zep", "hag hg", "zech zec", "mal ml", "matt mt",
    "mark mk", "luke lk", "john jn", "acts ac", "rom ro", "1cor 1co", "2cor 2co", "gal ga",
    "eph ep", "phil php", "col co", "1thess 1th", "2thess 2th", "1tim 1ti", "2tim 2ti", "titus tit",
    "phlm philem", "heb he", "jas jm", "1pet 1pe", "2pet 2pe", "1john 1jn", "2john 2jn", "3john 3jn",
    "jude jud", "rev re"
};

static int LookupBook(const char* name) {
    unsigned book, matches = 0, found = 0;
    for(book = 0; book < BIBLE_BOOK_COUNT; ++book) {
        const char* alias = g_book_aliases[book];
        while(*alias) {
            const char* end = strchr(alias, ' ');
            unsigned size = end ? (unsigned)(end - alias) : strlen(alias);
            if(strlen(name) == size && !memcmp(name, alias, size)) return book;
            if(!end) break;
            alias = end + 1;
        }
    }
    for(book = 0; book < BIBLE_BOOK_COUNT; ++book) {
        char canonical[32];
        unsigned count = 0;
        const char* source = g_books[book].name;
        while(*source) {
            if(*source != ' ' && *source != '.') canonical[count++] = LowercaseBibleLetter(*source);
            ++source;
        }
        canonical[count] = 0;
        if(!strncmp(canonical, name, strlen(name))) {
            found = book;
            ++matches;
        }
    }
    return matches == 1 ? (int)found : matches ? -2 : -1;
}

static unsigned ReadReferenceNumber(const char** input) {
    unsigned number = 0;
    while(**input >= '0' && **input <= '9') {
        if(number < 65536) number = number * 10 + *(*input) - '0';
        ++*input;
    }
    return number;
}

/* 1: reference, 0: ordinary search text, -1: invalid/ambiguous reference. */
static int ParseReference(const char* input, unsigned* chapter, unsigned* verse) {
    char name[32];
    unsigned size = 0, chapter_number, verse_number = 1;
    bool letters = 0;
    int book;
    const char* scan = input;
    while(*scan == ' ') ++scan;
    while(*scan && !(letters && *scan >= '0' && *scan <= '9')) {
        if(IsBibleLetter(*scan)) letters = 1;
        if(*scan != ' ' && *scan != '.') {
            if(size == sizeof(name) - 1) return 0;
            name[size++] = LowercaseBibleLetter(*scan);
        }
        ++scan;
    }
    name[size] = 0;
    if(!letters) {
        /* Retained numeric-book compatibility, without advertising it. */
        scan = input;
        while(*scan == ' ') ++scan;
        if(*scan < '0' || *scan > '9') return 0;
        unsigned numeric_book = ReadReferenceNumber(&scan);
        if(*scan != ' ') return 0;
        while(*scan == ' ') ++scan;
        if(*scan < '0' || *scan > '9') return 0;
        if(!numeric_book || numeric_book > BIBLE_BOOK_COUNT) return -1;
        book = numeric_book - 1;
    } else {
        if(!*scan) return 0;
        book = LookupBook(name);
        if(book == -1) return 0;
        if(book < 0) return -1;
    }
    chapter_number = ReadReferenceNumber(&scan);
    while(*scan == ' ') ++scan;
    if(*scan == ':') {
        ++scan;
        while(*scan == ' ') ++scan;
        if(*scan < '0' || *scan > '9') return -1;
        verse_number = ReadReferenceNumber(&scan);
    } else if(*scan >= '0' && *scan <= '9') {
        verse_number = ReadReferenceNumber(&scan);
    }
    while(*scan == ' ') ++scan;
    if(*scan || !chapter_number || chapter_number > g_books[book].chapters) return -1;
    *chapter = g_books[book].first + chapter_number - 1;
    *verse = verse_number;
    return verse_number && verse_number <= ReadBigEndian16(BibleVerseCounts + 2 * *chapter) ? 1 : -1;
}

static unsigned FindWordAtCaret(void) {
    unsigned verse = FindVerseAtOffset(g_editor.caret_offset);
    unsigned end = FileOffsetWithoutGap(g_editor.caret_offset);
    unsigned position = VerseTextOffset(verse);
    unsigned word_count = 0;
    unsigned word_state = 0;
    int32_t saved_position = FileTell(READER_FILE);

    while(position < end) {
        unsigned raw_position = position + (position >= g_editor.gap_start ?
            g_editor.gap_end - g_editor.gap_start : 0);
        unsigned count = end - position;
        int bytes_read;
        unsigned index;
        if(position < g_editor.gap_start && count > g_editor.gap_start - position) {
            count = g_editor.gap_start - position;
        }
        if(count > sizeof(g_write_buffer)) {
            count = sizeof(g_write_buffer);
        }
        if(FileSeek(READER_FILE, raw_position, FILE_SEEK_START) < 0) {
            break;
        }
        bytes_read = FileReadBuffer(READER_FILE, g_write_buffer, count);
        if(bytes_read <= 0) {
            break;
        }
        for(index = 0; index < (unsigned)bytes_read; ++index) {
            unsigned character = g_write_buffer[index];
            if(IsBibleLetter(character)) {
                if(!word_state) {
                    ++word_count;
                }
                word_state = 1;
            } else if(character == '\'' && word_state == 1) {
                word_state = 2;
            } else {
                word_state = 0;
            }
        }
        position += bytes_read;
    }
    FileSeek(READER_FILE, saved_position, FILE_SEEK_START);
    return word_count && word_state ? word_count - 1 : word_count;
}

static void StartDirectionalSearch(int direction, unsigned include_origin) {
    if(!g_have_query) {
        OpenFind();
        return;
    }
    BibleSearchSetOrigin(&g_search, g_current_chapter,
        FindVerseAtOffset(g_editor.caret_offset), FindWordAtCaret(), direction, include_origin);
    BibleSearchEnableWrap(&g_search);
    g_search_active = 1;
    ShowBusy("Searching");
    ObserveReaderForTesting();
}

static void AdvanceSearch(void) {
    BibleSearchResult_e result;
    uint32_t start = GetUptimeMilliseconds();
    ReaderProbeSet(phase, 11);
    /* Yield on a held key as well as a queued event. A full ScanKeyboard call
     * is too expensive here; the event loop performs normal key processing. */
    do {
        result = BibleSearchStep(&g_search, READER_SEARCH_BLOCK);
        UpdateBusy();
    } while(result == BIBLE_SEARCH_PENDING && !IsKeyReady() && !IsKeyDownNow() &&
        GetUptimeMilliseconds() - start < READER_SEARCH_SLICE_MS);
    ReaderProbeSet(phase, 12);
    if(result == BIBLE_SEARCH_PENDING) {
        return;
    }
    g_search_active = 0;
    if(result != BIBLE_SEARCH_FOUND) {
        g_busy_visible = 0;
        RedrawChapter();
        if(result == BIBLE_SEARCH_COMPLETE) ShowStatusMessage("No matches", 2000);
        else ShowNotice("Search decode error");
        return;
    }
    g_search_has_results = 1;
    ReaderProbeAdd(hits, 1);
    g_requested_word = g_search.matched_word;
    OpenChapter(g_search.chapter, g_search.verse);
    if(g_search.wrapped) {
        char label[48];
        unsigned book = FindBookForChapter(g_current_chapter);
        sprintf(label, "Wrapped: %s %u:%u", g_books[book].name,
            g_current_chapter - g_books[book].first + 1, g_search.verse);
        ShowStatusMessage(label, 2000);
    }
}

static void CopySelectedVerses(void) {
    unsigned first_verse = FindVerseAtOffset(g_editor.caret_offset);
    unsigned last_verse = first_verse;
    unsigned verse = 1;
    unsigned buffered = 0;
    int character;
    char citation[88];

    if(g_editor.selection_state) {
        unsigned other_verse = FindVerseAtOffset(g_editor.selection_anchor);
        unsigned selection_end;
        if(other_verse < first_verse) {
            first_verse = other_verse;
        } else {
            last_verse = other_verse;
        }
        selection_end = FileOffsetWithoutGap(g_editor.caret_offset > g_editor.selection_anchor ?
            g_editor.caret_offset : g_editor.selection_anchor);
        if(last_verse > first_verse && selection_end == g_verse_offsets[last_verse]) {
            --last_verse;
        }
    }
    if(!BibleDecoderOpenChapter(&g_decoder, g_current_chapter)) {
        ShowNotice("Cannot copy verse");
        return;
    }
    if(ClipboardSet(g_write_buffer, 0, 1) < 0) {
        ShowNotice("Clipboard unavailable");
        return;
    }
    ReaderProbeSet(copied, 0);
    while((character = BibleDecoderReadByte(&g_decoder)) >= 0) {
        unsigned newline = character == '\n';
        if(verse >= first_verse && verse <= last_verse) {
            if(newline) {
                character = verse == last_verse ? '\r' : ' ';
            }
            g_write_buffer[buffered++] = character;
            if(buffered == sizeof(g_write_buffer)) {
                if(FileWriteBuffer(FILE_ID_CLIPBOARD, g_write_buffer, buffered, FILE_WRITE_APPEND) != (int)buffered) {
                    goto failed;
                }
                ReaderProbeAdd(copied, buffered);
                buffered = 0;
            }
        }
        if(newline) {
            if(verse == last_verse) {
                break;
            }
            ++verse;
        }
    }
    if(buffered) {
        if(FileWriteBuffer(FILE_ID_CLIPBOARD, g_write_buffer, buffered, FILE_WRITE_APPEND) != (int)buffered) {
            goto failed;
        }
        ReaderProbeAdd(copied, buffered);
    }
    FormatCitation(citation, g_current_chapter, first_verse);
    if(last_verse > first_verse) {
        unsigned book = FindBookForChapter(g_current_chapter);
        sprintf(citation, "%s %u:%u-%u (%s)", g_books[book].name,
            g_current_chapter - g_books[book].first + 1, first_verse, last_verse, BIBLE_VERSION);
    }
    buffered = strlen(citation);
    if(FileWriteBuffer(FILE_ID_CLIPBOARD, citation, buffered, FILE_WRITE_APPEND) != (int)buffered) {
        goto failed;
    }
    ReaderProbeAdd(copied, buffered);
    unsigned book = FindBookForChapter(g_current_chapter);
    if(first_verse == last_verse) sprintf(g_status_text, "Copied %s %u:%u", g_books[book].name,
        g_current_chapter - g_books[book].first + 1, first_verse);
    else sprintf(g_status_text, "Copied %s %u:%u-%u", g_books[book].name,
        g_current_chapter - g_books[book].first + 1, first_verse, last_verse);
    ShowStatusMessage(g_status_text, 1000);
    return;

failed:
    ClipboardClear();
    ShowNotice("Not enough clipboard memory");
}

static void AcceptInput(void) {
    unsigned chapter, verse;
    char query[BIBLE_SEARCH_QUERY_BYTES];
    const char* start = g_input;
    unsigned length;
    int reference = ParseReference(g_input, &chapter, &verse);
    if(reference) {
        if(reference < 0) DrawFindFooter(" Invalid or ambiguous reference");
        else {
            CloseFind();
            OpenChapter(chapter, verse);
            ShowLocation(true);
        }
        return;
    }
    while(*start == ' ') ++start;
    length = strlen(start);
    while(length && start[length - 1] == ' ') --length;
    if(!length) { DrawFindFooter(" Enter words or a verse reference"); return; }
    g_search_mode = BIBLE_SEARCH_NEARBY;
    if(start[0] == '"') {
        if(length < 2 || start[length - 1] != '"') {
            DrawFindFooter(" Close the phrase with a double quote");
            return;
        }
        ++start;
        length -= 2;
        g_search_mode = BIBLE_SEARCH_PHRASE;
    }
    memcpy(query, start, length);
    query[length] = 0;
    if(strchr(query, '"')) {
        DrawFindFooter(" Put quotes around the whole phrase");
        return;
    }
    if(g_search_mode == BIBLE_SEARCH_PHRASE && strchr(query, '*')) {
        DrawFindFooter(" Use * only outside quoted phrases");
        return;
    }
    g_have_query = BibleSearchBegin(&g_search, BibleData, BibleDataEnd - BibleData,
        BibleSearchData, BibleSearchDataEnd - BibleSearchData, query, g_search_mode);
    if(!g_have_query) {
        DrawFindFooter(" Use 1-8 words; * only at word endings");
        return;
    }
    g_search_has_results = 0;
    ReaderProbeSet(hits, 0);
    CloseFind();
    BibleSearchSetNearbyWords(&g_search, BIBLE_SEARCH_NEAR_WORDS);
    StartDirectionalSearch(1, 1);
}

static void ShowHelp(void) {
    g_notice_deadline = 0;
    g_status_visible = 0;
    ClearScreen();
    SetCursorMode(CURSOR_MODE_HIDE);
    DrawSystemLine(0, "  Find: words or John 3:16   V: numbers");
    DrawSystemLine(1, "  Cmd-G: next   Shift-Cmd-G: previous");
    DrawSystemLine(2, "  Option-Up/Down: chapter  Ctrl-C: copy");
    DrawSystemLine(3, "  ?: location    Esc: return");
    g_notice_visible = 1;
    ObserveReaderForTesting();
}

static void ChangeChapter(int direction) {
    int chapter = g_current_chapter + direction;
    if(chapter >= 0 && chapter < BIBLE_CHAPTER_COUNT) OpenChapter(chapter, 1);
    else ShowLocation(false);
}

static void HandleCharacter(unsigned character) {
    RestoreTransientDisplay();
    if(g_input_kind) {
        ReaderProbeSet(phase, 20);
        if(character == '\r' || character == '\n') { AcceptInput(); return; }
        if(character == 8 && g_find_cursor) {
            memmove(g_input + g_find_cursor - 1, g_input + g_find_cursor,
                g_input_length - g_find_cursor + 1);
            --g_find_cursor;
            --g_input_length;
        } else if(character >= 32 && character <= 126) {
            if(g_input_length == sizeof(g_input) - 1) {
                DrawFindFooter(" 63 characters maximum; edit with arrows");
                return;
            }
            memmove(g_input + g_find_cursor + 1, g_input + g_find_cursor,
                g_input_length - g_find_cursor + 1);
            g_input[g_find_cursor++] = character;
            ++g_input_length;
        }
        if(g_find_error) DrawFindFooter(0);
        DrawFindField();
        ObserveReaderForTesting();
        return;
    }
    if(g_notice_visible) RedrawChapter();
    if(character == '/' || character == 'f' || character == 'F') OpenFind();
    else if(character == 'n' || character == 'N') StartDirectionalSearch(1, 0);
    else if(character == 'p' || character == 'P') StartDirectionalSearch(-1, 0);
    else if(character == 'v' || character == 'V') {
        unsigned verse = FindVerseAtOffset(g_editor.caret_offset);
        g_show_verse_numbers = !g_show_verse_numbers;
        OpenChapter(g_current_chapter, verse);
    } else if(character == '[' || character == '{' || character == '<') ChangeChapter(-1);
    else if(character == ']' || character == '}' || character == '>') ChangeChapter(1);
    else if(character == '?') ShowLocation(false);
    else if(character == 'h' || character == 'H') ShowHelp();
    else if(character == ' ') {
        int32_t status = 0;
        unsigned direction = GetKeyModifiers() & KEY_MOD_SHIFT ? KEY_UP : KEY_DOWN;
        TextEditorHandleMessage(&g_editor, MSG_KEY, KEY_MOD_CMD | direction, 0, &status);
        ShowLocation(false);
    }
}

static void HandleKey(uint32_t parameter) {
    unsigned key = parameter & 0x7f;
    int32_t status = 0;
    if(key == KEY_CTRL || key == KEY_ALT || key == KEY_CMD ||
        key == KEY_LEFTSHIFT || key == KEY_RIGHTSHIFT) return;
    RestoreTransientDisplay();
    if(key == KEY_ESC) {
        g_search_active = 0;
        RedrawChapter();
    } else if(g_search_active) return;
    else if(g_input_kind) {
        ReaderProbeSet(phase, 20);
        if(key == KEY_ENTER) { AcceptInput(); return; }
        if(key == KEY_LEFT || key == KEY_RIGHT) {
            if(key == KEY_LEFT && g_find_cursor) --g_find_cursor;
            if(key == KEY_RIGHT && g_find_cursor < g_input_length) ++g_find_cursor;
            DrawFindField();
        } else if(key == KEY_HOME || key == KEY_END) {
            g_find_cursor = key == KEY_HOME ? 0 : g_input_length;
            DrawFindField();
        } else if(key == KEY_BACKSPACE) { HandleCharacter(8); return; }
        ObserveReaderForTesting();
    } else if(key == KEY_G && (parameter & KEY_MOD_CMD)) {
        StartDirectionalSearch(parameter & KEY_MOD_SHIFT ? -1 : 1, 0);
    } else if(key == KEY_FIND || (key == KEY_F && (parameter & (KEY_MOD_CMD | KEY_MOD_CTRL)))) {
        OpenFind();
    } else if(key == KEY_H && (parameter & (KEY_MOD_CMD | KEY_MOD_CTRL))) ShowHelp();
    else if(key == KEY_C && (parameter & KEY_MOD_CTRL)) CopySelectedVerses();
    else if((key == KEY_UP || key == KEY_DOWN || key == KEY_LEFT || key == KEY_RIGHT) &&
        (parameter & KEY_MOD_ALT) && !(parameter & KEY_MOD_SHIFT)) {
        ChangeChapter(key == KEY_DOWN || key == KEY_RIGHT ? 1 : -1);
    } else if(!g_notice_visible && (key == KEY_DOWN || key == KEY_UP || key == KEY_LEFT ||
        key == KEY_RIGHT || key == KEY_HOME || key == KEY_END)) {
        unsigned previous = g_editor.caret_offset;
        TextEditorHandleMessage(&g_editor, MSG_KEY, parameter, 0, &status);
        ReaderProbeSet(error, status);
        if(key == KEY_HOME || key == KEY_END || (parameter & KEY_MOD_CMD) ||
            ((key == KEY_UP || key == KEY_DOWN) && previous == g_editor.caret_offset)) {
            ShowLocation(false);
        } else ObserveReaderForTesting();
    }
}

void ProcessMessage(Message_e message, uint32_t parameter, uint32_t* reply) {
    *reply = 0;
    if(message == MSG_SETFOCUS) {
        if(!g_ready) {
            ReaderProbeSet(magic, 0x42524452);
            g_ready = BibleDecoderInit(&g_decoder, BibleData, BibleDataEnd - BibleData);
        }
        if(g_ready) {
            if(g_chapter_loaded) {
                if(FileOpen(READER_FILE, FILE_OPEN_KEEP_POSITION) < 0 || TextEditorRefresh(&g_editor)) {
                    ReaderProbeSet(error, 1);
                    return;
                }
                RedrawChapter();
            } else {
                OpenChapter(g_current_chapter, 1);
            }
        }
    } else if(message == MSG_KILLFOCUS) {
        CloseFind();
        g_notice_deadline = 0;
        g_busy_visible = 0;
        if(g_ready && g_chapter_loaded) {
            SaveReadingPosition();
        }
    } else if(g_ready && message == MSG_IDLE) {
        if(g_notice_deadline && (int32_t)(GetUptimeMilliseconds() - g_notice_deadline) >= 0) {
            RestoreTransientDisplay();
        }
        if(g_search_active) {
            AdvanceSearch();
        }
    } else if(g_ready && message == READER_REDRAW_MESSAGE) {
        CloseFind();
        if(g_chapter_loaded) {
            unsigned verse = FindVerseAtOffset(g_editor.caret_offset);
            if(parameter == READER_RELOAD_FONTS) {
                        g_input_kind = INPUT_NONE;
                g_body_fonts[0] = 0;
                g_chapter_loaded = 0;
                OpenChapter(g_current_chapter, verse);
            } else {
                RedrawChapter();
            }
        }
    } else if(g_ready && message == MSG_KEY && !(parameter & KEY_MOD_KEY_UP)) {
        HandleKey(parameter);
    } else if(g_ready && !g_search_active && message == MSG_CHAR) {
        if(parameter == 3 && !g_input_kind) {
            CopySelectedVerses();
        } else if(!(GetKeyModifiers() & (KEY_MOD_CTRL | KEY_MOD_CMD | KEY_MOD_ALT))) {
            HandleCharacter(parameter);
        }
    }
}
