#include "Formatting.h"
#include <string.h>

#define FONT_SCRATCH_BYTES 512
#define ATOM_BYTES 64
#define PROFILE_WORDS 32

/* Metadata is generated with strict size/round-trip checks by format_data.py.
 * Only the selected WDP2/run-Huffman and translation-layout codecs are linked. */
typedef struct { const uint8_t* p; const uint8_t* end; } Cursor;
typedef struct {
    const uint8_t* counts;
    const uint8_t* symbols;
    unsigned maximum;
} Huffman;
typedef struct {
    Cursor bytes;
    Huffman model;
    unsigned byte, bits, remaining;
} HuffStream;
typedef struct {
    const uint8_t* header;
    const uint8_t* heading_header;
    const uint8_t* bitmap;
    const uint8_t* index;
    const uint8_t* payload;
    unsigned chapters, width, header_size, heading_size;
} Sidecar;
typedef struct {
    unsigned words;
    uint16_t word[PROFILE_WORDS];
    uint8_t mask[PROFILE_WORDS];
} Profile;
typedef struct { Cursor bytes; unsigned count, previous_end, start, end; } Run;
typedef struct {
    HuffStream bytes;
    const uint8_t* alphabet;
    unsigned width, count, next, value, default_first;
} Layout;
typedef struct {
    BibleDecoder_t decoder;
    const uint8_t* normalization;
    unsigned vocabulary_size;
    char token[64];
    unsigned position, length, normalized, pending_word;
} Text;

static unsigned ReadFormatVarint(Cursor* c) {
    unsigned result = 0, shift = 0, byte;
    do {
        byte = *c->p++;
        result |= (byte & 127u) << shift;
        shift += 7;
    } while(byte & 128);
    return result;
}

static unsigned ReadFormatOffset(const uint8_t* p, unsigned width) {
    unsigned result = 0;
    while(width--) result = (result << 8) | *p++;
    return result;
}

static Sidecar OpenFormatSidecar(const uint8_t* data) {
    Sidecar s;
    unsigned present = 0, i, n;
    s.chapters = ReadBigEndian16(data + 4);
    s.width = data[6];
    s.header_size = ReadBigEndian16(data + 8);
    s.heading_size = ReadBigEndian16(data + 10);
    s.header = data + 12;
    s.heading_header = s.header + s.header_size;
    s.bitmap = s.heading_header + s.heading_size + 1;
    for(i = 0; i < (s.chapters + 7) / 8; ++i) {
        n = s.bitmap[i];
        while(n) { present += n & 1; n >>= 1; }
    }
    s.index = s.bitmap + (s.chapters + 7) / 8;
    s.payload = s.index + (present + 1) * s.width;
    return s;
}

static Cursor ReadChapterMetadata(const Sidecar* s, unsigned chapter) {
    Cursor c;
    unsigned rank = 0, i, n;
    c.p = c.end = s->payload;
    if(!(s->bitmap[chapter / 8] & (1u << (chapter & 7)))) return c;
    for(i = 0; i < chapter / 8; ++i) {
        n = s->bitmap[i];
        while(n) { rank += n & 1; n >>= 1; }
    }
    n = s->bitmap[chapter / 8] & ((1u << (chapter & 7)) - 1);
    while(n) { rank += n & 1; n >>= 1; }
    c.p = s->payload + ReadFormatOffset(s->index + rank * s->width, s->width);
    c.end = s->payload + ReadFormatOffset(s->index + (rank + 1) * s->width, s->width);
    return c;
}

static Huffman ReadHuffmanModel(const uint8_t* p) {
    Huffman h;
    h.maximum = *p++;
    h.counts = p;
    h.symbols = p + 2 * h.maximum;
    return h;
}

static HuffStream OpenHuffmanStream(Cursor bytes, Huffman model) {
    HuffStream s;
    s.model = model;
    s.remaining = ReadFormatVarint(&bytes);
    s.bytes = bytes;
    s.bits = s.byte = 0;
    return s;
}

static unsigned ReadHuffmanByte(HuffStream* s) {
    unsigned code = 0, first = 0, index = 0, length, count;
    --s->remaining;
    for(length = 0; length < s->model.maximum; ++length) {
        if(!s->bits) {
            s->byte = *s->bytes.p++;
            s->bits = 8;
        }
        code = (code << 1) | ((s->byte >> --s->bits) & 1);
        count = ReadBigEndian16(s->model.counts + 2 * length);
        if(code >= first && code - first < count) return s->model.symbols[index + code - first];
        index += count;
        first = (first + count) << 1;
    }
    return 0;
}

