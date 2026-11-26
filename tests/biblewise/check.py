#!/usr/bin/env python3
"""Host acceptance for the production Bible codec and Full-index search."""

import argparse
import hashlib
import json
import random
import re
import struct
import subprocess
from pathlib import Path

from oracle import oracle, unordered
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "applets/BibleWise"))
from convert_source import encode_native

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
APP = ROOT / "applets/BibleWise"
QUERIES = [
    "beth how", "utterly how", "excellencies", "hypocrite", "beth", "creation", "history", "God", "god*", "believ*", "Methus*", "t d", "t* d*", "faith works", "works faith",
    "kingdom God", "in the beginning", "Jesus Jesus", "God God", "god* god", "be* bel*",
    "LORD's", "LORD’s", "man's", "man’s", "Jesus Christ", "the the", "a a", "holy spirit", "fear not", "zzzzunknown",
    "show* show", "maher shalal hash baz", "life God",
]
DIRECTION_QUERIES = {"God", "faith works", "kingdom God", "Jesus Jesus", "god* god", "be* bel*"}


def compile_driver(output, name, sources):
    executable = output / name
    subprocess.run(["cc", "-O2", "-Wall", "-Wextra", "-I" + str(APP),
        *map(str, sources), "-o", str(executable)], check=True)
    return executable


def read_matches(command):
    return [tuple(map(int, line.split())) for line in subprocess.check_output(command, text=True).splitlines()]


def check_decoder(data, output, chapters):
    executable = compile_driver(output, "decoder-check", [HERE / "decoder_check.c", APP / "Decoder.c"])
    decoded = subprocess.check_output([str(executable), str(data / "container.bin")])
    expected = bytearray(struct.pack(">I", len(chapters)))
    for chapter in reversed(range(len(chapters))):
        raw = encode_native("\n".join(chapters[chapter]) + "\n")
        expected.extend(struct.pack(">II", chapter, len(raw)) + raw)
    # Container text includes heading regions; canonical verse bytes exclude them.
    position = 4
    canonical = bytearray(decoded[:4])
    for chapter in reversed(range(len(chapters))):
        ci, size = struct.unpack_from('>II', decoded, position)
        position += 8
        raw = decoded[position:position+size]
        position += size
        plain = bytearray()
        offset = 0
        while offset < len(raw):
            if raw[offset] == 2:
                offset += 3
            elif raw[offset] == 3:
                offset = raw.index(4, offset + 2) + 1
            else:
                plain.append(raw[offset]); offset += 1
        canonical.extend(struct.pack('>II', ci, len(plain)) + plain)
    if canonical != expected or position != len(decoded):
        raise AssertionError("Reverse chapter decoding differs from the source")
    (output / "decoded.bin").write_bytes(decoded)
    return hashlib.sha256(decoded).hexdigest()


