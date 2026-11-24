/* Research-only portable C formatting decoder/merger. Not linked into BibleWise. */
#include "FormatBench.h"
#include <string.h>
#ifdef HOST_BENCH
#include <stdio.h>
#include <stdlib.h>
#endif

#define FONT_SCRATCH_BYTES 256
#define ATOM_BYTES 64
#define HEADING_BYTES 256
#define PROFILE_WORDS 32

static uint32_t g_error;
static void Fail(unsigned line) {
    g_error = line;
#ifdef HOST_BENCH
    fprintf(stderr,"FormatBench failure at line %u\n",line);
    exit(1);
#endif
}
#define CHECK(condition) do { if(!(condition)) Fail(__LINE__); } while(0)

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
    Cursor records;
    unsigned count, next, level, id, huffman, shift;
    const uint8_t* offsets;
    const uint8_t* text;
    unsigned width, strings;
    Huffman model;
    char buffer[HEADING_BYTES];
} Headings;
typedef struct {
    BibleDecoder_t decoder;
    const uint8_t* normalization;
    unsigned vocabulary_size;
    char token[64];
    unsigned position, length, normalized, pending_word;
} Text;

static unsigned Varint(Cursor* c) {
    unsigned result = 0, shift = 0, byte;
    do {
        CHECK(c->p < c->end && shift < 32);
        byte = *c->p++;
        result |= (byte & 127u) << shift;
        shift += 7;
    } while(byte & 128);
    return result;
}

static unsigned Index(const uint8_t* p, unsigned width) {
    unsigned result = 0;
    while(width--) result = (result << 8) | *p++;
    return result;
}

static Sidecar OpenSidecar(BenchBlob blob) {
    Sidecar s;
    unsigned present = 0, i, n;
    CHECK(blob.size >= 13 && !memcmp(blob.data, "BWF2", 4));
    s.chapters = ReadBigEndian16(blob.data + 4);
    s.width = blob.data[6];
    s.header_size = ReadBigEndian16(blob.data + 8);
    s.heading_size = ReadBigEndian16(blob.data + 10);
    s.header = blob.data + 12;
    s.heading_header = s.header + s.header_size;
    CHECK(s.heading_header[s.heading_size] == 1 || s.heading_header[s.heading_size] == 2 || s.heading_header[s.heading_size] == 4);
    s.bitmap = s.heading_header + s.heading_size + 1;
    for(i = 0; i < (s.chapters + 7) / 8; ++i) {
        n = s.bitmap[i];
        while(n) { present += n & 1; n >>= 1; }
    }
    s.index = s.bitmap + (s.chapters + 7) / 8;
    s.payload = s.index + (present + 1) * s.width;
    CHECK(s.payload <= blob.data + blob.size);
    return s;
}

static Cursor Chapter(const Sidecar* s, unsigned chapter) {
    Cursor c;
    unsigned rank = 0, i, n;
    c.p = c.end = s->payload;
    CHECK(chapter < s->chapters);
    if(!(s->bitmap[chapter / 8] & (1u << (chapter & 7)))) return c;
    for(i = 0; i < chapter / 8; ++i) {
        n = s->bitmap[i];
        while(n) { rank += n & 1; n >>= 1; }
    }
    n = s->bitmap[chapter / 8] & ((1u << (chapter & 7)) - 1);
    while(n) { rank += n & 1; n >>= 1; }
    c.p = s->payload + Index(s->index + rank * s->width, s->width);
    c.end = s->payload + Index(s->index + (rank + 1) * s->width, s->width);
    return c;
}

static Huffman OpenHuffman(const uint8_t* p) {
    Huffman h;
    h.maximum = *p++;
    CHECK(h.maximum && h.maximum <= 24);
    h.counts = p;
    h.symbols = p + 2 * h.maximum;
    return h;
}

static HuffStream OpenStream(Cursor bytes, Huffman model) {
    HuffStream s;
    s.model = model;
    s.remaining = Varint(&bytes);
    s.bytes = bytes;
    s.bits = s.byte = 0;
    return s;
}

static unsigned HuffByte(HuffStream* s) {
    unsigned code = 0, first = 0, index = 0, length, count;
    CHECK(s->remaining);
    --s->remaining;
    for(length = 0; length < s->model.maximum; ++length) {
        if(!s->bits) {
            CHECK(s->bytes.p < s->bytes.end);
            s->byte = *s->bytes.p++;
            s->bits = 8;
        }
        code = (code << 1) | ((s->byte >> --s->bits) & 1);
        count = ReadBigEndian16(s->model.counts + 2 * length);
        if(code >= first && code - first < count) return s->model.symbols[index + code - first];
        index += count;
        first = (first + count) << 1;
    }
    CHECK(0);
    return 0;
}