static unsigned ReadHuffmanVarint(HuffStream* s) {
    unsigned result = 0, shift = 0, byte;
    do {
        byte = ReadHuffmanByte(s);
        result |= (byte & 127u) << shift;
        shift += 7;
    } while(byte & 128);
    return result;
}

static const uint8_t* ReadWordDefaults(Profile* p, const uint8_t* raw, unsigned size, unsigned book) {
    Cursor c = {raw, raw + size};
    unsigned groups, bitmaps, word = 0, i, bit, mask;
    c.p += 5; /* WDP2, per-book profiles. */
    groups = ReadBigEndian16(c.p);
    c.p += 2;
    p->words = ReadFormatVarint(&c);
    bitmaps = (groups + 7) / 8;
    for(i = 0; i < p->words; ++i) {
        word += ReadFormatVarint(&c);
        p->word[i] = word;
        p->mask[i] = 0;
        mask = *c.p++;
        for(bit = 0; bit < 3; ++bit) {
            if(mask & (1u << bit)) {
                if(c.p[book / 8] & (1u << (book & 7))) p->mask[i] |= 1u << bit;
                c.p += bitmaps;
            }
        }
    }
    return c.p;
}

static unsigned FindWordDefault(const Profile* p, unsigned word) {
    unsigned low = 0, high = p->words;
    while(low < high) {
        unsigned middle = (low + high) / 2;
        if(p->word[middle] < word) low = middle + 1;
        else high = middle;
    }
    return low < p->words && p->word[low] == word ? p->mask[low] : 0;
}

static void AdvanceStyleRun(Run* r) {
    unsigned tag, length;
    if(!r->count) { r->start = r->end = UINT32_MAX; return; }
    --r->count;
    tag = ReadFormatVarint(&r->bytes);
    length = tag & 1 ? ReadFormatVarint(&r->bytes) + 2 : 1;
    r->start = r->previous_end + (tag >> 1);
    r->end = r->previous_end = r->start + length;
}

static void ReadStyleRuns(Run* runs, Cursor bytes) {
    unsigned mask, bit, count, tag;
    memset(runs, 0, 3 * sizeof(*runs));
    if(bytes.p == bytes.end) mask = 0;
    else mask = *bytes.p++;
    for(bit = 0; bit < 3; ++bit) {
        if(mask & (1u << bit)) {
            count = runs[bit].count = ReadFormatVarint(&bytes);
            runs[bit].bytes = bytes;
            while(count--) {
                tag = ReadFormatVarint(&bytes);
                if(tag & 1) ReadFormatVarint(&bytes);
            }
        }
        AdvanceStyleRun(runs + bit);
    }
}

static unsigned ReadAtomStyle(Run* runs, unsigned atom) {
    unsigned bit, mask = 0;
    for(bit = 0; bit < 3; ++bit) {
        while(atom >= runs[bit].end && runs[bit].end != UINT32_MAX) AdvanceStyleRun(runs + bit);
        if(atom >= runs[bit].start && atom < runs[bit].end) mask |= 1u << bit;
    }
    return mask;
}

static void AdvanceLayoutEvent(Layout* l) {
    unsigned tag;
    if(!l->count) { l->next = UINT32_MAX; return; }
    --l->count;
    tag = ReadHuffmanVarint(&l->bytes);
    l->next += tag >> l->width;
    l->value = l->alphabet[tag & ((1u << l->width) - 1)];
}

static Layout ReadChapterLayout(Sidecar* side, unsigned chapter) {
    Cursor header = {side->header, side->header + side->header_size};
    Layout l;
    unsigned size, alphabet;
    ++header.p; /* Translation-wide layout default. */
    size = ReadFormatVarint(&header);
    l.default_first = *header.p;
    header.p += size;
    l.width = *header.p++;
    alphabet = *header.p++;
    ++header.p; /* Unused Rice parameter. */
    l.alphabet = header.p;
    header.p += alphabet;
    Cursor bytes = ReadChapterMetadata(side, chapter);
    if(bytes.p == bytes.end) {
        l.count = 0;
        l.next = UINT32_MAX;
        return l;
    }
    l.bytes = OpenHuffmanStream(bytes, ReadHuffmanModel(header.p));
    l.count = ReadHuffmanVarint(&l.bytes);
    l.next = 0;
    AdvanceLayoutEvent(&l);
    return l;
}


