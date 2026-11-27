#include "os3k.h"
#define FONT_RUNTIME_DESCRIPTORS
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

/* Only descriptors consume RAM. Firmware supplies this base in A5 on every
 * dispatch. They are filled on demand, so getters do not depend on MSG_INIT. */
#ifdef BOLD_GLYPH_HEIGHT
#define FONT_FACE_COUNT 5
#else
#define FONT_FACE_COUNT 1
#endif
static FontHeader_t descriptor_storage[FONT_FACE_COUNT]
    __attribute__((used, section(".font.ram")));

void Os3kEntry(Message_e, uint32_t, uint32_t *)
    __attribute__((alias("BwProcessMessage")));

static const char font_name[] = FONT_NAME;

register FontHeader_t *fonts asm("a5");

void BwProcessMessage(Message_e message, uint32_t param, uint32_t *status) {
    *status = 0;
    switch (message) {
        case MSG_FONT_GET_NAME:
            *(const char **)param = font_name;
            break;
        case MSG_FONT_GET_NORMAL:
            GLYPH_INIT(&fonts[0]);
            *(const FontHeader_t **)param = &fonts[0];
            break;
        case MSG_FONT_GET_BOLD:
#ifdef BOLD_GLYPH_HEIGHT
            BOLD_GLYPH_INIT(&fonts[1]);
            *(const FontHeader_t **)param = &fonts[1];
#else
            *(const FontHeader_t **)param = 0;
#endif
            break;
        case MSG_FONT_GET_ITALIC:
#ifdef ITALIC_GLYPH_HEIGHT
            ITALIC_GLYPH_INIT(&fonts[2]);
            *(const FontHeader_t **)param = &fonts[2];
#else
            *(const FontHeader_t **)param = 0;
#endif
            break;
        case MSG_FONT_GET_BOLD_ITALIC:
#ifdef BOLD_ITALIC_GLYPH_HEIGHT
            BOLD_ITALIC_GLYPH_INIT(&fonts[3]);
            *(const FontHeader_t **)param = &fonts[3];
#else
            *(const FontHeader_t **)param = 0;
#endif
            break;
        case MSG_FONT_GET_PRIVATE:
#ifdef PRIVATE_GLYPH_HEIGHT
            PRIVATE_GLYPH_INIT(&fonts[4]);
            *(const FontHeader_t **)param = &fonts[4];
#else
            *(const FontHeader_t **)param = 0;
#endif
            break;
        case MSG_FONT_GET_HEIGHT:
            *(uint32_t *)param = GLYPH_HEIGHT;
            break;
    }
}
