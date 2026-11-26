"""Read bible-data translations and normalize device text before compression."""

import codecs
import json
import re
from collections import defaultdict

TEXT_REPLACEMENTS = {
    "–": "-", "—": "-", "―": "-", "…": "...",
    "\u2006": " ", "\u2009": " ", "á": "a", "í": "i",
    "½": "1/2", "¾": "3/4", "⅓": "1/3", "¼": "1/4", "⅔": "2/3",
    "æ": "ae", "Æ": "AE", "é": "e", "Ē": "E", "´": "'",
}
FRACTIONS = "½¾⅓¼⅔"
STYLE_MARKER = re.compile(r"\*[a-z]+")
# These four Neo-US glyph positions agree with Windows-1252. This is a
# deliberately limited mapping, not a claim about every native byte.
NATIVE_QUOTES = {"‘": 0x91, "’": 0x92, "“": 0x93, "”": 0x94}
NATIVE_ENCODING = {code: code for code in range(128)} | {
    ord(character): code for character, code in NATIVE_QUOTES.items()
}
NATIVE_DECODING = {code: character for character, code in NATIVE_ENCODING.items()}


def encode_native(text):
    """Encode normalized text and internal chapter markers as native bytes."""
    return codecs.charmap_encode(text, "strict", NATIVE_ENCODING)[0]


def decode_native(data):
    return codecs.charmap_decode(data, "strict", NATIVE_DECODING)[0]


def packed_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def convert_text(text):
    """Retain native curly quotes; explicitly map other supported typography."""
    result = []
    for index, character in enumerate(text):
        if character in FRACTIONS and index and text[index - 1].isdigit():
            result.append(" ")
        result.append(TEXT_REPLACEMENTS.get(character, character))
    converted = "".join(result)
    if not all(32 <= ord(character) <= 126 or character in NATIVE_QUOTES
               for character in converted):
        raise ValueError("Bible text contains an unsupported character")
    return converted


def verse_reference(row):
    _, book, chapter, verse = row["r"].split(":")
    return book, int(chapter), int(verse)


def read_corpus(repository, translation):
    """Retain canonical verse slots, including omissions in other translations.

    The source's per-word/paragraph style markers are omitted. Notes, headings,
    cross-references and original-language annotations are not reader resources.
    """
    books = json.loads((repository / "data/books.json").read_bytes())
    canonical_counts = {}
    reference_source = repository / "data/kjv/kjv.json"
    for row in json.loads(reference_source.read_bytes()):
        if "h" in row:
            continue
        book, chapter, verse = verse_reference(row)
        key = (book, chapter)
        canonical_counts[key] = max(canonical_counts.get(key, 0), verse)

    source = repository / "data" / translation / f"{translation}.json"
    verse_parts = defaultdict(list)
    for row in json.loads(source.read_bytes()):
        if "h" in row:
            continue
        book, chapter, verse = verse_reference(row)
        key = (book, chapter)
        if key not in canonical_counts or not 0 < verse < 256:
            raise ValueError(f"Unsupported verse reference: {row['r']}")
        canonical_counts[key] = max(canonical_counts[key], verse)
        plain_text = STYLE_MARKER.sub("", row["t"])
        if "*" in plain_text:
            raise ValueError(f"Unknown source formatting marker: {row['r']}")
        verse_parts[book, chapter, verse].append(convert_text(plain_text))

    corpus = []
    for book in books:
        chapters = []
        for chapter in range(1, book["numChapters"] + 1):
            verses = [
                " ".join(verse_parts[book["book"], chapter, verse])
                for verse in range(1, canonical_counts[book["book"], chapter] + 1)
            ]
            chapters.append(verses)
        corpus.append({"name": book["book"], "chapters": chapters})
    return corpus, source
