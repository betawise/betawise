"""The reader's sole codec: Native-byte front dictionary, phrase grammar, Huffman.

The byte layout remains KJVHUF02 for all translations. The magic identifies the
format, not the translation. Chapters are independently seekable Huffman streams.
"""

import heapq
import re
import struct
from collections import Counter

from convert_source import packed_json, encode_native, decode_native

TOKEN = re.compile(r" ?[A-Za-z]+(?:['’][A-Za-z]+)*|.", re.S)
GRAMMAR_ROUNDS = 16
RULES_PER_ROUND = 128
MINIMUM_PAIR_COUNT = 16
DICTIONARY_BLOCK_WORDS = 16
HUFFMAN_LOOKUP_BITS = 8


def front_dictionary(words):
    offsets = bytearray()
    text = bytearray()
    previous = b""
    for index, spelling in enumerate(words):
        word = encode_native(spelling)
        if b"\0" in word:
            raise ValueError("Dictionary word contains NUL")
        if index % DICTIONARY_BLOCK_WORDS == 0:
            offsets.extend(struct.pack(">I", len(text)))
            previous = b""
        prefix = 0
        while prefix < min(len(word), len(previous)) and word[prefix] == previous[prefix]:
            prefix += 1
        if prefix >= 256:
            raise ValueError("Dictionary prefix is too long")
        text.append(prefix)
        text.extend(word[prefix:] + b"\0")
        previous = word
    return bytes(offsets + text)


def train_phrase_grammar(sequences, word_count):
    """Replace frequent adjacent pairs; stable tie ordering keeps builds repeatable."""
    rules = []
    for _ in range(GRAMMAR_ROUNDS):
        pair_counts = Counter(pair for sequence in sequences for pair in zip(sequence, sequence[1:]))
        selected_pairs = [
            pair for pair, count in pair_counts.most_common(RULES_PER_ROUND)
            if count >= MINIMUM_PAIR_COUNT
        ]
        replacements = {
            pair: word_count + len(rules) + index
            for index, pair in enumerate(selected_pairs)
        }
        rules.extend(selected_pairs)
        updated_sequences = []
        for sequence in sequences:
            updated = []
            position = 0
            while position < len(sequence):
                symbol = replacements.get(tuple(sequence[position:position + 2]))
                if symbol is None:
                    updated.append(sequence[position])
                    position += 1
                else:
                    updated.append(symbol)
                    position += 2
            updated_sequences.append(updated)
        sequences = updated_sequences
    return sequences, rules


def huffman_lengths(frequencies):
    heap = [
        (count, index, [symbol])
        for index, (symbol, count) in enumerate(sorted(frequencies.items()))
    ]
    heapq.heapify(heap)
    lengths = Counter()
    serial = len(heap)
    while len(heap) > 1:
        first_count, _, first_symbols = heapq.heappop(heap)
        second_count, _, second_symbols = heapq.heappop(heap)
        for symbol in first_symbols + second_symbols:
            lengths[symbol] += 1
        heapq.heappush(heap, (first_count + second_count, serial, first_symbols + second_symbols))
        serial += 1
    return dict(lengths)


def canonical_codes(lengths):
    codes = {}
    code = 0
    previous_length = 0
    for symbol, length in sorted(enumerate(lengths), key=lambda entry: (entry[1], entry[0])):
        code <<= length - previous_length
        codes[symbol] = (code, length)
        code += 1
        previous_length = length
    return codes


def pack_symbols(sequence, codes):
    output = bytearray()
    pending = 0
    pending_bits = 0
    for symbol in sequence:
        code, length = codes[symbol]
        pending = (pending << length) | code
        pending_bits += length
        while pending_bits >= 8:
            pending_bits -= 8
            output.append((pending >> pending_bits) & 255)
        pending &= (1 << pending_bits) - 1
    if pending_bits:
        output.append(pending << (8 - pending_bits))
    return bytes(output)


def unpack_symbols(encoded, codes, count):
    lookup = {(length, code): symbol for symbol, (code, length) in codes.items()}
    result = []
    code = 0
    length = 0
    maximum_length = max(length for _, length in codes.values())
    for byte in encoded:
        for bit in range(7, -1, -1):
            code = (code << 1) | ((byte >> bit) & 1)
            length += 1
            if (length, code) in lookup:
                result.append(lookup[length, code])
                code = length = 0
                if len(result) == count:
                    return result
            elif length >= maximum_length:
                raise ValueError("Invalid Huffman code")
    raise ValueError("Truncated Huffman stream")


