#include "os3k.h"
#include FONT_GLYPHS

APPLET_HEADER_BEGIN
    APPLET_FLAGS(APPLET_FLAG_FONT | APPLET_FLAG_HIDDEN)
    APPLET_ID(0xA1F0)
#if defined(FONT_Tiny)
    APPLET_FONT_NAME("BetaWise Terminal Tiny")
#elif defined(FONT_Small)
    APPLET_FONT_NAME("BetaWise Terminal Small")
#else
    APPLET_FONT_NAME("BetaWise Terminal")
#endif
    APPLET_INFO("Copyright (c) 2020 Alpaxo Software")
    APPLET_VERSION(BETAWISE_VERSION_MAJOR, BETAWISE_VERSION_MINOR, BETAWISE_VERSION_REVISION)
    APPLET_LANGUAGE_EN_US
APPLET_HEADER_END

static FontHeader_t g_pFontHeader;

void BwProcessMessage(Message_e message, uint32_t param, uint32_t* status) {
    *status = 0;
    switch(message) {
        case MSG_INIT:
            g_pFontHeader.height = GLYPH_HEIGHT;
            g_pFontHeader.max_width = GLYPH_WIDTH;
            g_pFontHeader.max_bytes = GLYPH_BYTES;
#ifdef GLYPH_PROPORTIONAL
            g_pFontHeader.width_table = GLYPH_WIDTHS;
            g_pFontHeader.offset_table = GLYPH_OFFSETS;
            g_pFontHeader.bitmap_data = GLYPH_DATA;
#else
            // Monospaced, so no lookup tables required.
            g_pFontHeader.width_table = 0;
            g_pFontHeader.offset_table = 0;
            g_pFontHeader.bitmap_data = GLYPHS[0];
#endif
            break;

        case MSG_FONT_GET_NAME:
            *(const char**)param = APPLET_FONT_NAME_PTR;
            break;

        case MSG_FONT_GET_NORMAL:
            *(FontHeader_t**)param = &g_pFontHeader;
            break;

        case MSG_FONT_GET_BOLD:
        case MSG_FONT_GET_ITALIC:
        case MSG_FONT_GET_BOLD_ITALIC:
            *(FontHeader_t**)param = 0;
            break;

        case MSG_FONT_GET_HEIGHT:
            *(uint32_t*)param = GLYPH_HEIGHT;
            break;
    }
}
