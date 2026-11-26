#include "Decoder.h"
#include <string.h>

static int FailDecoder(BibleDecoder_t* decoder) {
    decoder->error = 1;
    return 0;
}

int BibleDecoderInit(BibleDecoder_t* decoder, const uint8_t* image, uint32_t size) {
    uint32_t metadata_size;
    uint32_t dictionary_size;
    uint32_t model_size;
    uint32_t rule_count;
    uint32_t frequent_words_offset;

    memset(decoder, 0, sizeof(*decoder));
    decoder->image = image;
    decoder->image_size = size;
    if(size < BIBLE_CONTAINER_HEADER_SIZE || memcmp(image, "KJVHUF02", 8)) {
        return FailDecoder(decoder);
    }

    metadata_size = ReadBigEndian32(image + 8);
    decoder->dictionary_word_count = ReadBigEndian32(image + 12);
    dictionary_size = ReadBigEndian32(image + 16);
    model_size = ReadBigEndian32(image + 20);
    decoder->chapter_count = ReadBigEndian32(image + 24);
    rule_count = ReadBigEndian32(image + 32);
    decoder->max_code_bits = ReadBigEndian32(image + 36);
    frequent_words_offset = ReadBigEndian32(image + 40);

    if(decoder->chapter_count != BIBLE_CHAPTER_COUNT ||
        !decoder->dictionary_word_count || decoder->dictionary_word_count > 63487 ||
        rule_count > BIBLE_MAX_GRAMMAR_RULES || !decoder->max_code_bits ||
        decoder->max_code_bits > 24 || metadata_size > size - 64 ||
        dictionary_size > size - 64 - metadata_size ||
        model_size > size - 64 - metadata_size - dictionary_size) {
        return FailDecoder(decoder);
    }
    if(frequent_words_offset) {
        if(frequent_words_offset > size || size - frequent_words_offset < 1024) {
            return FailDecoder(decoder);
        }
        decoder->frequent_words = image + frequent_words_offset;
    }

    decoder->grammar_rule_count = rule_count;
    decoder->symbol_count = decoder->dictionary_word_count + rule_count;
    decoder->dictionary = image + 64 + metadata_size;
    decoder->huffman_model = decoder->dictionary + dictionary_size;
    if(ReadBigEndian16(decoder->huffman_model) != decoder->max_code_bits ||
        ReadBigEndian16(decoder->huffman_model + 2) != decoder->symbol_count ||
        model_size != 4 + 8u * decoder->max_code_bits +
            2u * decoder->symbol_count + 1024) {
        return FailDecoder(decoder);
    }

    decoder->huffman_symbols = decoder->huffman_model + 4 + 8u * decoder->max_code_bits;
    decoder->huffman_lookup = decoder->huffman_symbols + 2u * decoder->symbol_count;
    decoder->grammar_rules = decoder->huffman_model + model_size;
    decoder->chapter_records = decoder->grammar_rules + 4 * rule_count;
    decoder->chapter_payload = decoder->chapter_records + 16u * decoder->chapter_count;
    if(decoder->chapter_payload > image + size) {
        return FailDecoder(decoder);
    }
    decoder->dictionary_block_count =
        (decoder->dictionary_word_count + BIBLE_DICTIONARY_BLOCK_WORDS - 1) /
        BIBLE_DICTIONARY_BLOCK_WORDS;
    decoder->dictionary_offsets = decoder->dictionary;
    decoder->dictionary_text = decoder->dictionary_offsets +
        4u * decoder->dictionary_block_count;
    return decoder->dictionary_text < decoder->huffman_model;
}

int BibleDecoderOpenChapter(BibleDecoder_t* decoder, uint16_t chapter) {
    const uint8_t* record;
    uint32_t offset;
    uint32_t encoded_size;
    uint32_t payload_size = decoder->image + decoder->image_size - decoder->chapter_payload;

    if(decoder->error || chapter >= decoder->chapter_count) {
        return FailDecoder(decoder);
    }
    record = decoder->chapter_records + 16u * chapter;
    offset = ReadBigEndian32(record);
    encoded_size = ReadBigEndian32(record + 4);
    if(offset > payload_size || encoded_size > payload_size - offset) {
        return FailDecoder(decoder);
    }

    decoder->input_cursor = decoder->chapter_payload + offset;
    decoder->input_end = decoder->input_cursor + encoded_size;
    decoder->remaining_symbols = ReadBigEndian32(record + 8);
    decoder->bit_buffer = decoder->buffered_bits = decoder->padding_bytes = 0;
    decoder->pending_symbol_count = decoder->word_cursor = decoder->word_length = 0;
    return 1;
}

