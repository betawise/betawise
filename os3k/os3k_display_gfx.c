#include "os3k.h"

static inline RopCode_e SolidRop(bool black)
{
    return (black ? ROP_BLACKNESS : ROP_WHITENESS);
}

void DrawPixel(uint16_t x, uint16_t y, bool black)
{
    RasterOp(x, y, 1, 1, NULL, SolidRop(black));
}

void DrawLine(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1, bool black)
{
    RopCode_e operation = SolidRop(black);
    /* On-screen endpoints bound major to 263 and minor to 64.
     * Counts are at most 264; doubled error arithmetic fits int16_t. */
    int16_t x = x0, y = y0;
    int16_t dx = (x1 >= x0 ? x1 - x0 : x0 - x1);
    int16_t dy = (y1 >= y0 ? y1 - y0 : y0 - y1);
    int16_t sx = (x0 < x1 ? 1 : -1);
    int16_t sy = (y0 < y1 ? 1 : -1);
    bool horizontal = dx >= dy;
    int16_t major = (horizontal ? dx : dy);
    int16_t minor = (horizontal ? dy : dx);
    int16_t remaining = major + 1;
    int16_t run = remaining;
    int16_t whole = 1, remainder = 0;
    int16_t error = 0;
    /* Axes and points use one complete span. Diagonals use unit spans
     * through the same loop, with no division needed. */
    if (minor) {
        if (major != minor) {
            /* Narrow operands produce one native 68000 DIVU.W for both
             * quotient and remainder, without software divide helpers. */
            whole = (uint16_t)major / (uint16_t)minor;
            remainder = (uint16_t)major % (uint16_t)minor;
        }
        run = whole / 2 + ((whole & 1) || remainder);
        error = ((whole & 1) ? minor : 0) + remainder - 1;
        if (error < 0)
            error += 2 * minor;
    }

    /* Run-length-slice Bresenham: interior runs have whole or whole+1
     * pixels. The first/last runs are partial. This initial error includes
     * the ceil-rounding adjustment that keeps halfway pixels biased toward
     * the destination, including when the endpoints are reversed.
     * Advance by spans, without walking the pixels inside each span. */
    for (;;) {
        if (remaining <= run)
            run = remaining;
        if (horizontal) {
            RasterOp((sx > 0 ? x : x-run+1), y, run, 1,
                     NULL, operation);
        } else {
            RasterOp(x, (sy > 0 ? y : y-run+1), 1, run,
                     NULL, operation);
        }
        remaining -= run;
        if (!remaining)
            break;
        if (horizontal) {
            x += (sx > 0 ? run : -run);
            y += sy;
        } else {
            x += sx;
            y += (sy > 0 ? run : -run);
        }
        run = whole;
        error += 2 * remainder;
        if (error >= 2 * minor) {
            ++run;
            error -= 2 * minor;
        }
    }
}
