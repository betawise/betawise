/* Small FreeType bridge for deterministic, monochrome source-font research. */
#include <ft2build.h>
#include FT_FREETYPE_H
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int fail(const char *message) { fprintf(stderr, "%s\n", message); return 1; }

int main(int argc, char **argv) {
    if (argc != 5) return fail("usage: vector_raster font ppem native|auto x-phase-64ths < unicode-values");
    int ppem = atoi(argv[2]), phase = atoi(argv[4]);
    if (ppem < 1 || ppem > 128 || phase < 0 || phase > 63 ||
        (strcmp(argv[3], "native") && strcmp(argv[3], "auto"))) return fail("invalid raster options");
    FT_Library library;
    FT_Face face;
    if (FT_Init_FreeType(&library)) return fail("FreeType initialization failed");
    if (FT_New_Face(library, argv[1], 0, &face)) return fail("cannot open outline font");
    if (!FT_IS_SCALABLE(face)) return fail("source must contain scalable outlines");
    if (FT_Select_Charmap(face, FT_ENCODING_UNICODE) || FT_Set_Pixel_Sizes(face, 0, ppem))
        return fail("cannot select Unicode/pixel size");
    FT_Vector delta = {phase, 0};
    FT_Set_Transform(face, NULL, &delta);
    FT_Int32 flags = FT_LOAD_NO_BITMAP | FT_LOAD_TARGET_MONO |
        (!strcmp(argv[3], "auto") ? FT_LOAD_FORCE_AUTOHINT : FT_LOAD_NO_AUTOHINT);
    int major, minor, patch;
    FT_Library_Version(library, &major, &minor, &patch);
    printf("{\"version\":\"%d.%d.%d\",\"glyphs\":{", major, minor, patch);
    unsigned long code;
    int first = 1;
    while (scanf("%lu", &code) == 1) {
        if (code > 0x10ffff) return fail("invalid Unicode scalar");
        printf("%s\"%lu\":", first ? "" : ",", code); first = 0;
        FT_UInt index = FT_Get_Char_Index(face, code);
        if (!index) { printf("null"); continue; }
        if (FT_Load_Glyph(face, index, flags) || FT_Render_Glyph(face->glyph, FT_RENDER_MODE_MONO))
            return fail("glyph rasterization failed");
        FT_GlyphSlot glyph = face->glyph;
        FT_Bitmap *bitmap = &glyph->bitmap;
        if (bitmap->width && bitmap->rows && bitmap->pixel_mode != FT_PIXEL_MODE_MONO)
            return fail("expected monochrome bitmap");
        printf("{\"left\":%d,\"top\":%d,\"advance64\":%ld,\"width\":%u,\"height\":%u,\"rows\":[",
               glyph->bitmap_left, glyph->bitmap_top, glyph->advance.x, bitmap->width, bitmap->rows);
        if (bitmap->pitch < 0) return fail("unsupported negative bitmap pitch");
        for (unsigned y = 0; y < bitmap->rows; ++y) {
            int offset = (int)y * bitmap->pitch;
            const unsigned char *row = bitmap->buffer + offset;
            printf("%s\"", y ? "," : "");
            for (unsigned x = 0; x < bitmap->width; ++x) putchar(row[x/8] & (0x80 >> (x%8)) ? '1' : '0');
            putchar('"');
        }
        printf("]}");
    }
    printf("}}\n");
    FT_Done_Face(face); FT_Done_FreeType(library);
    return 0;
}
