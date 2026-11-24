/* Research prototype, normal Neo LCD orientation, physical coordinates.
 * Opaque clockwise rotation with inverted polarity for a black sidebar.
 * Does not translate firmware scroll coordinates. No bitmap scratch.
 */
static void DrawBitmapRotatedDirect(unsigned x, unsigned y, unsigned width,
    unsigned height, const uint8_t* bitmap) {
    if(!width || !height || x + height > 264 || y + width > 65) {
        return;
    }
    for(unsigned page = y / 8; page <= (y + width - 1) / 8; ++page) {
        for(unsigned dx = 0; dx < height; ++dx) {
            unsigned col = x + dx;
            unsigned local = col >= 132 ? col - 132 : col;
            volatile uint8_t* command = col >= 132 ? &LCD_CMD_REG_RIGHT : &LCD_CMD_REG_LEFT;
            volatile uint8_t* data = command + 1;
            unsigned row = height - 1 - dx;
            uint8_t bits = 0;
            uint8_t mask = 0;
            for(unsigned bit = 0; bit < 8; ++bit) {
                unsigned line = page * 8 + bit;
                if(line >= y && line < y + width) {
                    unsigned source_column = line - y;
                    mask |= 1u << bit;
                    if(!(bitmap[(row / 8) * width + source_column] & (1u << (row & 7)))) {
                        bits |= 1u << bit;
                    }
                }
            }
            *command = LCD_CMD_PAGE_ADDR(page);
            *command = LCD_CMD_COL_ADDR_HI(local);
            *command = LCD_CMD_COL_ADDR_LO(local);
            *command = LCD_CMD_COL_ADDR_INC;
            (void)*data; /* Required dummy read, matching the ROM's LCD driver. */
            uint8_t previous = *data;
            *data = (previous & ~mask) | bits;
            *command = LCD_CMD_COL_ADDR_END;
        }
    }
}
