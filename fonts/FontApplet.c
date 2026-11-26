#include "os3k.h"
#include FONT_GLYPHS
#ifdef FONT_BOLD_GLYPHS
#include FONT_BOLD_GLYPHS
_Static_assert(BOLD_GLYPH_HEIGHT == GLYPH_HEIGHT, "bold height differs");
#endif
#ifdef FONT_ITALIC_GLYPHS
#include FONT_ITALIC_GLYPHS
_Static_assert(ITALIC_GLYPH_HEIGHT == GLYPH_HEIGHT, "italic height differs");
#endif
#ifdef FONT_BOLD_ITALIC_GLYPHS
#include FONT_BOLD_ITALIC_GLYPHS
_Static_assert(BOLD_ITALIC_GLYPH_HEIGHT == GLYPH_HEIGHT, "bold italic height differs");
#endif

#ifdef FONT_PRIVATE_GLYPHS
#include FONT_PRIVATE_GLYPHS
_Static_assert(PRIVATE_GLYPH_HEIGHT == GLYPH_HEIGHT, "private height differs");
#endif

#define STRINGIFY_VALUE(value) #value
#define STRINGIFY(value) STRINGIFY_VALUE(value)
#ifdef FONT_COLUMNS
#define FONT_APPLET_NAME "BetaWise - " FONT_MENU_NAME " (" STRINGIFY(FONT_COLUMNS) "x" STRINGIFY(FONT_LINES) ")"
#else
#define FONT_APPLET_NAME "BetaWise - " FONT_MENU_NAME " (" STRINGIFY(FONT_LINES) " lines)"
#endif
_Static_assert(sizeof(FONT_APPLET_NAME) <= 36, "font applet name too long");
_Static_assert(sizeof(FONT_INFO) <= 60, "font information too long");

APPLET_HEADER_BEGIN
    APPLET_FLAGS(APPLET_FLAG_FONT | APPLET_FLAG_HIDDEN)
    APPLET_ID(FONT_ID)
    APPLET_NAME(FONT_APPLET_NAME)
    APPLET_INFO(FONT_INFO)
    APPLET_VERSION(BETAWISE_VERSION_MAJOR, BETAWISE_VERSION_MINOR, BETAWISE_VERSION_REVISION)
    APPLET_LANGUAGE_EN_US
APPLET_HEADER_END

void BwProcessMessage(Message_e message, uint32_t param, uint32_t *status) {
    *status = 0;
    switch (message) {
        case MSG_FONT_GET_NAME:
            *(const char **)param = FONT_NAME;
            break;
        case MSG_FONT_GET_NORMAL:
            *(const FontHeader_t **)param = &GLYPH_FONT;
            break;
        case MSG_FONT_GET_BOLD:
#ifdef BOLD_GLYPH_HEIGHT
            *(const FontHeader_t **)param = &BOLD_GLYPH_FONT;
#else
            *(const FontHeader_t **)param = 0;
#endif
            break;
        case MSG_FONT_GET_ITALIC:
#ifdef ITALIC_GLYPH_HEIGHT
            *(const FontHeader_t **)param = &ITALIC_GLYPH_FONT;
#else
            *(const FontHeader_t **)param = 0;
#endif
            break;
        case MSG_FONT_GET_BOLD_ITALIC:
#ifdef BOLD_ITALIC_GLYPH_HEIGHT
            *(const FontHeader_t **)param = &BOLD_ITALIC_GLYPH_FONT;
#else
            *(const FontHeader_t **)param = 0;
#endif
            break;
        case MSG_FONT_GET_PRIVATE:
#ifdef PRIVATE_GLYPH_HEIGHT
            *(const FontHeader_t **)param = &PRIVATE_GLYPH_FONT;
#else
            *(const FontHeader_t **)param = 0;
#endif
            break;
        case MSG_FONT_GET_HEIGHT:
            *(uint32_t *)param = GLYPH_HEIGHT;
            break;
    }
}
