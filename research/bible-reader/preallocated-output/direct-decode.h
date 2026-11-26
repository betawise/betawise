/* Bound is the high 16 bits of the fourth chapter word in research HUF03. */
static unsigned ChapterCapacity(void) {
    const uint8_t* records = BibleData + 64 + ReadBigEndian32(BibleData + 8) +
        ReadBigEndian32(BibleData + 16) + ReadBigEndian32(BibleData + 20) +
        4 * ReadBigEndian32(BibleData + 32);
    return ReadBigEndian16(records + 16u * g_current_chapter + 12);
}