static void RefillBits(BibleDecoder_t* decoder, unsigned required_bits) {
    while(decoder->buffered_bits < required_bits) {
        unsigned next_byte = 0;
        if(decoder->input_cursor < decoder->input_end) {
            next_byte = *decoder->input_cursor++;
        } else if(++decoder->padding_bytes > 4) {
            decoder->error = 1;
        }
        decoder->bit_buffer = (decoder->bit_buffer << 8) | next_byte;
        decoder->buffered_bits += 8;
    }
}

static int ReadHuffmanSymbol(BibleDecoder_t* decoder) {
    uint32_t prefix;
    uint32_t entry;
    uint32_t code;
    unsigned length;

    RefillBits(decoder, BIBLE_HUFFMAN_LOOKUP_BITS);
    prefix = (decoder->bit_buffer >>
        (decoder->buffered_bits - BIBLE_HUFFMAN_LOOKUP_BITS)) & 255;
    entry = ReadBigEndian32(decoder->huffman_lookup + 4 * prefix);
    if(entry) {
        decoder->buffered_bits -= entry & 31;
        return entry >> 5;
    }

    code = prefix;
    decoder->buffered_bits -= BIBLE_HUFFMAN_LOOKUP_BITS;
    for(length = 9; length <= decoder->max_code_bits; ++length) {
        const uint8_t* record = decoder->huffman_model + 4 + 8u * (length - 1);
        uint32_t first_code = ReadBigEndian32(record);
        unsigned code_count = ReadBigEndian16(record + 6);
        RefillBits(decoder, 1);
        code = (code << 1) | ((decoder->bit_buffer >> --decoder->buffered_bits) & 1);
        if(code >= first_code && code - first_code < code_count) {
            unsigned symbol_index = ReadBigEndian16(record + 4) + code - first_code;
            return ReadBigEndian16(decoder->huffman_symbols + 2u * symbol_index);
        }
    }
    FailDecoder(decoder);
    return -2;
}

static int ReadWordSpelling(BibleDecoder_t* decoder, uint16_t terminal) {
    unsigned block = terminal / BIBLE_DICTIONARY_BLOCK_WORDS;
    unsigned entry_index;
    unsigned position = 0;
    unsigned length = 0;
    const uint8_t* text;
    const uint8_t* block_end;
    unsigned block_size;

    if(decoder->frequent_words) {
        unsigned cache_slot = (terminal ^ (terminal >> 8)) & 255;
        const uint8_t* record = decoder->frequent_words + 4 * cache_slot;
        if(ReadBigEndian16(record) == terminal) {
            text = decoder->frequent_words + 1024 + ReadBigEndian16(record + 2);
            while(text < decoder->image + decoder->image_size && *text) {
                if(length >= sizeof(decoder->word_buffer) - 1) {
                    return FailDecoder(decoder);
                }
                decoder->word_buffer[length++] = *text++;
            }
            if(text >= decoder->image + decoder->image_size) {
                return FailDecoder(decoder);
            }
            decoder->word_buffer[length] = 0;
            decoder->word_length = length;
            decoder->word_cursor = 0;
            return 1;
        }
    }

    text = decoder->dictionary_text +
        ReadBigEndian32(decoder->dictionary_offsets + 4u * block);
    block_end = block + 1 < decoder->dictionary_block_count ?
        decoder->dictionary_text + ReadBigEndian32(decoder->dictionary_offsets + 4u * (block + 1)) :
        decoder->huffman_model;
    if(text >= block_end || block_end > decoder->huffman_model || block_end - text > 512) {
        return FailDecoder(decoder);
    }
    block_size = block_end - text;
    for(entry_index = 0; entry_index <= terminal % BIBLE_DICTIONARY_BLOCK_WORDS; ++entry_index) {
        unsigned prefix_length;
        if(position >= block_size) {
            return FailDecoder(decoder);
        }
        prefix_length = text[position++];
        if(prefix_length > length) {
            return FailDecoder(decoder);
        }
        length = prefix_length;
        while(position < block_size && text[position]) {
            if(length >= sizeof(decoder->word_buffer) - 1) {
                return FailDecoder(decoder);
            }
            decoder->word_buffer[length++] = text[position++];
        }
        if(position >= block_size) {
            return FailDecoder(decoder);
        }
        ++position;
        decoder->word_buffer[length] = 0;
    }
    decoder->word_length = length;
    decoder->word_cursor = 0;
    return 1;
}

