#include "os3k.h"
#include "Decoder.h"
#include "Search.h"
#include "Formatting.h"
#include "Navigation.h"
#include "Superscript.h"
#if BIBLEWISE_ITALICS_PROTOTYPE
#include "ItalicResearch.h"
#endif
#include "charsets/neo-smallcaps.h"
#if BIBLEWISE_TEST
#include "../../tests/mame/asneo/BibleWiseProbe.h"
#else
#define ReaderProbeSet(field, value) ((void)0)
#define ReaderProbeAdd(field, value) ((void)0)
#define ReaderProbeSavedPosition(status, chapter, numbered) ((void)0)
#define ReaderProbeConfigureFonts(fonts) 1
#define ReaderProbeSelectSystemFont() ((void)0)
#endif
#include <string.h>

/* Neo 3.21 editor notifications; these remain private until the SDK names them. */
#define READER_REDRAW_MESSAGE ((Message_e)0x1b)
/* Native editor refresh parameters. */
#define READER_RELOAD_FONTS 0xfc
#define READER_REFRESH_CARET 0xfe
/* Neo 3.21: redraw-only dispatch bypasses caret/viewport reflow at 0x428902. */
#define READER_PAINT_VIEWPORT 0xff

/* Applet file, viewport and working limits. */
#define READER_FILE 1
#define READER_TEXT_WIDTH 252
#define READER_SIDEBAR_LEFT 253
#define READER_MAX_FILE_BYTES 65500
#define READER_NO_WORD UINT16_MAX
#define READER_FONT_AUTOMATIC UINT16_MAX
#define READER_FONT_SYSTEM_SMALL FONT_PICKER_SYSTEM_SMALL
#define READER_SEARCH_SLICE_MS 200
#define READER_BUSY_FRAME_MS 250
#define READER_NOTICE_WIDTH 112
#define READER_SEARCH_NOT_FOUND 1
#define READER_SEARCH_WRAPPED 2
#define READER_SEARCH_BLOCK 64
#define READER_FIND_MAX 32
#define READER_IO_BYTES 256

/* Native private-face verse markers. */
#define NATIVE_WRAP_SPACE 0x81
#define NATIVE_WRAP_HYPHEN 0xad
#define VERSE_DIGIT_CHARACTER '0'
#define VERSE_FONT_BEGIN 0xb1
#define VERSE_FONT_END 0xb2
#define VERSE_FONT_FACE_FLAGS 0x0c
#define VERSE_MARKER_BYTES 15
#define READER_REGION_PROTECTED 0x02
#define READER_REGION_HIDDEN 0x01

APPLET_HEADER_BEGIN
    APPLET_ID(0xA1B1)
    APPLET_NAME(BIBLE_APP_NAME)
    APPLET_INFO("Find words or verses; Option-Up/Down chapters")
    /* Keep the font shortcut local; the ROM chooser changes the system font. */
    APPLET_FLAGS(0)
    .fileCount = 1,
    APPLET_VERSION(0, 2, "a")
    APPLET_LANGUAGE_EN_US
APPLET_HEADER_END

extern const uint8_t BibleData[], BibleDataEnd[];
extern const uint8_t BibleSearchData[], BibleSearchDataEnd[], BibleVerseCounts[];
extern const uint8_t BibleStyles[], BibleLayouts[];

typedef struct {
    bool verse_numbers;
    bool italics;
    bool headings;
    uint16_t font_applet; /* Installed applet index; Automatic resolves once, zero selects ROM 6x16. */
} BibleSettings;

/* Only query/match information survives a completed search. The decoder,
 * candidate bitmaps and nearby matching workspace live on the search stack. */
static struct {
    uint16_t chapter, verse, word, end_verse, end_word;
    bool wrapped;
} g_match;
static BibleSearchMode_e g_search_mode;
static bool g_focused;
static TextEditor_t g_editor;
static FontHeader_t* g_body_fonts[4];
static FontHeader_t g_verse_font;
/* Stable identity survives slot compaction and label changes; the index is transient. */
static uint16_t g_reading_font_id;
static bool g_cursor_visible;
static uint16_t g_verse_offsets[BIBLE_MAX_CHAPTER_VERSES + 1];
static uint16_t g_search_offsets[BIBLE_MAX_CHAPTER_VERSES + 1];
static uint16_t g_verse_ends[BIBLE_MAX_CHAPTER_VERSES + 1];
/* Italics-off aliases persist while the editor references these tables.
 * Glyph bitmaps always remain in the font provider ROM. */
static FontHeader_t* g_private_font;
#if !BIBLEWISE_ITALICS_PROTOTYPE
static uint8_t g_private_widths[256];
static uint16_t g_private_offsets[256];
#elif BIBLEWISE_ITALICS_PROTOTYPE == 3
static uint16_t g_italic_offsets[ITALIC_RESEARCH_MAX_OFFSETS];
static uint16_t g_italic_offset_count;
#endif
static uint32_t g_chapter_file_bytes;
static uint16_t g_current_chapter;
static uint16_t g_verse_count;
static bool g_ready;
static bool g_chapter_loaded;
static uint8_t g_search_notice;
static BibleSettings g_settings = {true, true, true, READER_FONT_AUTOMATIC};
static uint8_t g_rendered_options;
static bool g_rich_typography;

static bool g_notice_visible;
static bool g_status_visible;
static uint32_t g_notice_deadline;
static bool g_busy_visible;
static uint32_t g_busy_updated;
static bool g_search_active;
static bool g_have_query;
static bool g_find_visible;
static bool g_font_menu_visible;
static unsigned g_busy_dots;

static char g_input[READER_FIND_MAX + 1];
static char g_last_find[READER_FIND_MAX + 1];
static unsigned DisplayOptions(void) {
    return g_settings.verse_numbers | (g_settings.italics << 1) | (g_settings.headings << 2);
}

static uint8_t HeadingRegionFlags(void) {
    return g_settings.headings ? READER_REGION_PROTECTED : READER_REGION_HIDDEN;
}

static bool ValidateBibleData(void) {
    BibleDecoder_t decoder;
    return BibleDecoderInit(&decoder, BibleData, BibleDataEnd - BibleData);
}

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
    while(verse < g_verse_count && g_search_offsets[verse + 1] <= position) {
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
    g_reader.mode = g_font_menu_visible ? 4 : g_find_visible ? 2 : g_notice_visible ? 3 : 0;
    g_reader.searching = g_search_active;
    g_reader.numbered = g_settings.verse_numbers;
    g_reader.phase = 4;
    ++g_reader.serial;
#endif
}