static int ReadFormattedTextByte(Text* t, unsigned* word_start) {
    *word_start = UINT32_MAX;
    if(t->position == t->length) {
        int terminal = BibleDecoderReadTerminal(&t->decoder);
        unsigned bit, packed;
        if(terminal < 0) return terminal;
        t->length = BibleDecoderGetWord(&t->decoder, terminal, t->token, sizeof(t->token));
        if(!t->length || t->length > sizeof(t->token)) return -2;
        t->position = 0;
        bit = 14u * terminal;
        packed = ((uint32_t)t->normalization[bit / 8] << 16) | ((unsigned)t->normalization[bit / 8 + 1] << 8) | t->normalization[bit / 8 + 2];
        t->normalized = (packed >> (10 - (bit & 7))) & 16383;
        t->pending_word = t->normalized < t->vocabulary_size;
    }
    {
        unsigned byte = (uint8_t)t->token[t->position++];
        if(t->pending_word && IsBibleLetter(byte)) {
            *word_start = t->normalized;
            t->pending_word = 0;
        }
        return byte;
    }
}


int BibleFormatChapter(const BibleFormatAssets* assets, unsigned chapter, unsigned book,
    BibleFormatOutput output, void* context) {
    Text text;
    Profile profile;
    Sidecar style_side = OpenFormatSidecar(assets->styles);
    Sidecar layout_side = OpenFormatSidecar(assets->layouts);
    Layout layout = ReadChapterLayout(&layout_side, chapter);
    Run runs[3];
    uint8_t style_bytes[FONT_SCRATCH_BYTES], atom_text[ATOM_BYTES], heading[256];
    const uint8_t* model = ReadWordDefaults(&profile, style_side.header, style_side.header_size, book) + 1;
    Cursor decoded = ReadChapterMetadata(&style_side, chapter);
    unsigned atom = 0, length = 0, words = 0, word = 0, first = 1;
    unsigned source_first = 1, word_start, size = 0;
    int character;
    BibleFormatEvent event;
    memset(&text, 0, sizeof(text));
    if(!BibleDecoderInit(&text.decoder, assets->bible, assets->bible_size) ||
        !BibleDecoderOpenChapter(&text.decoder, chapter)) return 0;
    text.normalization = assets->normalization;
    text.vocabulary_size = assets->vocabulary_size;
    if(decoded.p != decoded.end) {
        HuffStream stream = OpenHuffmanStream(decoded, ReadHuffmanModel(model));
        while(stream.remaining) {
            if(size == sizeof(style_bytes)) return 0;
            style_bytes[size++] = ReadHuffmanByte(&stream);
        }
        decoded.p = style_bytes;
        decoded.end = style_bytes + size;
    }
    ReadStyleRuns(runs, decoded);
    for(;;) {
        character = ReadFormattedTextByte(&text, &word_start);
        if(character == 3) {
            int level = ReadFormattedTextByte(&text, &word_start);
            if(length || level < 16 || level >= 32) return 0;
            size = 0;
            while((character = ReadFormattedTextByte(&text, &word_start)) >= 0 && character != 4) {
                if(size == sizeof(heading)) return 0;
                heading[size++] = character;
            }
            if(character != 4) return 0;
            event.kind = BIBLE_FORMAT_HEADING;
            event.style = BIBLE_STYLE_BOLD;
            event.layout = level & 15;
            event.text = heading;
            event.length = size;
            if(!output(context, &event)) return 0;
            continue;
        }
        if(character < 0 || character == ' ' || character == '\n') {
            if(length) {
                event.kind = BIBLE_FORMAT_ATOM;
                event.style = ReadAtomStyle(runs, atom) ^ (words == 1 ? FindWordDefault(&profile, word) : 0);
                event.layout = source_first ? layout.default_first : 0;
                if(layout.next == atom) {
                    event.layout = layout.value;
                    AdvanceLayoutEvent(&layout);
                }
                event.text = atom_text;
                event.length = length;
                if(!output(context, &event)) return 0;
                ++atom;
                length = words = 0;
                first = 0;
            }
            if(character < 0) break;
            event.kind = BIBLE_FORMAT_SPACE;
            event.style = event.layout = 0;
            event.text = atom_text;
            atom_text[0] = character;
            event.length = 1;
            if(!output(context, &event)) return 0;
            if(character == '\n') first = 1;
            continue;
        }
        if((!IsBibleQuote(character) && (character < 32 || character > 126)) ||
            length == sizeof(atom_text)) return 0;
        if(!length) source_first = first;
        atom_text[length++] = character;
        if(word_start != UINT32_MAX) { ++words; word = word_start; }
    }
    return character == -1 && !text.decoder.error;
}
