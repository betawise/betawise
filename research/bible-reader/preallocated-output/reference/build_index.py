"""Full packed word/chapter postings and grammar summaries (IDXEXP02)."""

import re
import struct
from collections import defaultdict
from convert_source import encode_native

WORD = re.compile(rb"[A-Za-z]+(?:'[A-Za-z]+)*")


def encode_deltas(values):
    output = bytearray()
    previous = -1
    for value in values:
        difference = value - previous
        previous = value
        while difference >= 128:
            output.append((difference & 127) | 128)
            difference >>= 7
        output.append(difference)
    return bytes(output)


def encode_elias_fano(values, universe):
    count = len(values)
    if not count:
        return b"\0\0\0"
    low_bits = max(0, (universe // count).bit_length() - 1)
    output = bytearray((count * low_bits + (values[-1] >> low_bits) + count + 8) // 8)

    def set_bit(bit):
        output[bit // 8] |= 1 << (bit & 7)

    for index, value in enumerate(values):
        for bit in range(low_bits):
            if value >> bit & 1:
                set_bit(index * low_bits + bit)
        set_bit(count * low_bits + (value >> low_bits) + index)
    return struct.pack(">HB", count, low_bits) + output


def pack_word_ids(values):
    output = bytearray()
    pending = 0
    pending_bits = 0
    for value in values:
        if not 0 <= value < 16384:
            raise ValueError("Normalization word ID exceeds 14 bits")
        pending = (pending << 14) | value
        pending_bits += 14
        while pending_bits >= 8:
            pending_bits -= 8
            output.append((pending >> pending_bits) & 255)
    if pending_bits:
        output.append((pending << (8 - pending_bits)) & 255)
    return bytes(output)


def build_index(blocks, words):
    postings = defaultdict(set)
    for chapter, raw in enumerate(blocks):
        for word in WORD.findall(raw.replace(b"\x92", b"'").lower()):
            postings[word].add(chapter)
    vocabulary = sorted(postings)
    normalized_ids = {word: index for index, word in enumerate(vocabulary)}
    if len(vocabulary) + 2 >= 16384 or len(words) >= 65536:
        raise ValueError("Vocabulary exceeds the packed index limits")
    canonical_terminals = {}
    normalization = []
    for terminal, spelling in enumerate(words):
        raw = encode_native(spelling)
        normalized = raw.lstrip(b" ").replace(b"\x92", b"'").lower()
        if raw == b"\n":
            normalization.append(len(vocabulary))
        elif normalized in normalized_ids:
            normalization.append(normalized_ids[normalized])
            canonical_terminals.setdefault(normalized, terminal)
        else:
            normalization.append(len(vocabulary) + 1)

    if any(terminal >= 16384 for terminal in canonical_terminals.values()):
        raise ValueError("Canonical terminal exceeds the packed record's 14 bits")

    universe = len(blocks)
    all_chapters = set(range(universe))
    body = bytearray()
    records = []
    for word in vocabulary:
        chapters = sorted(postings[word])
        complement = sorted(all_chapters - postings[word])
        bitmap = sum(1 << chapter for chapter in chapters).to_bytes((universe + 7) // 8, "little")
        choices = [
            (0, encode_deltas(chapters)),
            (1, encode_elias_fano(chapters, universe)),
            (2, bitmap),
            (3, encode_deltas(complement)),
            (4, encode_elias_fano(complement, universe)),
        ]
        encoding, data = min(choices, key=lambda choice: len(choice[1]))
        records.append((canonical_terminals[word] << 18) | len(body))
        body.extend(bytes([encoding]) + data)
    if len(body) >= 1 << 18:
        raise ValueError("Posting offsets exceed 18 bits")
    records.append(len(body))
    header = struct.pack(">8sHHII", b"IDXEXP02", len(vocabulary), len(words), 1, len(body))
    return header + struct.pack(">" + "I" * len(records), *records) + pack_word_ids(normalization) + body, len(vocabulary)


def grammar_summaries(words, image):
    metadata_size, terminals, dictionary_size, model_size, _, _, rule_count, _ = struct.unpack_from(">8I", image, 8)
    if terminals != len(words):
        raise ValueError("Grammar dictionary size mismatch")
    summaries = []
    for word in words:
        if word == "\n":
            summaries.append((0, 1, 0))
        elif WORD.fullmatch(encode_native(word.lstrip(" ").replace("’", "'"))):
            summaries.append((1, 0, 1))
        else:
            summaries.append((0, 0, 0))
    offset = 64 + metadata_size + dictionary_size + model_size
    for index in range(rule_count):
        first, second = struct.unpack_from(">HH", image, offset + 4 * index)
        if first >= terminals + index or second >= terminals + index:
            raise ValueError("Grammar rule has a forward reference")
        first_words, first_lines, first_trailing = summaries[first]
        second_words, second_lines, second_trailing = summaries[second]
        summary = (first_words + second_words, first_lines + second_lines,
            second_trailing if second_lines else first_trailing + second_words)
        if max(summary) >= 256:
            raise ValueError("Grammar summary exceeds one byte per field")
        summaries.append(summary)
    return bytes(value for summary in summaries[terminals:] for value in summary)