static FontHeader_t* SystemFont(void) {
    FontHeader_t* font = NULL;
    CallSysInt(0, SYS_INT_GET_SYSTEM_FONT_PTR, &font);
    return font;
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

static const char g_book_abbreviations[BIBLE_BOOK_COUNT][8] = {
    "Gen", "Ex", "Lev", "Num", "Deut", "Josh", "Judg", "Ruth", "1 Sam", "2 Sam",
    "1 Kgs", "2 Kgs", "1 Chr", "2 Chr", "Ezra", "Neh", "Esth", "Job", "Ps", "Prov",
    "Eccl", "Song", "Isa", "Jer", "Lam", "Ezek", "Dan", "Hos", "Joel", "Amos", "Obad",
    "Jonah", "Mic", "Nah", "Hab", "Zeph", "Hag", "Zech", "Mal", "Matt", "Mark", "Luke",
    "John", "Acts", "Rom", "1 Cor", "2 Cor", "Gal", "Eph", "Phil", "Col", "1 Thess",
    "2 Thess", "1 Tim", "2 Tim", "Titus", "Phlm", "Heb", "Jas", "1 Pet", "2 Pet",
    "1 John", "2 John", "3 John", "Jude", "Rev"
};

static FontHeader_t* SidebarFont(void) {
    FontHeader_t* font = NULL;
    CallSysInt(0, SYS_INT_GET_SMALL_FONT_PTR, &font);
    return font;
}

static unsigned GlyphWidth(FontHeader_t* font, unsigned character) {
    return font->width_table ? font->width_table[character] : font->max_width;
}

static const uint8_t* GlyphBitmap(FontHeader_t* font, unsigned character) {
    unsigned offset = font->offset_table ? font->offset_table[character] : character * font->max_bytes;
    return font->bitmap_data + offset;
}

static unsigned SidebarHeight(void) {
    return 65;
}

static void DrawSidebar(void) {
    ReaderProbeAdd(sidebar_draws, 1);
    ReaderProbeSet(phase, 40);
    uint8_t pixels[99];
    char label[16];
    FontHeader_t* font = SidebarFont();
    unsigned book = FindBookForChapter(g_current_chapter);
    unsigned chapter = g_current_chapter - g_books[book].first + 1;
    unsigned length = 0;
    sprintf(label, "%s %u", g_book_abbreviations[book], chapter);
    for(const char* c = label; *c; ++c) length += GlyphWidth(font, (uint8_t)*c);
    unsigned y = (SidebarHeight() - length) / 2;
    memset(pixels, 0xff, sizeof(pixels));
    for(const char* c = label; *c; ++c) {
        unsigned width = GlyphWidth(font, (uint8_t)*c);
        const uint8_t* glyph = GlyphBitmap(font, (uint8_t)*c);
        for(unsigned column = 0; column < width; ++column) {
            for(unsigned row = 0; row < font->height; ++row) {
                if(glyph[(row / 8) * width + column] & (1 << (row & 7))) {
                    pixels[((y + column) / 8) * 11 + 9 - row] &= ~(1 << ((y + column) & 7));
                }
            }
        }
        y += width;
    }
    ReaderProbeSet(phase, 41);
    RasterOp(READER_TEXT_WIDTH, 0, 1, 65, 0, ROP_WHITENESS);
    DrawBitmap(READER_SIDEBAR_LEFT, 0, 11, SidebarHeight(), pixels);
    ReaderProbeSet(phase, 42);
}

static void ApplyReadingCursor(void) {
    SetCursorMode(g_cursor_visible ? CURSOR_MODE_SHOW : CURSOR_MODE_HIDE);
}

static void StippleTextView(void) {
    uint8_t pixels[READER_TEXT_WIDTH * 9];
    RasterOp(0, 0, READER_TEXT_WIDTH, 65, pixels, ROP_CAPTURE);
    for(unsigned band = 0; band < 9; ++band) {
        for(unsigned column = 0; column < READER_TEXT_WIDTH; ++column) {
            pixels[band * READER_TEXT_WIDTH + column] &= column & 1 ? 0x55 : 0xaa;
        }
    }
    DrawBitmap(0, 0, READER_TEXT_WIDTH, 65, pixels);
}

static void DrawCenteredNotice(const char* text) {
    char label[41];
    strncpy(label, text, sizeof(label) - 1);
    label[sizeof(label) - 1] = 0;
    unsigned width = strlen(label) * 6;
    unsigned x = (READER_TEXT_WIDTH - width) / 2;
    RasterOp((READER_TEXT_WIDTH - READER_NOTICE_WIDTH) / 2, 22, READER_NOTICE_WIDTH, 20, 0, ROP_BLACKNESS);
    DrawSystemText(x, 24, label);
    RasterOp(x, 24, width, 16, 0, ROP_DSTINVERT);
}

static void DrawStatusMessage(const char* text) {
    StippleTextView();
    DrawCenteredNotice(text);
}

static void DrawBusyFrame(void) {
    uint8_t pixels[35];
    unsigned phase = g_busy_dots % 8 + 1;
    unsigned center = phase <= 5 ? phase - 1 : 9 - phase;
    g_busy_dots = 0;
    memset(pixels, 0xff, sizeof(pixels));
    for(unsigned dot = 0; dot < 5; ++dot) {
        unsigned distance = dot > center ? dot - center : center - dot;
        unsigned radius = distance <= 1 ? 1 : 0;
        unsigned cy = dot * 12 + 3;
        for(int dy = -(int)radius; dy <= (int)radius; ++dy) {
            for(int dx = -(int)radius; dx <= (int)radius; ++dx) {
                if(distance == 1 && dx && dy) continue;
                unsigned y = cy + dy;
                pixels[(y / 8) * 5 + 2 + dx] &= ~(1 << (y & 7));
            }
        }
    }
    DrawBitmap(256, 5, 5, 55, pixels);
    g_busy_dots = phase;
    g_busy_updated = GetUptimeMilliseconds();
}

static void RestoreTransientDisplay(void);

static void ShowBusy(bool searching) {
    RestoreTransientDisplay();
    SetCursorMode(CURSOR_MODE_HIDE);
    if(!g_busy_visible) StippleTextView();
    g_busy_visible = true;
    g_busy_dots = 0;
    if(searching) {
        RasterOp(READER_SIDEBAR_LEFT, 0, 11, SidebarHeight(), 0, ROP_BLACKNESS);
        DrawCenteredNotice("Searching");
        DrawBusyFrame();
    } else {
        DrawSidebar();
    }
}

static void UpdateBusy(void) {
    if(g_busy_visible && g_search_active && GetUptimeMilliseconds() - g_busy_updated >= READER_BUSY_FRAME_MS) {
        DrawBusyFrame();
    }
}

static void ShowStatusMessage(const char* text, unsigned milliseconds) {
    RestoreTransientDisplay();
    SaveScreen();
    SetCursorMode(CURSOR_MODE_HIDE);
    DrawStatusMessage(text);
    g_status_visible = 1;
    g_notice_deadline = GetUptimeMilliseconds() + milliseconds;
    ObserveReaderForTesting();
}

static void RedrawChapter(void);
static void OpenChapter(unsigned chapter, unsigned verse, unsigned target_word);
static void SelectSearchMatch(void);

static void ShowSearchNotice(unsigned notice) {
    ReaderProbeSet(phase, 50);
    g_busy_visible = false;
    g_search_notice = notice;
    DrawCenteredNotice(notice == READER_SEARCH_WRAPPED ? "Search wrapped" : "Not found");
    ReaderProbeSet(phase, 51);
    g_status_visible = 1;
    g_notice_deadline = GetUptimeMilliseconds() + 2000;
    ObserveReaderForTesting();
}

static void RestoreTransientDisplay(void) {
    if(g_notice_deadline) {
        g_notice_deadline = 0;
        g_notice_visible = 0;
        g_status_visible = 0;
        unsigned notice = g_search_notice;
        g_search_notice = 0;
        if(notice == READER_SEARCH_WRAPPED) {
            OpenChapter(g_match.chapter, g_match.verse, g_match.word);
            SelectSearchMatch();
        } else if(notice == READER_SEARCH_NOT_FOUND) {
            RedrawChapter();
        } else {
            RestoreScreen();
            ObserveReaderForTesting();
        }
    }
}

static void CloseFind(void) {
    g_find_visible = false;
}

static void ShowNotice(const char* text) {
    CloseFind();
    g_notice_deadline = 0;
    g_status_visible = 0;
    g_busy_visible = 0;
    g_find_visible = false;
    ClearScreen();
    SetCursorMode(CURSOR_MODE_HIDE);
    DrawSystemText(12, 0, text);
    DrawSystemLine(2, "  Find: words or a verse reference");
    DrawSystemLine(3, "  Press esc to return.");
    g_notice_visible = 1;
    ObserveReaderForTesting();
}


static void RedrawChapterWithMode(unsigned redraw_mode) {
    CloseFind();
    g_status_visible = 0;
    g_notice_deadline = 0;
    g_busy_visible = 0;
    int32_t status = 0;
    g_notice_visible = 0;
    g_find_visible = false;
    if(redraw_mode != READER_PAINT_VIEWPORT) ClearScreen();
    else if(g_editor.height < 65)
        RasterOp(0, g_editor.height, READER_TEXT_WIDTH, 65 - g_editor.height, NULL, ROP_WHITENESS);
    SetCursorMode(CURSOR_MODE_HIDE);
    TextEditorHandleMessage(&g_editor, READER_REDRAW_MESSAGE, redraw_mode, 0, &status);
    ReaderProbeSet(error, status);
    if(redraw_mode != READER_PAINT_VIEWPORT) DrawSidebar();
    ApplyReadingCursor();
    ObserveReaderForTesting();
}

static void RedrawChapter(void) {
    RedrawChapterWithMode(READER_REFRESH_CARET);
}

static void FormatCitation(char* output, unsigned chapter, unsigned verse) {
    unsigned book = FindBookForChapter(chapter);
    sprintf(output, "%s %u:%u (%s)", g_books[book].name,
        chapter - g_books[book].first + 1, verse, BIBLE_VERSION);
}

static bool FontAppletName(unsigned index, char name[37]) {
    if(!AppletIsFont(index) || AppletGetDisableMask(index)) return false;
    return AppletGetName(index,name);
}

static void SelectReadingFont(unsigned index) {
    uint16_t id = 0;
    if(index == READER_FONT_SYSTEM_SMALL) {
        g_reading_font_id = 0; g_settings.font_applet = index; return;
    }
    if(index && AppletIsFont(index) && !AppletGetDisableMask(index))
        id = AppletGetId(index);
    g_reading_font_id = id;
    g_settings.font_applet = id ? index : 0;
}

static unsigned ResolveReadingFont(void) {
    unsigned index;
    if(g_settings.font_applet == READER_FONT_SYSTEM_SMALL) return READER_FONT_SYSTEM_SMALL;
    if(!g_reading_font_id) return 0;
    index = AppletFindById(g_reading_font_id);
    return index && AppletIsFont(index) && !AppletGetDisableMask(index) ? index : 0;
}

/* First run only: prefer line count before family, then the built-in 6x16
 * font. Never inherit the global text-editor preference. */
static uint16_t DefaultReadingFont(void) {
    static const uint16_t priority[] = {
        0xAFFA, 0xAFF2, 0xAFF6, 0xAFFE, /* Five lines: Book, Serif, Sans, Mono. */
        0xAFFB, 0xAFF3, 0xAFF7, 0xAFFF, /* Six lines. */
        0xAFF9, 0xAFF1, 0xAFF5, 0xAFFD, /* Four lines. */
        0xAFF8, 0xAFF0, 0xAFF4, 0xAFFC  /* Three lines. */
    };
    unsigned choice, index;
    for(choice = 0; choice < sizeof(priority) / sizeof(*priority); ++choice) {
        index = AppletFindById(priority[choice]);
        if(index && !AppletGetDisableMask(index)) return index;
    }
    return 0;
}

/* The reading-font providers expose standard styles and the shared private
 * face. Never send a custom selector to an unrelated vendor font applet. */
static bool ConfigureBodyFaces(void) {
    unsigned index, face;
    g_private_font = NULL;
    g_body_fonts[1] = g_body_fonts[2] = g_body_fonts[0];
    for(unsigned id = 0xAFF0; id <= 0xAFFF; ++id) {
        FontHeader_t* normal = NULL;
        FontHeader_t* private_font = NULL;
        uint32_t reply = 0;
        index = AppletFindById(id);
        if(!index || AppletGetDisableMask(index)) continue;
        AppletSendMessage(index, MSG_FONT_GET_NORMAL, (uint32_t)&normal, &reply);
        if(normal != g_body_fonts[0]) continue;
        AppletSendMessage(index, MSG_FONT_GET_PRIVATE, (uint32_t)&private_font, &reply);
        if(!private_font || private_font->height != normal->height ||
            !private_font->width_table || !private_font->offset_table) return false;
        g_private_font = private_font;
        for(face = 1; face < 3; ++face) {
            FontHeader_t* font = NULL;
            AppletSendMessage(index, MSG_FONT_GET_NORMAL + face, (uint32_t)&font, &reply);
            g_body_fonts[face] = font ? font : normal;
        }
        if(!g_settings.italics) g_body_fonts[2] = normal;
        return true;
    }
    return false;
}

/* One H glyph per font selection: OR each packed page's columns, then find
 * its first ink bit. No text scan or per-character measurement is needed. */
static unsigned CapitalTop(FontHeader_t* font) {
    unsigned width = GlyphWidth(font, 'H'), page, x, bit;
    const uint8_t* glyph = GlyphBitmap(font, 'H');
    for(page = 0; page < (font->height + 7u) / 8; ++page) {
        uint8_t ink = 0;
        for(x = 0; x < width; ++x) ink |= glyph[page * width + x];
        if(ink) {
            for(bit = 0; !(ink & 1); ++bit) ink >>= 1;
            return page * 8 + bit;
        }
    }
    return 0;
}

static int ConfigureVerseFont(void) {
    FontHeader_t* font = g_body_fonts[0];
    unsigned height = font->height;
#if !BIBLEWISE_ITALICS_PROTOTYPE
    unsigned character;
#endif
    if(!height || height > 64) return 0;
    if(g_private_font) {
        g_verse_font = *g_private_font;
#if !BIBLEWISE_ITALICS_PROTOTYPE
        if(!g_settings.italics) {
            /* Preserve encoded file bytes while aliasing only Italic letters.
             * No glyph copying or runtime resizing is needed. */
            for(character = 0; character < 256; ++character) {
                unsigned slot = character;
                uint8_t source, regular;
                if(NeoSmallCapsDecodeByte(character, &source) &&
                    NeoSmallCapsEncodeByte(source, NEO_SMALLCAPS_REGULAR, &regular) &&
                    character == NeoSmallCapsItalicFromRegular(regular)) slot = regular;
                g_private_widths[character] = GlyphWidth(g_private_font, slot);
                g_private_offsets[character] = g_private_font->offset_table[slot];
            }
            g_verse_font.width_table = g_private_widths;
            g_verse_font.offset_table = g_private_offsets;
        }
#endif
    } else {
        /* Vendor/Terminal fonts need only BibleWise's sparse number overlay. */
        g_verse_font = *font;
        g_verse_font.max_width = 4;
        g_verse_font.max_bytes = 8;
        g_verse_font.width_table = superscript_widths;
        g_verse_font.offset_table = superscript_offsets;
        unsigned top = CapitalTop(font), bank;
        if(height < 5) return 0;
        if(top > height - 5) top = height - 5;
        /* Four ROM positions; unknown deeper capitals use the lowest bank. */
        bank = top >= 4 ? 3 : top >= 2 ? 2 : top;
        /* Keep the body height where the two-page ROM slots allow it: the
         * native cursor can otherwise leave residue on the 9px face. Taller
         * body fonts use a top-aligned 16px overlay without growing the line. */
        g_verse_font.height = height > 16 ? 16 : height;
        g_verse_font.bitmap_data = superscript_bitmaps[bank];
    }
    return 1;
}

static int32_t SetReadingFonts(void) {
    int32_t status = TextEditorSetFonts(&g_editor, g_body_fonts[0], g_body_fonts[1],
        g_body_fonts[2], &g_verse_font, false);
    if(status) return status;
    /* AlphaWord fits six Small rows; the last blank glyph row is clipped. */
    g_editor.height = g_body_fonts[0]->height == 11 ? 66 :
        (65 / g_body_fonts[0]->height) * g_body_fonts[0]->height;
    g_editor.layout_height = g_editor.height;
    return 0;
}

static int AppendChapterBytes(const void* bytes, unsigned count) {
    UpdateBusy();
    if(g_chapter_file_bytes + count > READER_MAX_FILE_BYTES) return 0;
    if(FileWriteBuffer(READER_FILE, bytes, count, FILE_WRITE_APPEND) != (int)count) {
        return 0;
    }
    g_chapter_file_bytes += count;
    return 1;
}

static int BufferChapterByte(uint8_t byte, uint8_t* buffer, unsigned* buffered) {
    buffer[(*buffered)++] = byte;
    if(*buffered == READER_IO_BYTES) {
        if(!AppendChapterBytes(buffer, *buffered)) {
            return 0;
        }
        *buffered = 0;
    }
    return 1;
}

static int BufferVerseNumber(unsigned verse, uint8_t* buffer, unsigned* buffered) {
    uint8_t marker[VERSE_MARKER_BYTES];
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
    marker[marker_size++] = VERSE_FONT_BEGIN;
    marker[marker_size++] = g_settings.verse_numbers ? READER_REGION_PROTECTED : READER_REGION_HIDDEN;
    marker[marker_size++] = VERSE_FONT_BEGIN;
    while(digit_count) {
        marker[marker_size++] = digits[--digit_count];
    }
    marker[marker_size++] = VERSE_FONT_END;
    marker[marker_size++] = g_settings.verse_numbers ? READER_REGION_PROTECTED : READER_REGION_HIDDEN;
    marker[marker_size++] = VERSE_FONT_END;
    marker[marker_size++] = VERSE_FONT_END;
    marker[marker_size++] = VERSE_FONT_FACE_FLAGS;
    marker[marker_size++] = VERSE_FONT_END;
    for(index = 0; index < marker_size; ++index) {
        if(!BufferChapterByte(marker[index], buffer, buffered)) {
            return 0;
        }
    }
    return 1;
}

static unsigned VerseTextOffset(unsigned verse) {
    unsigned start = g_verse_offsets[verse];
    /* Empty/omitted verses have no marker. Other markers contain twelve
     * formatting bytes followed by one to three superscript digits. */
    if(start == g_verse_ends[verse]) return start;
    return start + 12 + (verse >= 100 ? 3 : verse >= 10 ? 2 : 1);
}

static int PositionCaretAtOffset(unsigned position, bool draw) {
    TextScan_t scan;
    int32_t status = 0;
    if(g_editor.selection_state) {
        if(draw) TextEditorHandleMessage(&g_editor, MSG_KEY, KEY_LEFT, 0, &status);
        else g_editor.selection_state = 0;
    }
    if(TextScanInit(&g_editor, &scan, TEXT_POSITION_START)) {
        return 0;
    }
    if(position && position >= g_editor.gap_start) {
        position += g_editor.gap_end - g_editor.gap_start;
    }
    /* All three inventoried ROMs consume only editor/offset here and compute
     * layout themselves. A preliminary scan from byte zero is redundant. */
    scan.offset = position;
    if(draw && !g_busy_visible) {
        ClearScreen();
    }
    /* The editor repaints its viewport, not the unused margin. Clear old
     * overlays/stipple there, including COMS after a Small-font chapter. */
    if(draw && g_editor.height < 65) {
        RasterOp(0, g_editor.height, 264, 65 - g_editor.height, 0, ROP_WHITENESS);
    }
    if(TextEditorSetScanPosition(&scan, draw)) {
        return 0;
    }
    if(!draw) return 1;
    g_busy_visible = 0;
    DrawSidebar();
    ApplyReadingCursor();
    g_notice_visible = 0;
    g_find_visible = false;
    ObserveReaderForTesting();
    return 1;
}

static int MoveCaretToOffset(unsigned position) {
    return PositionCaretAtOffset(position, true);
}

static int SeekToVerse(unsigned verse) {
    if(verse < 1 || verse > g_verse_count) {
        return 0;
    }
    ReaderProbeSet(word, READER_NO_WORD);
    return MoveCaretToOffset(verse == 1 ? 0 : g_verse_offsets[verse]);
}

typedef struct { unsigned token, flags; } NativeTextFilter;

/* AlphaWord's three-byte region records are zero-width; heading and body
 * words share the same search stream. */
static int NativeTextCharacter(NativeTextFilter* filter, unsigned byte) {
    if(filter->token == 1 || filter->token == 2) {
        if(filter->token == 1) filter->flags |= byte;
        else filter->flags &= ~byte;
        filter->token = 3;
        return -1;
    }
    if(filter->token == 3) { filter->token = 0; return -1; }
    if(byte == VERSE_FONT_BEGIN) { filter->token = 1; return -1; }
    if(byte == VERSE_FONT_END) { filter->token = 2; return -1; }
    if((filter->flags & 12) == 12) {
        uint8_t source;
        return NeoSmallCapsDecodeByte(byte, &source) ? source : -1;
    }
    /* Cached wrap markers retain their source character when copied/searched. */
    return byte == NATIVE_WRAP_SPACE ? ' ' : byte == NATIVE_WRAP_HYPHEN ? '-' : byte;
}

static int FindWordOffset(unsigned verse, unsigned target_word, bool end_of_word, unsigned* offset) {
    uint8_t buffer[READER_IO_BYTES];
    unsigned position = g_search_offsets[verse];
    unsigned end = g_verse_ends[verse];
    unsigned ordinal = 0;
    unsigned word_end = 0;
    unsigned word_state = 0;
    NativeTextFilter filter = {0, 0};
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
        if(count > sizeof(buffer)) {
            count = sizeof(buffer);
        }
        if(FileSeek(READER_FILE, raw_position, FILE_SEEK_START) < 0) {
            return 0;
        }
        bytes_read = FileReadBuffer(READER_FILE, buffer, count);
        if(bytes_read <= 0) {
            return 0;
        }
        for(index = 0; index < (unsigned)bytes_read; ++index) {
            int character = NativeTextCharacter(&filter, buffer[index]);
            if(character < 0) continue;
            if(IsBibleLetter(character)) {
                if(!word_state && ordinal++ == target_word && !end_of_word) {
                    FileSeek(READER_FILE, saved_position, FILE_SEEK_START);
                    *offset = position + index;
                    return 1;
                }
                word_end = position + index + 1;
                word_state = 1;
            } else if(IsBibleApostrophe(character) && word_state == 1) {
                word_state = 2;
            } else {
                if(word_state && ordinal - 1 == target_word && end_of_word) {
                    FileSeek(READER_FILE, saved_position, FILE_SEEK_START);
                    *offset = word_end;
                    return 1;
                }
                word_state = 0;
            }
        }
        position += bytes_read;
    }
    FileSeek(READER_FILE, saved_position, FILE_SEEK_START);
    if(word_state && ordinal - 1 == target_word && end_of_word) {
        *offset = word_end;
        return 1;
    }
    return 0;
}