def build_huffman_model(sequences, symbol_count):
    counts = Counter(symbol for sequence in sequences for symbol in sequence)
    lengths = huffman_lengths({symbol: max(1, counts[symbol]) for symbol in range(symbol_count)})
    codes = canonical_codes([lengths[symbol] for symbol in range(symbol_count)])
    maximum = max(lengths.values())
    ordered = sorted(codes, key=lambda symbol: (codes[symbol][1], symbol))
    model = bytearray(struct.pack(">HH", maximum, symbol_count))
    for length in range(1, maximum + 1):
        group = [symbol for symbol in ordered if codes[symbol][1] == length]
        first_index = ordered.index(group[0]) if group else 0
        model.extend(struct.pack(">IHH", codes[group[0]][0] if group else 0, first_index, len(group)))
    model.extend(struct.pack(">" + "H" * len(ordered), *ordered))
    lookup = [0] * (1 << HUFFMAN_LOOKUP_BITS)
    for symbol, (code, length) in codes.items():
        if length <= HUFFMAN_LOOKUP_BITS:
            for prefix in range(code << (8 - length), (code + 1) << (8 - length)):
                lookup[prefix] = (symbol << 5) | length
    model.extend(struct.pack(">256I", *lookup))
    return bytes(model), codes, maximum


def frequent_word_cache(words, frequencies):
    """ROM-only direct-mapped spellings avoid repeatedly reconstructing common words."""
    slots = {}
    strings = bytearray()
    records = bytearray()
    for terminal in sorted(range(len(words)), key=lambda index: -frequencies[index]):
        slot = (terminal ^ (terminal >> 8)) & 255
        slots.setdefault(slot, terminal)
    for slot in range(256):
        terminal = slots.get(slot, 65535)
        offset = len(strings)
        if terminal != 65535:
            strings.extend(encode_native(words[terminal]) + b"\0")
        records.extend(struct.pack(">HH", terminal, offset))
    return bytes(records + strings)


def order_dictionary(words):
    """Keep canonical vocabulary spellings inside the index's 14-bit ID range.

    Larger translations can have more than 16,384 spelling/spacing variants even
    though their normalized vocabulary fits. Swap only overflowing canonical
    spellings with nearby noncanonical slots. The container format and decoder
    are unchanged; KJV/NKJV keep their original byte-identical dictionary order.
    """
    canonical = {}
    word_pattern = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)*")
    for terminal, spelling in enumerate(words):
        normalized = spelling.lstrip(" ").replace("’", "'").lower()
        if word_pattern.fullmatch(normalized):
            canonical.setdefault(normalized, terminal)
    canonical_slots = set(canonical.values())
    overflow = sorted(slot for slot in canonical_slots if slot >= 16384)
    available = [slot for slot in reversed(range(min(16384, len(words))))
        if slot not in canonical_slots]
    if len(overflow) > len(available):
        raise ValueError("Canonical spellings exceed the Full index's 14-bit range")
    for high, low in zip(overflow, available):
        words[low], words[high] = words[high], words[low]
    return words


def build_container(blocks, metadata):
    words = sorted({token for block in blocks for token in TOKEN.findall(decode_native(block))})
    if len(words) + 2048 >= 65536 or max(map(len, words)) >= 64:
        raise ValueError("Dictionary exceeds device limits")
    words = order_dictionary(words)
    word_ids = {word: index for index, word in enumerate(words)}
    original_sequences = [[word_ids[token] for token in TOKEN.findall(decode_native(block))] for block in blocks]
    sequences, rules = train_phrase_grammar(original_sequences, len(words))
    dictionary = front_dictionary(words)
    model, codes, maximum = build_huffman_model(sequences, len(words) + len(rules))
    chapter_index = bytearray()
    payload = bytearray()
    for raw, sequence in zip(blocks, sequences):
        encoded = pack_symbols(sequence, codes)
        chapter_index.extend(struct.pack(">IIII", len(payload), len(encoded), len(sequence), len(raw)))
        payload.extend(encoded)
        decoded = unpack_symbols(encoded, codes, len(sequence))
        if decoded != sequence:
            raise ValueError("Huffman round-trip failed")
        expanded = []
        for symbol in decoded:
            pending = [symbol]
            while pending:
                terminal = pending.pop()
                if terminal < len(words):
                    expanded.append(words[terminal])
                else:
                    first, second = rules[terminal - len(words)]
                    pending.extend([second, first])
        if encode_native("".join(expanded)) != raw:
            raise ValueError("Phrase round-trip failed")

    metadata_bytes = packed_json(metadata)
    grammar = b"".join(struct.pack(">HH", *rule) for rule in rules)
    header = bytearray(struct.pack(">8s8I", b"KJVHUF02", len(metadata_bytes), len(words),
        len(dictionary), len(model), len(blocks), sum(map(len, blocks)), len(rules), maximum).ljust(64, b"\0"))
    body = metadata_bytes + dictionary + model + grammar + chapter_index + payload
    struct.pack_into(">I", header, 40, 64 + len(body))
    frequencies = Counter(token for raw in blocks for token in TOKEN.findall(decode_native(raw)))
    cache = frequent_word_cache(words, [frequencies[word] for word in words])
    return bytes(header) + body + cache, words