int BibleDecoderReadNode(BibleDecoder_t* decoder) {
    int symbol;
    if(decoder->error) {
        return -2;
    }
    if(decoder->pending_symbol_count) {
        return decoder->pending_symbols[--decoder->pending_symbol_count];
    }
    if(!decoder->remaining_symbols) {
        return -1;
    }
    symbol = ReadHuffmanSymbol(decoder);
    if(symbol < 0) {
        return -2;
    }
    --decoder->remaining_symbols;
    return symbol;
}

int BibleDecoderExpandRule(BibleDecoder_t* decoder, unsigned symbol) {
    const uint8_t* rule;
    unsigned first_child;
    unsigned second_child;
    if(symbol < decoder->dictionary_word_count || symbol >= decoder->symbol_count ||
        decoder->pending_symbol_count > 30) {
        return FailDecoder(decoder);
    }
    rule = decoder->grammar_rules + 4u * (symbol - decoder->dictionary_word_count);
    first_child = ReadBigEndian16(rule);
    second_child = ReadBigEndian16(rule + 2);
    if(first_child >= symbol || second_child >= symbol) {
        return FailDecoder(decoder);
    }
    decoder->pending_symbols[decoder->pending_symbol_count++] = second_child;
    decoder->pending_symbols[decoder->pending_symbol_count++] = first_child;
    return 1;
}

int BibleDecoderReadTerminal(BibleDecoder_t* decoder) {
    int symbol = BibleDecoderReadNode(decoder);
    if(symbol < 0) {
        return symbol;
    }
    while(symbol >= decoder->dictionary_word_count) {
        const uint8_t* rule;
        unsigned first_child;
        unsigned second_child;
        if(symbol >= decoder->symbol_count || decoder->pending_symbol_count >= 32) {
            FailDecoder(decoder);
            return -2;
        }
        rule = decoder->grammar_rules + 4u * (symbol - decoder->dictionary_word_count);
        first_child = ReadBigEndian16(rule);
        second_child = ReadBigEndian16(rule + 2);
        if(first_child >= (unsigned)symbol || second_child >= (unsigned)symbol) {
            FailDecoder(decoder);
            return -2;
        }
        decoder->pending_symbols[decoder->pending_symbol_count++] = second_child;
        symbol = first_child;
    }
    return symbol;
}

int BibleDecoderReadByte(BibleDecoder_t* decoder) {
    int terminal;
    if(decoder->error) {
        return -2;
    }
    if(decoder->word_cursor < decoder->word_length) {
        return decoder->word_buffer[decoder->word_cursor++];
    }
    terminal = BibleDecoderReadTerminal(decoder);
    if(terminal < 0) {
        return terminal;
    }
    if(!ReadWordSpelling(decoder, terminal) || !decoder->word_length) {
        FailDecoder(decoder);
        return -2;
    }
    return decoder->word_buffer[decoder->word_cursor++];
}

int BibleDecoderGetWord(BibleDecoder_t* decoder, uint16_t terminal,
    char* output, unsigned capacity) {
    if(terminal >= decoder->dictionary_word_count ||
        !ReadWordSpelling(decoder, terminal) || capacity <= decoder->word_length) {
        return 0;
    }
    memcpy(output, decoder->word_buffer, decoder->word_length + 1);
    return decoder->word_length;
}