static int SeekToWord(unsigned verse, unsigned target_word) {
    unsigned offset;
    if(!FindWordOffset(verse, target_word, false, &offset)) {
        return 0;
    }
    ReaderProbeSet(word, target_word);
    return MoveCaretToOffset(offset);
}

static int ExtendNativeSelection(unsigned position, unsigned direction) {
    TextScan_t scan;
    int32_t status = 0;
    /* The native key establishes the anchor and its formatting flags. */
    TextEditorHandleMessage(&g_editor, MSG_KEY, direction | KEY_MOD_SHIFT, 0, &status);
    if(status || TextScanInit(&g_editor, &scan, TEXT_POSITION_START)) {
        return 0;
    }
    if(position >= g_editor.gap_start) {
        position += g_editor.gap_end - g_editor.gap_start;
    }
    TextScanRead(&scan, position, NULL, false, TEXT_BYTES_ENCODED, false, false, false, true, NULL);
    if(TextEditorSetScanPosition(&scan, true)) {
        return 0;
    }
    ApplyReadingCursor();
    ObserveReaderForTesting();
    return 1;
}

static void SelectSearchMatch(void) {
    unsigned end;
    if(FindWordOffset(g_match.end_verse, g_match.end_word, true, &end)) {
        ExtendNativeSelection(end, KEY_RIGHT);
    }
}

static void SelectVerseLookup(unsigned verse) {
    unsigned start = g_verse_offsets[verse];
    unsigned end = g_verse_ends[verse];
    /* Visit the end first so a short verse is wholly visible. Returning to its
     * beginning keeps long verses readable from their first line. */
    if(MoveCaretToOffset(end)) {
        ExtendNativeSelection(start, KEY_LEFT);
    }
}

typedef struct {
    uint8_t buffer[READER_IO_BYTES];
    unsigned buffered, verse, face, first_atom, line_start, separator;
    unsigned alignment, aligned_count, search_started;
    uint8_t aligned[1024];
} ChapterOutput;

static unsigned ChapterOutputOffset(const ChapterOutput* output) {
    return g_chapter_file_bytes + output->buffered + output->aligned_count;
}

