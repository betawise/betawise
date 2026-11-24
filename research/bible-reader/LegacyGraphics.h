/* Compatibility only for the frozen streaming experiment. Not production SDK. */
#include "os3k.h"

static inline void DrawRectangle(uint16_t x, uint16_t y, uint16_t width, uint16_t height,
                                 bool center_black, bool border_black) {
    if(!width || !height) return;
    RasterOp(x, y, width, height, 0, center_black ? ROP_BLACKNESS : ROP_WHITENESS);
    if(center_black == border_black) return;
    DrawLine(x, y, x + width - 1, y, border_black);
    if(height > 1) DrawLine(x, y + height - 1, x + width - 1, y + height - 1, border_black);
    if(height > 2) {
        DrawLine(x, y + 1, x, y + height - 2, border_black);
        if(width > 1) DrawLine(x + width - 1, y + 1, x + width - 1, y + height - 2, border_black);
    }
}
