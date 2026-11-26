/* Isolated -Os cost probe, not part of the applet. */
unsigned MakeVerseMarker(unsigned target, unsigned char* pattern) {
    const unsigned char prefix[6] = {0xB1, 12, 0xB1, 0xB1, 0, 0xB1};
    __builtin_memcpy(pattern, prefix, 6);
    unsigned length = 6;
    if(target >= 100) pattern[length++] = '0' + target / 100;
    if(target >= 10) pattern[length++] = '0' + target / 10 % 10;
    pattern[length++] = '0' + target % 10;
    pattern[length++] = 0xB2;
    unsigned mask = length++;
    pattern[length++] = 0xB2;
    pattern[length++] = 0xB2;
    pattern[length++] = 12;
    pattern[length++] = 0xB2;
    return length;
}
int CompareVerseMarker(const void* a, const void* b, unsigned length) {
    return __builtin_memcmp(a, b, length);
}