static int FlushAlignedLine(ChapterOutput* output) {
    unsigned index = 0, flags = 0, width = 0, padding = 0;
    unsigned base = g_chapter_file_bytes + output->buffered;
    unsigned count = output->aligned_count;
    if(!output->alignment) return 1;
    while(index < count) {
        unsigned character = output->aligned[index++];
        if(character == VERSE_FONT_BEGIN || character == VERSE_FONT_END) {
            unsigned mask = output->aligned[index++];
            flags = character == VERSE_FONT_BEGIN ? flags | mask : flags & ~mask;
            ++index;
        } else if(!(flags & READER_REGION_HIDDEN)) {
            FontHeader_t* font = (flags & 12) == 12 ? &g_verse_font : g_body_fonts[(flags >> 2) & 3];
            width += GlyphWidth(font, character);
        }
    }
    if(width < READER_TEXT_WIDTH) {
        unsigned space = GlyphWidth(g_body_fonts[0], ' ');
        padding = (READER_TEXT_WIDTH - width) / (space ? space : 1);
        if(output->alignment == BIBLE_LAYOUT_CENTER) padding /= 2;
    }
    /* Positions already recorded within the buffered line move with its prefix. */
    for(index = 1; index <= g_verse_count && index <= output->verse; ++index) {
        if(index < output->verse || !output->first_atom) {
            if(g_search_offsets[index] >= base) g_search_offsets[index] += padding;
            if(g_verse_offsets[index] >= base) g_verse_offsets[index] += padding;
        }
        if(index < output->verse && g_verse_ends[index] >= base) g_verse_ends[index] += padding;
    }
#if BIBLEWISE_ITALICS_PROTOTYPE == 3
    for(index = 0; index < g_italic_offset_count; ++index)
        if(g_italic_offsets[index] >= base) g_italic_offsets[index] += padding;
#endif
    output->alignment = output->aligned_count = 0;
    while(padding--) if(!BufferChapterByte(' ', output->buffer, &output->buffered)) return 0;
    for(index = 0; index < count; ++index)
        if(!BufferChapterByte(output->aligned[index], output->buffer, &output->buffered)) return 0;
    return 1;
}

static int ChapterByte(ChapterOutput* output, unsigned character) {
    if(output->alignment) {
        if(output->aligned_count < sizeof(output->aligned)) {
            output->aligned[output->aligned_count++] = character;
            return 1;
        }
        /* Oversized logical lines are wider than the screen and left-wrap. */
        if(!FlushAlignedLine(output)) return 0;
    }
    return BufferChapterByte(character, output->buffer, &output->buffered);
}

static int ChapterRegion(ChapterOutput* output, unsigned begin, unsigned flags) {
    if(output->alignment && output->aligned_count + 3 > sizeof(output->aligned) &&
        !FlushAlignedLine(output)) return 0;
    return ChapterByte(output, begin ? VERSE_FONT_BEGIN : VERSE_FONT_END) &&
        ChapterByte(output, flags) && ChapterByte(output, begin ? VERSE_FONT_BEGIN : VERSE_FONT_END);
}

static int ChapterFace(ChapterOutput* output, unsigned face) {
    if(face == output->face) return 1;
    if(output->face && !ChapterRegion(output, false, output->face)) return 0;
    output->face = face;
    return !face || ChapterRegion(output, true, face);
}

static int ChapterLine(ChapterOutput* output) {
    output->separator = 0;
    if(!FlushAlignedLine(output) || !ChapterFace(output, 0)) return 0;
    if(!output->line_start && !ChapterByte(output, '\r')) return 0;
    output->line_start = 1;
    return 1;
}

static int WriteChapterEvent(void* context, const BibleFormatEvent* event) {
    ChapterOutput* output = context;
    unsigned index, face, indent;
    unsigned style = g_rich_typography ? event->style : 0;
    if(event->kind == BIBLE_FORMAT_SPACE) {
        output->separator = 1;
        if(event->text[0] == '\n') {
            if(output->verse > g_verse_count) return 0;
            if(output->first_atom) {
                if(!output->search_started) g_search_offsets[output->verse] = ChapterOutputOffset(output);
                g_verse_offsets[output->verse] = ChapterOutputOffset(output);
            }
            if(!ChapterFace(output, 0)) return 0;
            g_verse_ends[output->verse] = ChapterOutputOffset(output);
            ++output->verse;
            output->first_atom = 1;
            output->search_started = 0;
        }
        return 1;
    }
    if(event->kind == BIBLE_FORMAT_HEADING) {
        if(!ChapterLine(output)) return 0;
        if(!output->search_started && output->verse <= g_verse_count) {
            g_search_offsets[output->verse] = ChapterOutputOffset(output);
            output->search_started = 1;
        }
        /* A fixed-size visibility record keeps heading text and formatting in
         * the file. Include its terminating CR in the same hidden region. */
        if(!ChapterRegion(output, true, HeadingRegionFlags()) ||
            !ChapterFace(output, g_rich_typography ? 4 : 0)) return 0;
        for(index = 0; index < event->length; ++index) {
            if(!ChapterByte(output, event->text[index])) return 0;
        }
        output->line_start = 0;
        if(!ChapterFace(output, 0) || !ChapterLine(output)) return 0;
        return ChapterRegion(output, false, HeadingRegionFlags());
    }
    if(event->layout && !ChapterLine(output)) return 0;
    if(event->layout & (BIBLE_LAYOUT_CENTER | BIBLE_LAYOUT_RIGHT))
        output->alignment = event->layout & BIBLE_LAYOUT_CENTER ? BIBLE_LAYOUT_CENTER : BIBLE_LAYOUT_RIGHT;
    /* Never let a sparse small-cap face consume separators or indentation. */
    if(!ChapterFace(output, 0)) return 0;
    if(output->separator && !output->line_start && !ChapterByte(output, ' ')) return 0;
    output->separator = 0;
    indent = event->layout & BIBLE_LAYOUT_DOUBLE_INDENT ? 4 :
        event->layout & BIBLE_LAYOUT_INDENT ? 2 : 0;
    while(indent--) if(!ChapterByte(output, ' ')) return 0;
    if(output->first_atom) {
        if(output->verse > g_verse_count || !ChapterFace(output, 0)) return 0;
        g_verse_offsets[output->verse] = ChapterOutputOffset(output);
        if(!output->search_started) {
            g_search_offsets[output->verse] = ChapterOutputOffset(output);
            output->search_started = 1;
        }
        {
            uint8_t marker[VERSE_MARKER_BYTES];
            unsigned size = 0;
            if(output->alignment && output->aligned_count + sizeof(marker) > sizeof(output->aligned) &&
                !FlushAlignedLine(output)) return 0;
            if(!BufferVerseNumber(output->verse, marker, &size)) return 0;
            for(index = 0; index < size; ++index) if(!ChapterByte(output, marker[index])) return 0;
        }
        output->first_atom = 0;
    }
    face = style & BIBLE_STYLE_ITALIC ? 8 : style & BIBLE_STYLE_BOLD ? 4 : 0;
#if BIBLEWISE_ITALICS_PROTOTYPE == 6
    /* Permanent source provenance, independent of the display preference. */
    if(style & BIBLE_STYLE_ITALIC) face |= 0x10;
#endif
    for(index = 0; index < event->length; ++index) {
        unsigned character = event->text[index];
        unsigned actual_face = face;
#if BIBLEWISE_ITALICS_PROTOTYPE == 3
        bool record_italic = false;
#endif
        if(style & BIBLE_STYLE_SMALL_CAPS) {
            uint8_t glyph;
            NeoSmallCapsStyle variant = style & BIBLE_STYLE_ITALIC ? NEO_SMALLCAPS_ITALIC :
                style & BIBLE_STYLE_BOLD ? NEO_SMALLCAPS_BOLD : NEO_SMALLCAPS_REGULAR;
#if BIBLEWISE_ITALICS_PROTOTYPE
            NeoSmallCapsStyle displayed = !g_settings.italics && variant == NEO_SMALLCAPS_ITALIC ?
                NEO_SMALLCAPS_REGULAR : variant;
#else
            NeoSmallCapsStyle displayed = variant;
#endif
            if(NeoSmallCapsEncodeByte(character, displayed, &glyph)) {
                actual_face = 12;
#if BIBLEWISE_ITALICS_PROTOTYPE == 4 || BIBLEWISE_ITALICS_PROTOTYPE == 6
                if(variant == NEO_SMALLCAPS_ITALIC) actual_face |= 0x10;
#elif BIBLEWISE_ITALICS_PROTOTYPE == 3
                record_italic = variant == NEO_SMALLCAPS_ITALIC;
#endif
                character = glyph;
            }
        }
        if(!ChapterFace(output, actual_face)) return 0;
#if BIBLEWISE_ITALICS_PROTOTYPE == 3
        if(record_italic) {
            if(g_italic_offset_count == ITALIC_RESEARCH_MAX_OFFSETS) return 0;
            g_italic_offsets[g_italic_offset_count++] = ChapterOutputOffset(output);
        }
#endif
        if(!ChapterByte(output, character)) return 0;
    }
    output->line_start = 0;
    return 1;
}

static int DecodeChapterToFile(void) {
    ReaderProbeAdd(chapter_decodes, 1);
#if BIBLEWISE_ITALICS_PROTOTYPE == 3
    g_italic_offset_count = 0;
#endif
    ChapterOutput output;
    BibleFormatAssets assets;
    unsigned vocabulary = ReadBigEndian16(BibleSearchData + 8);
    memset(&output, 0, sizeof(output));
    output.verse = output.first_atom = output.line_start = 1;
    assets.bible = BibleData;
    assets.bible_size = BibleDataEnd - BibleData;
    assets.styles = BibleStyles;
    assets.layouts = BibleLayouts;
    assets.vocabulary_size = vocabulary;
    assets.normalization = BibleSearchData + 20 + 4u * (vocabulary + 1);
    if(!BibleFormatChapter(&assets, g_current_chapter, FindBookForChapter(g_current_chapter),
        WriteChapterEvent, &output) || output.verse != (unsigned)g_verse_count + 1 ||
        !FlushAlignedLine(&output)) return 0;
    return !output.buffered || AppendChapterBytes(output.buffer, output.buffered);
}

#if BIBLEWISE_ITALICS_PROTOTYPE > 0 && BIBLEWISE_ITALICS_PROTOTYPE < 5
#include "../../research/bible-reader/smallcaps-italics/rewrite.h"
#endif