static unsigned HuffVarint(HuffStream* s) {
    unsigned result = 0, shift = 0, byte;
    do {
        byte = HuffByte(s);
        result |= (byte & 127u) << shift;
        shift += 7;
        CHECK(shift <= 35);
    } while(byte & 128);
    return result;
}

static const uint8_t* OpenProfile(Profile* p, const uint8_t* raw, unsigned size, unsigned book) {
    Cursor c = {raw, raw + size};
    unsigned groups, bitmaps, word = 0, i, bit, mask;
    int extended = size >= 4 && !memcmp(raw, "WDP2", 4);
    if(extended) {
        c.p += 5;
        groups = ReadBigEndian16(c.p); c.p += 2;
        p->words = Varint(&c);
    } else {
        CHECK(*c.p++ == 1);
        groups = 66;
        p->words = *c.p++;
    }
    CHECK(groups == 66 && p->words <= PROFILE_WORDS && book < groups);
    bitmaps = (groups + 7) / 8;
    for(i = 0; i < p->words; ++i) {
        word += Varint(&c);
        p->word[i] = word;
        p->mask[i] = 0;
        mask = extended ? *c.p++ : 4;
        for(bit = 0; bit < 3; ++bit) {
            if(mask & (1u << bit)) {
                CHECK(c.p + bitmaps <= c.end);
                if(c.p[book / 8] & (1u << (book & 7))) p->mask[i] |= 1u << bit;
                c.p += bitmaps;
            }
        }
    }
    return c.p;
}

static unsigned DefaultStyle(const Profile* p, unsigned word) {
    unsigned low = 0, high = p->words;
    while(low < high) {
        unsigned middle = (low + high) / 2;
        if(p->word[middle] < word) low = middle + 1;
        else high = middle;
    }
    return low < p->words && p->word[low] == word ? p->mask[low] : 0;
}

static void NextRun(Run* r) {
    unsigned tag, length;
    if(!r->count) { r->start = r->end = UINT32_MAX; return; }
    --r->count;
    tag = Varint(&r->bytes);
    length = tag & 1 ? Varint(&r->bytes) + 2 : 1;
    r->start = r->previous_end + (tag >> 1);
    r->end = r->previous_end = r->start + length;
}

static void OpenRuns(Run* runs, Cursor bytes) {
    unsigned mask, bit, count, tag;
    memset(runs, 0, 3 * sizeof(*runs));
    if(bytes.p == bytes.end) mask = 0;
    else mask = *bytes.p++;
    for(bit = 0; bit < 3; ++bit) {
        if(mask & (1u << bit)) {
            count = runs[bit].count = Varint(&bytes);
            runs[bit].bytes = bytes;
            while(count--) {
                tag = Varint(&bytes);
                if(tag & 1) Varint(&bytes);
            }
        }
        NextRun(runs + bit);
    }
}

static unsigned StyleAt(Run* runs, unsigned atom) {
    unsigned bit, mask = 0;
    for(bit = 0; bit < 3; ++bit) {
        while(atom >= runs[bit].end && runs[bit].end != UINT32_MAX) NextRun(runs + bit);
        if(atom >= runs[bit].start && atom < runs[bit].end) mask |= 1u << bit;
    }
    return mask;
}

static void NextLayout(Layout* l) {
    unsigned tag;
    if(!l->count) { l->next = UINT32_MAX; return; }
    --l->count;
    tag = HuffVarint(&l->bytes);
    l->next += tag >> l->width;
    l->value = l->alphabet[tag & ((1u << l->width) - 1)];
}

static Layout OpenLayout(Sidecar* side, unsigned chapter) {
    Cursor header = {side->header, side->header + side->header_size};
    Layout l;
    unsigned scope = *header.p++, size = Varint(&header), alphabet;
    CHECK(scope == 0 && size == 1);
    l.default_first = *header.p;
    header.p += size;
    l.width = *header.p++;
    alphabet = *header.p++;
    ++header.p; /* Unused Rice parameter. */
    l.alphabet = header.p;
    header.p += alphabet;
    l.bytes = OpenStream(Chapter(side, chapter), OpenHuffman(header.p));
    l.count = HuffVarint(&l.bytes);
    l.next = 0;
    NextLayout(&l);
    return l;
}

