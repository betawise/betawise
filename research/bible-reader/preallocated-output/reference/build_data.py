#!/usr/bin/env python3
"""Build the one production codec/index pair from the pinned bible-data submodule."""

import argparse
import hashlib
import json
import struct
from pathlib import Path

from build_index import build_index, grammar_summaries
from compress_text import build_container
from convert_source import packed_json, read_corpus, encode_native
from format_data import read_formatting, inline_headings, build_sidecars, searchable_chapters

HERE = Path(__file__).resolve().parent
TRANSLATIONS = ("kjv", "nkjv", "esv", "niv", "nasb", "csb")


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_navigation(output, metadata, verse_counts):
    name_width = max(len(name.encode("ascii")) + 1 for name, _, _ in metadata)
    declarations = [
        "/* Generated from the same source as the compressed chapter records. */",
        f"#define BIBLE_MAX_CHAPTER_VERSES {max(verse_counts)}",
        "",
        "typedef struct {",
        "    uint16_t first;",
        "    uint16_t chapters;",
        f"    char name[{name_width}];",
        "} BibleBook_t;",
        "",
        "static const BibleBook_t g_books[BIBLE_BOOK_COUNT] = {",
    ]
    for name, first, count in metadata:
        declarations.append(f"    {{{first}, {count}, {json.dumps(name)}}},")
    declarations.extend(["};", ""])
    (output / "Navigation.h").write_text("\n".join(declarations))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=TRANSLATIONS, default="kjv")
    parser.add_argument("--repo", type=Path, default=HERE / "upstream")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    corpus, source = read_corpus(args.repo, args.version)
    blocks = [encode_native("\n".join(chapter) + "\n") for book in corpus for chapter in book["chapters"]]
    metadata = []
    first_chapter = 0
    for book in corpus:
        metadata.append([book["name"], first_chapter, len(book["chapters"])])
        first_chapter += len(book["chapters"])
    if len(corpus) != 66 or len(blocks) != 1189:
        raise ValueError("Reader navigation requires the canonical 66-book, 1189-chapter layout")

    formatting = read_formatting(args.version, args.repo)
    assert formatting["blocks"] == blocks
    formatted_blocks = inline_headings(formatting)
    image, dictionary = build_container(formatted_blocks, metadata)
    styles, layouts = build_sidecars(formatting)
    index, vocabulary_size = build_index(formatted_blocks, dictionary)
    summaries = grammar_summaries(dictionary, image)
    verse_counts = [len(chapter) for book in corpus for chapter in book["chapters"]]
    resources = {
        "container.bin": image,
        "styles.bin": styles,
        "layouts.bin": layouts,
        "search.bin": index,
        "pruning.bin": summaries,
        "verses.bin": struct.pack(">" + "H" * len(verse_counts), *verse_counts),
        "source.json": packed_json(corpus),
        "search-source.json": packed_json(searchable_chapters(formatted_blocks)),
    }
    for name, contents in resources.items():
        (args.output / name).write_bytes(contents)
    write_navigation(args.output, metadata, verse_counts)
    builder_files = [HERE / name for name in
        ("build_data.py", "convert_source.py", "compress_text.py", "build_index.py", "format_data.py")]
    report = {
        "version": args.version.upper(),
        "codec": "Native-byte phrase Huffman, raw front dictionary, eight-bit lookup",
        "search_index_kind": "packed-prune",
        "source_sha256": file_hash(source),
        "books_sha256": file_hash(args.repo / "data/books.json"),
        "canonical_verses_sha256": file_hash(args.repo / "data/kjv/kjv.json"),
        "builder_sha256": hashlib.sha256(b"".join(path.read_bytes() for path in builder_files)).hexdigest(),
        "text_sha256": file_hash(args.output / "source.json"),
        "sha256": hashlib.sha256(image).hexdigest(),
        "resource_sha256": {name: hashlib.sha256(contents).hexdigest() for name, contents in resources.items()},
        "bytes": len(image),
        "search_bytes": len(index),
        "style_bytes": len(styles),
        "layout_bytes": len(layouts),
        "headings": sum(map(len, formatting["headings"])),
        "pruning_bytes": len(summaries),
        "search_words": vocabulary_size,
        "dictionary_entries": len(dictionary),
        "max_dictionary_word": max(map(len, dictionary)),
        "max_chapter_bytes": max(map(len, blocks)),
        "chapters": len(blocks),
        "verses": sum(verse_counts),
        "mapped_text_bytes": sum(map(len, blocks)),
    }
    (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