static void OpenChapter(unsigned chapter, unsigned verse, unsigned target_word) {
    g_cursor_visible = false;
    g_notice_deadline = 0;
    g_status_visible = 0;
    int32_t status = 0;
    ReaderProbeSet(phase, 1);
    ReaderProbeSet(error, 0);
    if(chapter >= BIBLE_CHAPTER_COUNT || verse < 1 ||
        ReadBigEndian16(BibleVerseCounts + 2 * chapter) > BIBLE_MAX_CHAPTER_VERSES ||
        verse > ReadBigEndian16(BibleVerseCounts + 2 * chapter)) {
        ShowNotice("Invalid chapter or verse");
        return;
    }
    if(g_chapter_loaded && chapter == g_current_chapter &&
        g_rendered_options == DisplayOptions()) {
        if(FileOpen(READER_FILE, FILE_OPEN_KEEP_POSITION) < 0 ||
            TextEditorRefresh(&g_editor) ||
            !(target_word == READER_NO_WORD ? SeekToVerse(verse) : SeekToWord(verse, target_word))) {
            goto failed;
        }
        ObserveReaderForTesting();
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
    SetCursorMode(CURSOR_MODE_HIDE);
    status = TextEditorInit(&g_editor, READER_FILE, TEXT_EDITOR_EDITABLE,
        READER_MAX_FILE_BYTES, 0, 0, READER_TEXT_WIDTH, 64);
    if(status) {
        goto failed;
    }
    if(!g_body_fonts[0]) {
        unsigned face;
        FontHeader_t* normal = NULL;
        uint8_t provider;
        if(g_settings.font_applet == READER_FONT_AUTOMATIC)
            SelectReadingFont(DefaultReadingFont());
        provider = ResolveReadingFont();
        g_settings.font_applet = provider;
        uint32_t reply = 0;
        if(provider == READER_FONT_SYSTEM_SMALL) normal = SidebarFont();
        else if(provider) AppletSendMessage(provider, MSG_FONT_GET_NORMAL, (uint32_t)&normal, &reply);
        if(!normal) normal = SystemFont();
        for(face = 0; face < 4; ++face) g_body_fonts[face] = normal;
        if(!ReaderProbeConfigureFonts(g_body_fonts)) {
            goto failed;
        }
    }
    g_rich_typography = ConfigureBodyFaces();
    if(!ConfigureVerseFont()) {
        goto failed;
    }
    status = SetReadingFonts();
    if(status) goto failed;
    ShowBusy(false);
    ReaderProbeSet(phase, 3);
    if(!DecodeChapterToFile()) {
        goto failed;
    }
    ReaderProbeSet(phase, 2);
    g_chapter_loaded = 1;
    g_rendered_options = DisplayOptions();
    ReaderProbeSet(phase, 6);
    /* SetScanPosition handles the required layout. Avoid a redundant refresh. */
    if(!(target_word == READER_NO_WORD ? SeekToVerse(verse) : SeekToWord(verse, target_word))) {
        goto failed;
    }
    ObserveReaderForTesting();
    return;

failed:
    ReaderProbeSet(error, status ? status : 1);
    ReaderProbeSet(phase, 5);
    SetCursorMode(CURSOR_MODE_HIDE);
    DrawSystemLine(0, "Unable to open Bible chapter");
}

static void SaveReadingPosition(void) {
    int32_t status;
    unsigned anchor = FileOffsetWithoutGap(g_editor.selection_anchor);
    ReaderProbeSet(phase, 15);
    status = TextEditorSavePosition(&g_editor);
    /* Saving moves the file gap to the caret without rebasing the selection
     * anchor. Keep its logical position in the descriptor across focus changes. */
    if(!status && g_editor.selection_state) {
        g_editor.selection_anchor = anchor + (anchor >= g_editor.gap_start ?
            g_editor.gap_end - g_editor.gap_start : 0);
    }
    ReaderProbeSavedPosition(status, g_current_chapter, g_settings.verse_numbers);
    (void)status;
    FileClose();
    ReaderProbeSet(phase, 16);
}

/* Bypass the optional Betawise console font: the native cursor syscall selects
 * the ROM 6x16 font when showing its cursor, exactly as native TextBox expects. */
extern void _OS3K_SetCursor(uint8_t row, uint8_t column, CursorMode_e mode);
static bool AcceptInput(bool repeat_query);

static void DrawFindLine(unsigned row, const char* text) {
    _OS3K_SetCursor(row + 1, 1, CURSOR_MODE_SHOW);
    SetCursorMode(CURSOR_MODE_HIDE);
    PutStringRaw(text);
}

static void DrawFindFooter(const char* error) {
    RasterOp(0, 48, 264, 16, 0, ROP_WHITENESS);
    DrawFindLine(3, error ? error : "  verse: John 3:16    next: Cmd/Ctrl-Find");
}

static void OpenFind(void) {
    bool repeat_query = g_have_query && !strcmp(g_input, g_last_find);
    const Key_e exits[] = {KEY_ENTER, KEY_ESC, (Key_e)0xfe, KEY_NONE};
    ReaderProbeSet(phase, 20);
    RestoreTransientDisplay();
    CloseFind();
    g_cursor_visible = false;
    g_busy_visible = false;
    ClearScreen();
    DrawFindLine(0, " Find:[                                ]");
    DrawFindLine(1, "  exact: \"so loved\"      search: Enter");
    DrawFindLine(2, " nearby: love* world       exit: Esc");
    DrawFindFooter(0);
    for(;;) {
        g_find_visible = true;
        g_notice_visible = false;
        uint8_t input_length = strlen(g_input);
        _OS3K_SetCursor(1, 8, CURSOR_MODE_SHOW);
        ObserveReaderForTesting();
        unsigned key = TextBox(g_input, &input_length, READER_FIND_MAX, exits, false);
        g_input[input_length] = 0;
        SetCursorMode(CURSOR_MODE_HIDE);
        if(key == KEY_ENTER) {
            if(AcceptInput(repeat_query)) return;
        } else {
            CloseFind();
            if(key == KEY_ESC) RedrawChapter();
            return;
        }
    }
}

/* Canonical prefixes are supplemented by common non-prefix abbreviations. */
static const char g_book_aliases[BIBLE_BOOK_COUNT][14] = {
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
    unsigned size = 0, chapter_number, verse_number = 0;
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
        if(!verse_number) return -1;
    } else if(*scan >= '0' && *scan <= '9') {
        verse_number = ReadReferenceNumber(&scan);
        if(!verse_number) return -1;
    }
    while(*scan == ' ') ++scan;
    if(*scan || !chapter_number || chapter_number > g_books[book].chapters) return -1;
    *chapter = g_books[book].first + chapter_number - 1;
    *verse = verse_number;
    return verse_number <= ReadBigEndian16(BibleVerseCounts + 2 * *chapter) ? 1 : -1;
}