static Headings OpenHeadings(BenchBlob blob, unsigned chapter, unsigned huffman, unsigned shift) {
    Sidecar side = OpenSidecar(blob);
    Headings h;
    Cursor header = {side.heading_header, side.heading_header + side.heading_size};
    unsigned blocks, model_size;
    memset(&h, 0, sizeof(h));
    h.records = Chapter(&side, chapter);
    h.count = h.records.p == h.records.end ? 0 : Varint(&h.records);
    h.next = h.count ? Varint(&h.records) : UINT32_MAX;
    h.huffman = huffman;
    h.shift = shift;
    h.strings = Varint(&header);
    blocks = (h.strings + (1u << shift) - 1) >> shift;
    if(huffman) {
        model_size = Varint(&header);
        h.model = OpenHuffman(header.p);
        header.p += model_size;
        h.width = *header.p++;
        h.offsets = header.p;
        h.text = header.p + (blocks + 1) * h.width;
    } else {
        h.width = 4;
        h.offsets = header.p;
        h.text = header.p + blocks * 4;
    }
    return h;
}

static unsigned HeadingText(Headings* h, unsigned id) {
    unsigned block = id >> h->shift, entry, length = 0, prefix, byte;
    Cursor c;
    HuffStream stream;
    CHECK(id < h->strings);
    c.p = h->text + Index(h->offsets + block * h->width, h->width);
    c.end = h->huffman ? h->text + Index(h->offsets + (block + 1) * h->width, h->width) : c.p;
    if(h->huffman) stream = OpenStream(c, h->model);
    for(entry = 0; entry <= (id & ((1u << h->shift) - 1)); ++entry) {
        prefix = h->huffman ? HuffByte(&stream) : *c.p++;
        CHECK(prefix <= length);
        length = prefix;
        while((byte = h->huffman ? HuffByte(&stream) : *c.p++)) {
            CHECK(length + 1 < sizeof(h->buffer));
            h->buffer[length++] = byte;
        }
        h->buffer[length] = 0;
    }
    return length;
}

static void Emit(BenchResult* r, unsigned byte) {
    r->hash = ((r->hash << 5) | (r->hash >> 27)) ^ byte;
    ++r->bytes;
}

static void TextBytes(BenchResult* r, const uint8_t* bytes, unsigned size) {
    while(size--) Emit(r, *bytes++);
}

static void EmitHeading(BenchResult* r, unsigned level, const uint8_t* text, unsigned size) {
    Emit(r, 'H'); Emit(r, 2); /* Semantic bold face, in the same text flow. */
    Emit(r, level); Emit(r, size >> 8); Emit(r, size & 255);
    TextBytes(r, text, size);
    ++r->headings;
}

static void AtHeadings(BenchResult* r, Headings* h, unsigned atom) {
    while(h->count && h->next == atom) {
        unsigned level = *h->records.p++, id = Varint(&h->records);
        unsigned size = HeadingText(h, id);
        EmitHeading(r, level, (const uint8_t*)h->buffer, size);
        if(--h->count) h->next += Varint(&h->records);
        else h->next = UINT32_MAX;
    }
}