def check_search(data, output, chapters):
    chapters = json.loads((data / 'search-source.json').read_text())
    summaries = (data / "pruning.bin").read_bytes()
    resource = output / "summaries.c"
    resource.write_text("#include <stdint.h>\nconst uint8_t BibleGrammarSummary[] = {" +
        ",".join(map(str, summaries)) + "};\n")
    executable = compile_driver(output, "search-check",
        [HERE / "search_check.c", APP / "Search.c", APP / "Decoder.c", resource])
    cases = 0
    for query in QUERIES:
        for mode in range(3):
            expected = oracle(chapters, query, mode)
            command = [str(executable), str(data / "container.bin"), str(data / "search.bin"), query.encode("cp1252"), str(mode)]
            actual = read_matches(command)
            assert actual == expected, (query, mode, len(actual), len(expected))
            cases += 1
            if query not in DIRECTION_QUERIES:
                continue
            for origin in [(0, 1, 0), (596, 80, 0), (999, 16, 0), (1188, 22, 30)]:
                for direction in [-1, 1]:
                    for inclusive in [0, 1]:
                        if direction > 0:
                            matches = [hit for hit in expected if (hit >= origin if inclusive else hit > origin)][:1]
                        else:
                            matches = [hit for hit in expected if (hit <= origin if inclusive else hit < origin)][-1:]
                        actual = read_matches(command + list(map(str, (*origin, direction, inclusive))))
                        assert actual == matches, (query, mode, origin, direction, inclusive, actual, matches)
                        cases += 1
    # Derive positions from this translation, not KJV-specific word ordinals.
    holy_words = re.findall("[A-Za-z]+(?:'[A-Za-z]+)*", chapters[684][2].lower())
    first_holy = next(i for i in range(len(holy_words)-2) if holy_words[i:i+3] == ['holy']*3)
    for mode in (1, 2):
        for origin_word, direction, expected_word in [(first_holy, 1, first_holy+1), (first_holy+2, -1, first_holy)]:
            actual = read_matches([str(executable), str(data / "container.bin"),
                str(data / "search.bin"), "holy holy", str(mode), "684", "3",
                str(origin_word), str(direction), "0", "1", "20", "1"])
            assert actual == [(684, 3, expected_word, 0)], ("overlap", mode, direction, actual)
            cases += 1
    unique = oracle(chapters, 'raca', 2)
    assert len(unique) == 1, unique
    for direction in (-1, 1):
        actual = read_matches([str(executable), str(data / "container.bin"),
            str(data / "search.bin"), "raca", "2", *map(str,unique[0]),
            str(direction), "0", "1", "20", "1"])
        assert actual == [], ("must not wrap to current selection", direction, actual)
        cases += 1
    for query in ["*God", "go*d", "God**", "*", "faith * works"]:
        command = [str(executable), str(data / "container.bin"), str(data / "search.bin"), query, "0"]
        assert subprocess.run(command, stdout=subprocess.DEVNULL).returncode == 2, query
    # A heading occupies real proximity positions between verses 8 and 9.
    for distance in (2, 3, 20):
        query = 'utterly how'
        expected = [hit for hit in oracle(chapters, query, 2, distance) if hit >= (596,8,0)][:1]
        command = [str(executable), str(data/'container.bin'), str(data/'search.bin'), query,
            '2','596','8','0','1','1','0',str(distance)]
        actual = read_matches(command)
        assert actual == [(*hit,0)for hit in expected], ('heading proximity',distance,actual,expected)
        if distance == 2: assert not actual or actual[0][:2] != (596,8)
        cases += 1
    return cases


def check_matcher(output):
    executable = compile_driver(output, "matcher-check", [HERE / "matcher_check.c", APP / "Decoder.c"])
    random_source = random.Random(0xA1B1)
    cases = 0
    for terms in range(1, 9):
        for mode in [0, 2]:
            for _ in range(20):
                events = [(position, 1 + position // 17, position % 17, random_source.randrange(1 << terms))
                    for position in range(100)]
                expected = unordered(events, terms, mode)
                request = f"{terms} {mode}\n" + "".join(f"{mask} {verse} {word}\n" for _, verse, word, mask in events)
                actual = [tuple(map(int, line.split())) for line in
                    subprocess.check_output([str(executable)], input=request, text=True).splitlines()]
                assert actual == expected, (terms, mode, actual, expected)
                cases += 1
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=["KJV", "NKJV", "ESV", "NIV", "NASB", "CSB"], default="KJV")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    subprocess.run(["make", "-C", str(APP), f"VERSION={args.version}"], check=True)
    data = APP / "build/data" / args.version.lower()
    chapters = [chapter for book in json.loads((data / "source.json").read_text()) for chapter in book["chapters"]]
    result = {
        "status": "passed",
        "version": args.version,
        "decoded_sha256": check_decoder(data, args.output, chapters),
        "source_search_cases": check_search(data, args.output, chapters),
        "matcher_property_cases": check_matcher(args.output),
        "invalid_queries": 5,
    }
    (args.output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
