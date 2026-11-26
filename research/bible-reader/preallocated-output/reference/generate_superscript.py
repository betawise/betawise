#!/usr/bin/env python3
"""Generate the sparse, private verse-number face used by the native editor."""

import argparse
import json
from pathlib import Path

DIGIT_SOURCE = Path(__file__).resolve().parents[2] / 'research/fonts/superscript-3x5.json'
DIGIT_COLUMNS = tuple(tuple(columns) for columns in json.loads(DIGIT_SOURCE.read_text())['columns'])
DIGIT_CHARACTER = ord('0')
GLYPH_BYTES = 8
TOPS = (0, 1, 2, 4)


def generate():
    lines = [
        "/* Generated compact ROM banks, top offsets 0, 1, 2, 4. */",
        "static const uint8_t superscript_widths[256] = {",
    ]
    lines.extend(f"    [0x{DIGIT_CHARACTER + digit:02x}] = 4," for digit in range(10))
    lines.extend(["};", "", "static const uint16_t superscript_offsets[256] = {"])
    lines.extend(f"    [0x{DIGIT_CHARACTER + digit:02x}] = {GLYPH_BYTES * (digit + 1)}," for digit in range(10))
    lines.extend(["};", "", "static const uint8_t superscript_bitmaps[4][11 * 8] = {"])
    for top in TOPS:
        lines.append("    {")
        for digit, columns in enumerate(DIGIT_COLUMNS):
            entries=[]
            for x,column in enumerate(columns):
                shifted=column << top
                for page in range(2):
                    byte=(shifted >> (page*8))&255
                    if byte:entries.append(f"[{GLYPH_BYTES*(digit+1)+4*page+x}] = {byte}")
            lines.append("        "+", ".join(entries)+",")
        lines.append("    },")
    lines.extend(["};", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(generate())


if __name__ == "__main__":
    main()
