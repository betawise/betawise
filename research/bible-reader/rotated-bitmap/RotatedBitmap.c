/* Research size probe only: not linked into BibleWise.
 * Clockwise rotation, opaque inverted output, matching the sidebar's polarity.
 * Input uses DrawBitmap's vertical-byte packing. Coordinates must fit the LCD.
 */
#include "os3k.h"

/* No bitmap scratch: every source ink pixel requires a firmware call. */
void DrawBitmapRotatedPixels(uint16_t x, uint16_t y, uint16_t width,
    uint16_t height, const uint8_t* bitmap) {
    RasterOp(x, y, height, width, NULL, ROP_BLACKNESS);
    for(unsigned column = 0; column < width; ++column) {
        for(unsigned row = 0; row < height; ++row) {
            if(bitmap[(row / 8) * width + column] & (1u << (row & 7))) {
                RasterOp(x + height - 1 - row, y + column, 1, 1, NULL, ROP_WHITENESS);
            }
        }
    }
}

/* One output column at a time: at most nine scratch bytes for width <= 65.
 * Still needs a packed bitmap, but does not assemble the complete destination.
 */
void DrawBitmapRotatedColumns(uint16_t x, uint16_t y, uint16_t width,
    uint16_t height, const uint8_t* bitmap) {
    if(width > 65) {
        return;
    }
    for(unsigned row = 0; row < height; ++row) {
        uint8_t column_pixels[9];
        memset(column_pixels, 0xff, sizeof(column_pixels));
        for(unsigned column = 0; column < width; ++column) {
            if(bitmap[(row / 8) * width + column] & (1u << (row & 7))) {
                column_pixels[column / 8] &= ~(1u << (column & 7));
            }
        }
        DrawBitmap(x + height - 1 - row, y, 1, width, column_pixels);
    }
}

/* Extracted equivalent of the production inner rotation loop; excludes label
 * formatting, centering, background setup and the final DrawBitmap syscall.
 */
void RotateGlyphIntoSidebar(uint8_t* pixels, unsigned y, unsigned width,
    unsigned height, const uint8_t* glyph) {
    for(unsigned column = 0; column < width; ++column) {
        for(unsigned row = 0; row < height; ++row) {
            if(glyph[(row / 8) * width + column] & (1u << (row & 7))) {
                pixels[((y + column) / 8) * 11 + 9 - row] &= ~(1u << ((y + column) & 7));
            }
        }
    }
}