static int TextByte(Text* t, unsigned* word_start) {
    *word_start = UINT32_MAX;
    if(t->position == t->length) {
        int terminal = BibleDecoderReadTerminal(&t->decoder);
        unsigned bit, packed;
        if(terminal < 0) return terminal;
        t->length = BibleDecoderGetWord(&t->decoder, terminal, t->token, sizeof(t->token));
        CHECK(t->length);
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

int BenchFormatChapter(const BenchAssets* a, const BenchCase* bc,
    unsigned mode, unsigned show_headings, BenchResult* r) {
    Text t;
    Profile profile;
    Sidecar font_side, layout_side;
    Layout layout;
    Run runs[3];
    Headings headings;
    uint8_t font_data[FONT_SCRATCH_BYTES], atom_text[ATOM_BYTES];
    Cursor raw_heads = {bc->raw_headings.data, bc->raw_headings.data + bc->raw_headings.size};
    unsigned raw_count = 0, raw_next = UINT32_MAX;
    unsigned atom = 0, length = 0, words = 0, word = 0;
    unsigned residual = 0, atom_residual = 0, inline_layout = 0, have_layout = 0, atom_layout = 0;
    unsigned first = 1, source_first = 1, byte, word_start, actual_style, actual_layout, i;
    int character;
    memset(r, 0, sizeof(*r));
    r->hash = 0x12345678;
    g_error = 0;
    memset(&t, 0, sizeof(t));
    CHECK(BibleDecoderInit(&t.decoder, a->bible.data, a->bible.size));
    CHECK(BibleDecoderOpenChapter(&t.decoder, bc->chapter));
    if(mode == 0) {
        while((character = BibleDecoderReadByte(&t.decoder)) >= 0) Emit(r, character);
        CHECK(character == -1);
        r->error = g_error;
        return !g_error;
    }
    t.normalization = a->normalization.data;
    t.vocabulary_size = a->vocabulary_size;
    if(mode == 1) {
        if(show_headings && raw_heads.p < raw_heads.end) {
            raw_count = Varint(&raw_heads);
            if(raw_count) raw_next = Varint(&raw_heads);
        }
    } else {
        if(mode == 2) {
            const uint8_t* model;
            HuffStream stream;
            Cursor decoded;
            font_side = OpenSidecar(a->font);
            model = OpenProfile(&profile, font_side.header, font_side.header_size, bc->book) + 1;
            decoded = Chapter(&font_side, bc->chapter);
            if(decoded.p != decoded.end) {
                stream = OpenStream(decoded, OpenHuffman(model));
                i = 0;
                while(stream.remaining) {
                    CHECK(i < sizeof(font_data));
                    font_data[i++] = HuffByte(&stream);
                }
                decoded.p = font_data; decoded.end = font_data + i;
            }
            OpenRuns(runs, decoded);
            layout_side = OpenSidecar(a->layout);
            layout = OpenLayout(&layout_side, bc->chapter);
        } else {
            OpenProfile(&profile, a->prediction.data, a->prediction.size, bc->book);
        }
        if(show_headings && !a->headings_inline) headings = OpenHeadings(a->headings, bc->chapter, a->heading_huffman, a->heading_shift);
    }
    for(;;) {
        character = TextByte(&t, &word_start);
        if(a->headings_inline && character == 3) {
            uint8_t title[256];
            unsigned size = 0;
            int level = TextByte(&t, &word_start);
            CHECK(!length && level >= 16 && level < 32);
            while((character = TextByte(&t, &word_start)) >= 0 && character != 4) {
                CHECK(size < sizeof(title));
                title[size++] = character;
            }
            CHECK(character == 4);
            if(show_headings) EmitHeading(r, level & 15, title, size);
            continue;
        }
        if(mode == 3 && character >= 0) {
            if(character == 2) {
                unsigned high = TextByte(&t, &word_start), low = TextByte(&t, &word_start);
                CHECK(high >= 16 && high < 32 && low >= 16 && low < 32);
                inline_layout = ((high & 15) << 4) | (low & 15);
                have_layout = 1;
                continue;
            }
            if(character >= 16 && character < 32) { residual = character & 15; continue; }
        }
        if(character < 0 || character == ' ' || character == '\n') {
            if(length) {
                if(show_headings) {
                    if(mode == 1) {
                        while(raw_count && raw_next == atom) {
                            unsigned level = *raw_heads.p++, size = Varint(&raw_heads);
                            EmitHeading(r, level, raw_heads.p, size); raw_heads.p += size;
                            if(--raw_count) raw_next += Varint(&raw_heads);
                            else raw_next = UINT32_MAX;
                        }
                    } else if(!a->headings_inline) AtHeadings(r, &headings, atom);
                }
                if(mode == 1) {
                    actual_style = bc->expected_styles.data[atom];
                    actual_layout = bc->expected_layout.data[atom];
                } else {
                    actual_style = (mode == 2 ? StyleAt(runs, atom) : atom_residual) ^ (words == 1 ? DefaultStyle(&profile, word) : 0);
                    if(mode == 2) {
                        actual_layout = source_first ? layout.default_first : 0;
                        if(layout.next == atom) { actual_layout = layout.value; NextLayout(&layout); }
                    } else actual_layout = atom_layout;
                }
                Emit(r, 'A'); Emit(r, actual_style); Emit(r, actual_layout);
                Emit(r, length >> 8); Emit(r, length & 255); TextBytes(r, atom_text, length);
                ++atom; ++r->atoms; length = words = 0;
                first = 0;
            }
            if(character < 0) break;
            Emit(r, 'W'); Emit(r, character);
            if(character == '\n') first = 1;
            continue;
        }
        byte = character;
        if(!length) {
            atom_residual = residual;
            source_first = first;
            if(mode == 3) {
                unsigned default_layout = first ? a->layout_defaults.data[a->layout_defaults.size == 1 ? 0 : bc->book] : 0;
                atom_layout = have_layout ? inline_layout : default_layout;
                have_layout = 0;
            }
        }
        CHECK(length + 1 < sizeof(atom_text));
        atom_text[length++] = byte;
        if(word_start != UINT32_MAX) { ++words; word = word_start; }
    }
    CHECK(character == -1 && atom == bc->atoms);
    if(show_headings && mode != 1 && !a->headings_inline) AtHeadings(r, &headings, atom);
    r->error = g_error;
    return !g_error;
}