static unsigned FindWordAtOffset(unsigned offset) {
    uint8_t buffer[READER_IO_BYTES];
    unsigned verse = FindVerseAtOffset(offset);
    unsigned end = FileOffsetWithoutGap(offset);
    unsigned position = g_search_offsets[verse];
    unsigned word_count = 0;
    unsigned word_state = 0;
    NativeTextFilter filter = {0, 0};
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
        if(count > sizeof(buffer)) {
            count = sizeof(buffer);
        }
        if(FileSeek(READER_FILE, raw_position, FILE_SEEK_START) < 0) {
            break;
        }
        bytes_read = FileReadBuffer(READER_FILE, buffer, count);
        if(bytes_read <= 0) {
            break;
        }
        for(index = 0; index < (unsigned)bytes_read; ++index) {
            int character = NativeTextCharacter(&filter, buffer[index]);
            if(character < 0) continue;
            if(IsBibleLetter(character)) {
                if(!word_state) {
                    ++word_count;
                }
                word_state = 1;
            } else if(IsBibleApostrophe(character) && word_state == 1) {
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

#define READER_SEARCH_INVALID -3

static int FindDirectionalMatch(const char* query, BibleSearchMode_e mode,
    int direction, unsigned include_origin, const char* new_query) {
    BibleSearch_t search;
    BibleSearchResult_e result = BIBLE_SEARCH_PENDING;
    ReaderProbeSet(phase, 610);
    if(!BibleSearchBegin(&search, BibleData, BibleDataEnd - BibleData,
        BibleSearchData, BibleSearchDataEnd - BibleSearchData, query, mode)) {
        ReaderProbeSet(phase, 611);
        return READER_SEARCH_INVALID;
    }
    ReaderProbeSet(phase, 611);
    if(new_query) {
        strcpy(g_last_find, new_query);
        g_search_mode = mode;
        g_have_query = true;
        ReaderProbeSet(hits, 0);
    }
    if(g_find_visible) RedrawChapter();
    unsigned origin = g_editor.caret_offset;
    bool selected = g_editor.selection_state && g_editor.selection_anchor != origin;
    if(selected && (direction < 0 ? g_editor.selection_anchor > origin : g_editor.selection_anchor < origin))
        origin = g_editor.selection_anchor;
    ReaderProbeSet(phase, 600);
    BibleSearchSetNearbyWords(&search, BIBLE_SEARCH_NEAR_WORDS);
    BibleSearchSetOrigin(&search, g_current_chapter,
        FindVerseAtOffset(origin), FindWordAtOffset(origin), direction, include_origin);
    if(selected) BibleSearchUseSelectionOrigin(&search);
    BibleSearchEnableWrap(&search);
    ReaderProbeSet(phase, 601);
    g_search_active = true;
    ShowBusy(true);
    ObserveReaderForTesting();
    while(result == BIBLE_SEARCH_PENDING && g_search_active) {
        volatile uint8_t due = 0;
        TimerId_t timer = TIMER_ID_INVALID;
        bool timed = TimerStart(READER_SEARCH_SLICE_MS, &due, NULL, &timer) == TIMER_OK;
        uint32_t start = timed ? 0 : GetUptimeMilliseconds();
        ReaderProbeSet(phase, 11);
        do {
            result = BibleSearchStep(&search, READER_SEARCH_BLOCK);
            UpdateBusy();
        } while(result == BIBLE_SEARCH_PENDING && !IsKeyReady() && !IsKeyDownNow() &&
            (timed ? !due : GetUptimeMilliseconds() - start < READER_SEARCH_SLICE_MS));
        /* Firmware special-key handling may abandon this callback's stack.
         * Never leave a timer pointing at it when polling those keys. */
        if(timed) TimerCancel(timer);
        ReaderProbeSet(phase, 12);
        if(result == BIBLE_SEARCH_PENDING) {
            /* Keep the workspace on this stack while polling between bounded
             * slices. Special keys retain their native firmware handling. */
            /* Matrix sampling is cheap; a full ROM scan is expensive. Poll
             * only when a held key needs translating into queued events. */
            if(IsKeyDownNow()) ScanKeyboard();
            while(IsKeyReady()) {
                unsigned key = GetKey(true);
                if(!(key & KEY_MOD_KEY_UP) && (key & 0x7f) == KEY_ESC)
                    g_search_active = false;
            }
        }
    }
    g_search_active = false;
    if(result == BIBLE_SEARCH_FOUND) {
        g_match.chapter = search.chapter;
        g_match.verse = search.verse;
        g_match.word = search.matched_word;
        g_match.end_verse = search.matched_end_verse;
        g_match.end_word = search.matched_end_word;
        g_match.wrapped = search.wrapped;
        ReaderProbeAdd(hits, 1);
    }
    return result;
}

static void FinishSearch(int result) {
    /* FindDirectionalMatch has returned: chapter loading and drawing cannot
     * overlap its large temporary search workspace on the stack. */
    if(!g_focused) return;
    if(result == BIBLE_SEARCH_PENDING) RedrawChapter();
    else if(result == BIBLE_SEARCH_COMPLETE) ShowSearchNotice(READER_SEARCH_NOT_FOUND);
    else if(result != BIBLE_SEARCH_FOUND) ShowNotice("Search decode error");
    else if(g_match.wrapped) ShowSearchNotice(READER_SEARCH_WRAPPED);
    else {
        OpenChapter(g_match.chapter, g_match.verse, g_match.word);
        SelectSearchMatch();
    }
}

static void StartDirectionalSearch(int direction, unsigned include_origin) {
    char query[BIBLE_SEARCH_QUERY_BYTES];
    const char* start = g_last_find;
    unsigned length;
    if(!g_have_query) { OpenFind(); return; }
    while(*start == ' ') ++start;
    length = strlen(start);
    while(length && start[length - 1] == ' ') --length;
    if(g_search_mode == BIBLE_SEARCH_PHRASE) { ++start; length -= 2; }
    memcpy(query, start, length);
    query[length] = 0;
    FinishSearch(FindDirectionalMatch(query, g_search_mode, direction, include_origin, NULL));
}

static unsigned VerseTextEnd(unsigned verse) {
    return g_verse_ends[verse];
}

static int WriteClipboardBytes(const void* bytes, unsigned count) {
    if(FileWriteBuffer(FILE_ID_CLIPBOARD, bytes, count, FILE_WRITE_APPEND) != (int)count) return 0;
    ReaderProbeAdd(copied, count);
    return 1;
}

static void CopySelectedVerses(void) {
    RestoreTransientDisplay();
    uint8_t buffer[READER_IO_BYTES];
    unsigned first_verse = FindVerseAtOffset(g_editor.caret_offset);
    unsigned last_verse = first_verse;
    unsigned start = VerseTextOffset(first_verse);
    unsigned end = VerseTextEnd(last_verse);
    unsigned position, buffered = 0;
    bool copy_has_text = false, copy_space_pending = false;
    NativeTextFilter filter = {0, 0};
    int32_t saved_position = FileTell(READER_FILE);
    char citation[88];

    if(g_editor.selection_state && g_editor.selection_anchor != g_editor.caret_offset) {
        unsigned raw_start = g_editor.caret_offset < g_editor.selection_anchor ?
            g_editor.caret_offset : g_editor.selection_anchor;
        unsigned raw_end = g_editor.caret_offset > g_editor.selection_anchor ?
            g_editor.caret_offset : g_editor.selection_anchor;
        start = FileOffsetWithoutGap(raw_start);
        end = FileOffsetWithoutGap(raw_end);
        first_verse = FindVerseAtOffset(raw_start);
        last_verse = FindVerseAtOffset(raw_end - 1);
        while(first_verse <= last_verse && start >= VerseTextEnd(first_verse)) ++first_verse;
        while(last_verse >= first_verse && end <= VerseTextOffset(last_verse)) --last_verse;
        if(first_verse > last_verse) {
            ShowStatusMessage("Select Bible text", 2000);
            return;
        }
    }
    bool omitted_start = start > VerseTextOffset(first_verse);
    bool omitted_end = end < VerseTextEnd(last_verse);
    if(ClipboardSet(buffer, 0, 1) < 0) {
        ShowNotice("Clipboard unavailable");
        return;
    }
    ReaderProbeSet(copied, 0);
    if(omitted_start && !WriteClipboardBytes("... ", 4)) goto failed;
    /* Begin before the verse's first style record, even for a partial selection,
     * so the region filter has its true state at the selection boundary. */
    position = g_verse_offsets[first_verse];
    while(position < end) {
        uint8_t input[READER_IO_BYTES];
        unsigned count = end - position, index;
        unsigned raw = position + (position >= g_editor.gap_start ?
            g_editor.gap_end - g_editor.gap_start : 0);
        int read;
        if(position < g_editor.gap_start && count > g_editor.gap_start - position)
            count = g_editor.gap_start - position;
        if(count > sizeof(input)) count = sizeof(input);
        if(FileSeek(READER_FILE, raw, FILE_SEEK_START) < 0 ||
            (read = FileReadBuffer(READER_FILE, input, count)) <= 0) goto failed;
        for(index = 0; index < (unsigned)read; ++index) {
            int character = NativeTextCharacter(&filter, input[index]);
            if(character < 0 || (filter.flags & 1)) continue;
            /* These slots are quotes in body faces, but digits in face four.
             * Keep visible digits available to layout/caret measurement. */
            if((filter.flags & 12) == 12 && character >= VERSE_DIGIT_CHARACTER &&
                character < VERSE_DIGIT_CHARACTER + 10) continue;
            if(!IsBibleQuote(character) && !NeoSmallCapsCanonicalSource(character) &&
                (character < 32 || character > 126)) {
                if(character != '\r') continue;
                character = ' ';
            }
            if(position + index >= start) {
                if(character == ' ') {
                    copy_space_pending = copy_has_text;
                    continue;
                }
                if(copy_space_pending) {
                    buffer[buffered++] = ' ';
                    if(buffered == sizeof(buffer)) {
                        if(!WriteClipboardBytes(buffer, buffered)) goto failed;
                        buffered = 0;
                    }
                    copy_space_pending = false;
                }
                buffer[buffered++] = character;
                copy_has_text = true;
                if(buffered == sizeof(buffer)) {
                    if(!WriteClipboardBytes(buffer, buffered)) goto failed;
                    buffered = 0;
                }
            }
        }
        position += read;
    }
    FileSeek(READER_FILE, saved_position, FILE_SEEK_START);
    if(buffered && !WriteClipboardBytes(buffer, buffered)) goto failed;
    if(omitted_end && !WriteClipboardBytes(" ...", 4)) goto failed;
    if(!WriteClipboardBytes("\r", 1)) goto failed;
    FormatCitation(citation, g_current_chapter, first_verse);
    if(last_verse > first_verse) {
        unsigned book = FindBookForChapter(g_current_chapter);
        sprintf(citation, "%s %u:%u-%u (%s)", g_books[book].name,
            g_current_chapter - g_books[book].first + 1, first_verse, last_verse, BIBLE_VERSION);
    }
    if(!WriteClipboardBytes(citation, strlen(citation))) goto failed;
    ShowStatusMessage("Copied", 2000);
    return;

failed:
    FileSeek(READER_FILE, saved_position, FILE_SEEK_START);
    ClipboardClear();
    ShowNotice("Not enough clipboard memory");
}

static bool AcceptInput(bool repeat_query) {
    unsigned chapter, verse;
    char query[BIBLE_SEARCH_QUERY_BYTES];
    const char* start = g_input;
    unsigned length;
    int reference = ParseReference(g_input, &chapter, &verse);
    if(reference) {
        if(reference < 0) DrawFindFooter(" Invalid or ambiguous reference");
        else {
            g_input[0] = 0;
            CloseFind();
            OpenChapter(chapter, verse ? verse : 1, READER_NO_WORD);
            if(verse && g_chapter_loaded && g_current_chapter == chapter && !g_notice_visible) {
                SelectVerseLookup(verse);
            }
            ObserveReaderForTesting();
            return true;
        }
        return false;
    }
    while(*start == ' ') ++start;
    length = strlen(start);
    while(length && start[length - 1] == ' ') --length;
    if(!length) { DrawFindFooter(" Enter words or a verse reference"); return false; }
    BibleSearchMode_e search_mode = BIBLE_SEARCH_NEARBY;
    if(start[0] == '"') {
        if(length < 2 || start[length - 1] != '"') {
            DrawFindFooter(" Close the phrase with a double quote");
            return false;
        }
        ++start;
        length -= 2;
        search_mode = BIBLE_SEARCH_PHRASE;
    }
    memcpy(query, start, length);
    query[length] = 0;
    if(strchr(query, '"')) {
        DrawFindFooter(" Put quotes around the whole phrase");
        return false;
    }
    if(search_mode == BIBLE_SEARCH_PHRASE && strchr(query, '*')) {
        DrawFindFooter(" Use * only outside quoted phrases");
        return false;
    }
    if(repeat_query && g_have_query && search_mode == g_search_mode && !strcmp(g_input, g_last_find)) {
        RedrawChapter();
        StartDirectionalSearch(1, 0);
        return true;
    }
    int result = FindDirectionalMatch(query, search_mode, 1, 1, g_input);
    if(result == READER_SEARCH_INVALID) {
        DrawFindFooter(" Use 1-8 words; * only at word endings");
        return false;
    }
    FinishSearch(result);
    return true;
}

typedef struct {
    char label[9];
    char keys[24];
} HelpRow;

static const HelpRow g_help_left[] = {
    {"Page", "Space / Shift Space"},
    {"Chapter", ", .  [ ]  < >"},
    {"Find", "Find"},
    {"Next", "Ctrl Find"},
    {"Prev", "Ctrl Shift Find"},
    {"Copy", "Ctrl C"}
};
static const HelpRow g_help_right[] = {
    {"I", "Toggle italics"},
    {"H", "Toggle headings"},
    {"V", "Verse numbers"},
    {"F", "Font"},
    {"?", "Help"},
    {"Esc", "Back"}
};

static unsigned FontTextWidth(FontHeader_t* font, const char* text) {
    unsigned width = 0;
    while(*text) width += GlyphWidth(font, (uint8_t)*text++);
    return width;
}

static void DrawFontText(FontHeader_t* font, unsigned x, unsigned y, const char* text) {
    while(*text) {
        unsigned character = (uint8_t)*text++, width = GlyphWidth(font, character);
        DrawBitmap(x, y, width, font->height, GlyphBitmap(font, character));
        x += width;
    }
}

static void DrawHelpColumn(FontHeader_t* font, unsigned left, unsigned width,
    unsigned colon, const char* title, const HelpRow* rows, unsigned count) {
    unsigned index;
    DrawFontText(font, left + (width - FontTextWidth(font, title)) / 2, 0, title);
    RasterOp(left, 0, width, font->height, NULL, ROP_DSTINVERT);
    for(index = 0; index < count; ++index) {
        unsigned y = 10 + 9 * index;
        DrawFontText(font, left + colon - 2 - FontTextWidth(font, rows[index].label), y, rows[index].label);
        DrawFontText(font, left + colon, y, ":");
        DrawFontText(font, left + colon + GlyphWidth(font, ':') + 3, y, rows[index].keys);
    }
}

static void ShowHelp(void) {
    FontHeader_t* font = SidebarFont();
    g_notice_deadline = 0;
    g_status_visible = 0;
    ClearScreen();
    SetCursor(1, 1, CURSOR_MODE_HIDE);
    DrawHelpColumn(font, 0, 145, 38, "Read / find", g_help_left, sizeof(g_help_left) / sizeof(*g_help_left));
    DrawHelpColumn(font, 145, 119, 34, "Display / font", g_help_right, sizeof(g_help_right) / sizeof(*g_help_right));
    g_notice_visible = 1;
    ObserveReaderForTesting();
}

static void ShowReadingFontMenu(void) {
    CloseFind();
    ClearScreen();
    SetCursor(1, 1, CURSOR_MODE_HIDE);
    ReaderProbeSet(phase,601);
    FontPickerBegin(FontAppletName,g_settings.font_applet);
    if(!FontPickerOpen()) { RedrawChapter(); return; }
    g_font_menu_visible = true;
    ReaderProbeSet(phase,602);
    ObserveReaderForTesting();
    return;
}

static void ChangeChapter(int direction) {
    int chapter = g_current_chapter + direction;
    if(chapter >= 0 && chapter < BIBLE_CHAPTER_COUNT) OpenChapter(chapter, 1, READER_NO_WORD);
    else ObserveReaderForTesting();
}

static void PageChapter(bool reverse) {
    TextScan_t position;
    int32_t status = 0;
    /* Native page movement advances the caret, then scrolls only enough to
     * expose it. A reader instead anchors each page at the viewport's top. */
    if(TextScanInit(&g_editor, &position, TEXT_POSITION_VIEWPORT)) return;
    if(g_editor.selection_state)
        TextEditorHandleMessage(&g_editor, MSG_KEY, KEY_LEFT, 0, &status);
    if(status || TextEditorSetScanPosition(&position, false)) return;
    g_cursor_visible = false;
    TextEditorHandleMessage(&g_editor, MSG_KEY,
        KEY_MOD_CMD | (reverse ? KEY_UP : KEY_DOWN), 0, &status);
    if(!status && !g_editor.caret_x &&
        FileOffsetWithoutGap(g_editor.caret_offset) < g_chapter_file_bytes) {
        g_editor.viewport_offset = g_editor.caret_offset;
        g_editor.viewport_scan_flags = g_editor.caret_scan_flags;
        g_editor.viewport_scan_line = g_editor.caret_scan_line;
        g_editor.caret_y = 0;
    }
    ReaderProbeSet(error, status);
    /* Reflow would move the viewport back to keep context above the caret. */
    RedrawChapterWithMode(READER_PAINT_VIEWPORT);
}

/* Visibility records use protected-only when shown and hidden-only when hidden.
 * Both masks are nonzero, so native normalization retains their bytes. Combining
 * hidden/protected bits can remove adjacent records during reflow. Inside the
 * private face the wrappers surround verse digits; elsewhere they mark headings. */
static bool SetRegionVisibility(unsigned region, bool visible) {
    uint8_t buffer[READER_IO_BYTES];
    unsigned position = 0, token = 0, flags = 0, begin = 0;
    int32_t saved_position = FileTell(READER_FILE);
    while(position < g_chapter_file_bytes) {
        unsigned raw = position, length = g_chapter_file_bytes - position, index;
        int bytes;
        if(position < g_editor.gap_start && length > g_editor.gap_start - position)
            length = g_editor.gap_start - position;
        if(position >= g_editor.gap_start) raw += g_editor.gap_end - g_editor.gap_start;
        if(length > sizeof(buffer)) length = sizeof(buffer);
        if(FileSeek(READER_FILE, raw, FILE_SEEK_START) < 0) return false;
        bytes = FileReadBuffer(READER_FILE, buffer, length);
        if(bytes <= 0) return false;
        for(index = 0; index < (unsigned)bytes; ++index) {
            unsigned character = buffer[index];
            if(token == 1) {
                bool number_region = (flags & VERSE_FONT_FACE_FLAGS) == VERSE_FONT_FACE_FLAGS;
                if((character == READER_REGION_PROTECTED || character == READER_REGION_HIDDEN) &&
                    number_region == region) {
                    uint8_t mask = visible ? READER_REGION_PROTECTED : READER_REGION_HIDDEN;
                    if(FileSeek(READER_FILE, raw + index, FILE_SEEK_START) < 0 ||
                        FileWriteBuffer(READER_FILE, &mask, 1, FILE_WRITE_OVERWRITE) != 1) return false;
                    character = mask;
                }
                flags = begin ? flags | character : flags & ~character;
                token = 2;
            } else if(token == 2) token = 0;
            else if(character == VERSE_FONT_BEGIN || character == VERSE_FONT_END) {
                token = 1;
                begin = character == VERSE_FONT_BEGIN;
            }
#if BIBLEWISE_ITALICS_PROTOTYPE == 6
            else if(region == 2 && (flags & 0x1C) == 0x1C) {
                /* Only source-italic small-cap letters carry this combination.
                 * A preference toggle exchanges their Regular/Italic slots. */
                uint8_t glyph = character ^ 0x2B;
                if(FileSeek(READER_FILE, raw + index, FILE_SEEK_START) < 0 ||
                    FileWriteBuffer(READER_FILE, &glyph, 1, FILE_WRITE_OVERWRITE) != 1) return false;
            }
#endif
        }
        position += bytes;
    }
    FileSeek(READER_FILE, saved_position, FILE_SEEK_START);
    return true;
}

/* After native wrapping, measure only the displayed prefix to the caret.
 * Soft line breaks are already cached by the ROM; this performs no word wrap. */
static bool RestoreCaretInViewport(unsigned position, const TextScan_t* viewport) {
    uint8_t buffer[READER_IO_BYTES];
    NativeTextFilter filter = {0, viewport->flags};
    unsigned start = FileOffsetWithoutGap(viewport->offset), x = 0, y = 0;
    TextScan_t caret;
    if(position < start) return false;
    while(start < position) {
        unsigned length = position - start, raw = start, index;
        int bytes;
        if(start < g_editor.gap_start && length > g_editor.gap_start - start)
            length = g_editor.gap_start - start;
        if(start >= g_editor.gap_start) raw += g_editor.gap_end - g_editor.gap_start;
        if(length > sizeof(buffer)) length = sizeof(buffer);
        if(FileSeek(READER_FILE, raw, FILE_SEEK_START) < 0) return false;
        bytes = FileReadBuffer(READER_FILE, buffer, length);
        if(bytes <= 0) return false;
        for(index = 0; index < (unsigned)bytes; ++index) {
            unsigned character = buffer[index], width;
            if(NativeTextCharacter(&filter, character) < 0 || (filter.flags & 1)) continue;
            if(character == 13 || character == NATIVE_WRAP_SPACE) {
                x = 0;
                y += g_body_fonts[0]->height;
                continue;
            }
            bool wrapped_hyphen = character == NATIVE_WRAP_HYPHEN;
            if(wrapped_hyphen) character = '-';
            width = GlyphWidth(g_editor.fonts[(filter.flags >> 2) & 3], character);
            if(x + width > READER_TEXT_WIDTH) {
                x = 0;
                y += g_body_fonts[0]->height;
            }
            x += width;
            if(wrapped_hyphen) {
                x = 0;
                y += g_body_fonts[0]->height;
            }
        }
        start += bytes;
    }
    /* If reflow moves the caret beyond this page, let the caller use native
     * positioning rather than losing the caret or changing a selection. */
    if(y >= g_editor.height) return false;
    caret = *viewport;
    if(position >= g_editor.gap_start) position += g_editor.gap_end - g_editor.gap_start;
    TextScanRead(&caret, position - caret.offset, NULL, false, TEXT_BYTES_ENCODED,
        false, false, false, true, NULL);
    if(caret.offset != position) return false;
    g_editor.caret_offset = caret.offset;
    g_editor.caret_scan_flags = caret.flags;
    g_editor.caret_scan_line = caret.line_state;
    g_editor.caret_x = x;
    g_editor.caret_y = y;
    return true;
}

typedef struct {
    unsigned top, caret, anchor, selection_state;
    bool cursor_visible;
} ReadingView;

static void SaveReadingView(ReadingView* view) {
    view->top = FileOffsetWithoutGap(g_editor.viewport_offset);
    view->caret = FileOffsetWithoutGap(g_editor.caret_offset);
    view->anchor = FileOffsetWithoutGap(g_editor.selection_anchor);
    view->selection_state = g_editor.selection_state;
    view->cursor_visible = g_cursor_visible;
}

static bool RestoreReadingView(const ReadingView* view) {
    TextScan_t viewport, selection;
    unsigned anchor = view->anchor;
    int32_t status = 0;
    if(!PositionCaretAtOffset(view->top, false)) return false;
    ReaderProbeSet(phase, 503);
    if(g_editor.caret_x) TextEditorHandleMessage(&g_editor, MSG_KEY, KEY_MOD_CMD | KEY_LEFT, 0, &status);
    if(status || TextScanInit(&g_editor, &viewport, TEXT_POSITION_CARET)) return false;
    ReaderProbeSet(phase, 504);
    g_editor.viewport_offset = viewport.offset;
    g_editor.viewport_scan_flags = viewport.flags;
    g_editor.viewport_scan_line = viewport.line_state;
    g_editor.caret_y = 0;
    if(!RestoreCaretInViewport(view->caret, &viewport) && !PositionCaretAtOffset(view->caret, false)) return false;
    if(view->selection_state) {
        selection = viewport;
        if(anchor >= g_editor.gap_start) anchor += g_editor.gap_end - g_editor.gap_start;
        bool reverse = anchor < selection.offset;
        unsigned distance = reverse ? selection.offset - anchor : anchor - selection.offset;
        TextScanRead(&selection, distance, NULL, reverse, TEXT_BYTES_ENCODED,
            false, false, false, true, NULL);
        if(selection.offset != anchor) return false;
        g_editor.selection_anchor = selection.offset;
        g_editor.selection_flags = selection.flags;
        g_editor.selection_state = view->selection_state;
    }
    g_cursor_visible = view->cursor_visible;
    ReaderProbeSet(phase, 505);
    return true;
}

#if BIBLEWISE_TEST
#include "../../research/bible-reader/offset-rebuild-probe.h"
#endif

#if BIBLEWISE_ITALICS_PROTOTYPE == 5
#include "../../research/bible-reader/smallcaps-italics/rebuild-view.h"
#endif

static void ToggleReadingOption(bool* option) {
    ReadingView view;
    int32_t status;
    SaveReadingView(&view);
    ReaderProbeSet(phase, 669);
#if BIBLEWISE_ITALICS_PROTOTYPE == 5
    RebuildPoint points[3];
    if(option == &g_settings.italics) {
        SaveRebuildPoint(view.top, &points[0]);
        SaveRebuildPoint(view.caret, &points[1]);
        SaveRebuildPoint(view.anchor, &points[2]);
    }
#endif
    *option = !*option;
    ShowBusy(false);
    if(option == &g_settings.italics) {
        g_rich_typography = ConfigureBodyFaces();
        if(!ConfigureVerseFont()) return;
#if BIBLEWISE_ITALICS_PROTOTYPE
        ReaderProbeSet(phase, 670);
#if BIBLEWISE_ITALICS_PROTOTYPE == 5
        /* Reuse the normal chapter-loading path without displaying its initial
         * viewport. Source anchors account for regenerated alignment padding. */
        if(FileSeek(READER_FILE, 0, FILE_SEEK_START) < 0 || FileEraseCurrent() < 0 ||
            TextEditorInit(&g_editor, READER_FILE, TEXT_EDITOR_EDITABLE,
                READER_MAX_FILE_BYTES, 0, 0, READER_TEXT_WIDTH, 64) || SetReadingFonts()) return;
        g_chapter_file_bytes = 0;
        if(!DecodeChapterToFile()) return;
        view.top = RestoreRebuildPoint(&points[0]);
        view.caret = RestoreRebuildPoint(&points[1]);
        view.anchor = RestoreRebuildPoint(&points[2]);
#elif BIBLEWISE_ITALICS_PROTOTYPE == 6
        if(!SetRegionVisibility(2, g_settings.italics)) return;
#else
        if(!RewriteSmallCapItalics(g_settings.italics)) { ReaderProbeSet(error, 670); return; }
#endif
        ReaderProbeSet(phase, 671);
#endif
    } else if(!SetRegionVisibility(option == &g_settings.verse_numbers, *option)) return;
    ReaderProbeSet(phase, 501);
    status = SetReadingFonts();
    ReaderProbeSet(phase, 502);
    if(status) { ReaderProbeSet(error, status); return; }
    g_rendered_options = DisplayOptions();
    if(!RestoreReadingView(&view)) return;
    RedrawChapterWithMode(READER_PAINT_VIEWPORT);
    ReaderProbeSet(phase, 506);
    ReaderProbeSet(phase, 672);
#if BIBLEWISE_TEST
    ProbeRebuildVerseOffsets();
#endif
    ObserveReaderForTesting();
}

static void HandleCharacter(unsigned character) {
    RestoreTransientDisplay();
    if(g_notice_visible) {
        RedrawChapter();
    }
    switch(character) {
        case '/':
            OpenFind();
            break;
        case 'f':
        case 'F':
            ShowReadingFontMenu();
            break;
        case 'n':
        case 'N':
            StartDirectionalSearch(1, 0);
            break;
        case 'p':
        case 'P':
            StartDirectionalSearch(-1, 0);
            break;
        case 'v':
        case 'V':
            ToggleReadingOption(&g_settings.verse_numbers);
            break;
        case ',':
        case '[':
        case '{':
        case '<':
            ChangeChapter(-1);
            break;
        case '.':
        case ']':
        case '}':
        case '>':
            ChangeChapter(1);
            break;
        case 'i':
        case 'I':
            ToggleReadingOption(&g_settings.italics);
            break;
        case 'h':
        case 'H':
            ToggleReadingOption(&g_settings.headings);
            break;
        case '?':
            ShowHelp();
            break;
        case ' ':
            PageChapter((GetKeyModifiers() & KEY_MOD_SHIFT) != 0);
            break;
    }
}

static void HandleKey(uint32_t parameter) {
    unsigned key = parameter & 0x7f;
    int32_t status = 0;
    switch(key) {
        case KEY_CTRL:
        case KEY_ALT:
        case KEY_CMD:
        case KEY_LEFTSHIFT:
        case KEY_RIGHTSHIFT:
            return;
    }
    RestoreTransientDisplay();
    if(key == KEY_ESC) {
        g_search_active = false;
        RedrawChapter();
        return;
    }
    if(g_search_active) {
        return;
    }
    switch(key) {
        case KEY_G:
            if(parameter & (KEY_MOD_CMD | KEY_MOD_CTRL)) {
                StartDirectionalSearch(parameter & KEY_MOD_SHIFT ? -1 : 1, 0);
            }
            break;
        case KEY_F:
            if((parameter & (KEY_MOD_CTRL | KEY_MOD_CMD | KEY_MOD_ALT)) ==
                (KEY_MOD_CTRL | KEY_MOD_CMD | KEY_MOD_ALT)) {
                ShowReadingFontMenu();
                break;
            }
            if(!(parameter & (KEY_MOD_CMD | KEY_MOD_CTRL))) {
                break;
            }
            OpenFind();
            break;
        case KEY_FIND:
            if(parameter & (KEY_MOD_CMD | KEY_MOD_CTRL)) {
                StartDirectionalSearch(parameter & KEY_MOD_SHIFT ? -1 : 1, 0);
            } else {
                OpenFind();
            }
            break;
        case KEY_H:
            if(parameter & (KEY_MOD_CMD | KEY_MOD_CTRL)) ToggleReadingOption(&g_settings.headings);
            break;
        case KEY_I:
            if(parameter & (KEY_MOD_CMD | KEY_MOD_CTRL)) ToggleReadingOption(&g_settings.italics);
            break;
        case KEY_C:
            if(parameter & KEY_MOD_CTRL) {
                CopySelectedVerses();
            }
            break;
        case KEY_UP:
        case KEY_DOWN:
        case KEY_LEFT:
        case KEY_RIGHT:
            if((parameter & KEY_MOD_ALT) && !(parameter & KEY_MOD_SHIFT)) {
                ChangeChapter(key == KEY_DOWN || key == KEY_RIGHT ? 1 : -1);
                break;
            }
            /* fall through */
        case KEY_HOME:
        case KEY_END: {
            if(g_notice_visible) {
                break;
            }
            bool page = (parameter & KEY_MOD_CMD) && (key == KEY_UP || key == KEY_DOWN);
            if(page && !(parameter & KEY_MOD_SHIFT)) {
                PageChapter(key == KEY_UP);
                break;
            }
            if(page) {
                g_cursor_visible = false;
            } else if(key != KEY_HOME && key != KEY_END) {
                g_cursor_visible = true;
            }
            unsigned previous = g_editor.caret_offset;
            TextEditorHandleMessage(&g_editor, MSG_KEY, parameter, 0, &status);
            ReaderProbeSet(error, status);
            ApplyReadingCursor();
            if(key == KEY_HOME || key == KEY_END || (parameter & KEY_MOD_CMD) ||
                ((key == KEY_UP || key == KEY_DOWN) && previous == g_editor.caret_offset)) {
                ObserveReaderForTesting();
            } else {
                ObserveReaderForTesting();
            }
            break;
        }
    }
}

void ProcessMessage(Message_e message, uint32_t parameter, uint32_t* reply) {
    *reply = 0;
    if(g_font_menu_visible) {
        if(message == MSG_KILLFOCUS) {
            FontPickerClose();
            g_font_menu_visible = false;
        } else {
            if((message == MSG_KEY && !(parameter & KEY_MOD_KEY_UP)) ||
               (message == MSG_CHAR && parameter == '\r')) {
                unsigned key = message == MSG_CHAR ? KEY_ENTER : parameter & 0x7f;
                if(key == KEY_ENTER || key == KEY_ESC) {
                    uint16_t id = FontPickerChoice();
                    unsigned verse = FindVerseAtOffset(g_editor.caret_offset);
                    FontPickerClose(); g_font_menu_visible = false;
                    if(key == KEY_ENTER && id != g_settings.font_applet) {
                        SelectReadingFont(id); g_body_fonts[0] = NULL;
                        g_chapter_loaded = false;
                        OpenChapter(g_current_chapter, verse, READER_NO_WORD);
                    } else RedrawChapter();
                } else {
                    ReaderProbeSet(phase,601);
                    if(key == KEY_UP) FontPickerMove(-1, 0);
                    else if(key == KEY_DOWN) FontPickerMove(1, 0);
                    else if(key == KEY_LEFT) FontPickerMove(0, -1);
                    else if(key == KEY_RIGHT) FontPickerMove(0, 1);
                    else if(key == KEY_HOME) FontPickerEdge(false);
                    else if(key == KEY_END) FontPickerEdge(true);
                    ReaderProbeSet(phase,603);
                    FontPickerDraw();
                    ReaderProbeSet(phase,602);
                    ObserveReaderForTesting();
                }
            } else if(message == READER_REDRAW_MESSAGE) FontPickerRedraw();
            return;
        }
    }
    if(message == MSG_SETFOCUS) {
        g_focused = true;
        if(!g_ready) {
            ReaderProbeSet(magic, 0x42524452);
            ReaderProbeSelectSystemFont();
            g_ready = ValidateBibleData();
        }
        if(g_ready) {
            if(g_settings.font_applet && g_settings.font_applet != READER_FONT_AUTOMATIC) {
                unsigned index = ResolveReadingFont();
                FontHeader_t* font = NULL;
                uint32_t status = 0;
                if(index == READER_FONT_SYSTEM_SMALL) font = SidebarFont();
                else if(index) AppletSendMessage(index, MSG_FONT_GET_NORMAL, (uint32_t)&font, &status);
                if(!font) {
                    SelectReadingFont(0);
                    g_body_fonts[0] = NULL;
                    g_chapter_loaded = false;
                } else {
                    g_settings.font_applet = index;
                    if(font != g_body_fonts[0]) {
                        g_body_fonts[0] = font;
                        g_rich_typography = ConfigureBodyFaces();
                        if(!ConfigureVerseFont()) return;
                    }
                }
            }
            g_cursor_visible = false;
            if(g_chapter_loaded) {
                ReadingView view;
                SaveReadingView(&view);
                /* Refresh reloads shared system fonts; restore the reader's own
                 * descriptors before restoring its viewport and selection. */
                if(FileOpen(READER_FILE, FILE_OPEN_KEEP_POSITION) < 0 || TextEditorRefresh(&g_editor) ||
                    SetReadingFonts() || !RestoreReadingView(&view)) {
                    ReaderProbeSet(error, 1);
                    return;
                }
                ClearScreen();
                DrawSidebar();
                RedrawChapterWithMode(READER_PAINT_VIEWPORT);
            } else {
                OpenChapter(g_current_chapter, 1, READER_NO_WORD);
            }
        }
    } else if(message == MSG_KILLFOCUS) {
        g_focused = false;
        g_search_active = false;
        g_font_menu_visible = false;
        RestoreTransientDisplay();
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
    } else if(g_ready && message == READER_REDRAW_MESSAGE) {
        RestoreTransientDisplay();
        CloseFind();
        if(g_chapter_loaded) {
            if(parameter == READER_RELOAD_FONTS) {
                ShowReadingFontMenu();
            } else {
                RedrawChapter();
            }
        }
    } else if(g_ready && message == MSG_KEY && !(parameter & KEY_MOD_KEY_UP)) {
        HandleKey(parameter);
    } else if(g_ready && !g_search_active && message == MSG_CHAR) {
        if(parameter == 3 && !g_find_visible) {
            CopySelectedVerses();
        } else if(!(GetKeyModifiers() & (KEY_MOD_CTRL | KEY_MOD_CMD | KEY_MOD_ALT))) {
            HandleCharacter(parameter);
        }
    }
}
