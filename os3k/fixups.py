#!/usr/bin/env python3
"""Write the big-endian RAM fixup table for an OS3K ELF."""
import argparse
import struct
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from elf_reader import Image, R_68K_32, GOT_OFFSETS

RAM_BASE = 0x80000000
HEADER_FIELDS = {
    4: "__os3k_rom_size",
    8: "__os3k_ram_size",
    0x84: "Os3kEntry",
}


def fixups(image):
    metadata = Image(image)
    values = metadata.values
    got_size = values["__os3k_got_size"]
    image_size = values["__os3k_image_size"]
    rom_size = values["__os3k_rom_size"]
    ram_size = values["__os3k_ram_size"]
    got_base = values.get("_GLOBAL_OFFSET_TABLE_", RAM_BASE)
    if got_size and got_base != RAM_BASE:
        raise ValueError(f"GOT base is {got_base:#x}, expected {RAM_BASE:#x}")

    offsets = set()
    for rel in metadata.relocations:
        kind = rel.kind
        symbol = rel.symbol
        # GNU ld represents resolved zero-valued absolute constants using the
        # reserved null symbol. These are not pointers requiring runtime rebasing.
        if symbol.key[1] == 0:
            continue
        description = f'relocation type {kind} at {rel.offset:#x} to {symbol.name}'
        if kind in GOT_OFFSETS and symbol.section == "SHN_ABS":
            raise ValueError(f"absolute GOT target cannot be rebased: {description}")
        if kind != R_68K_32:
            continue
        address = rel.offset
        if HEADER_FIELDS.get(address) == symbol.name or symbol.section == "SHN_ABS":
            continue
        offset = address - RAM_BASE
        if not got_size <= offset <= image_size - 4 or not offset or offset % 2:
            raise ValueError(f"absolute relocation outside initialized data: {description}")
        target = rel.target
        if not (0 <= target <= rom_size or RAM_BASE <= target <= RAM_BASE + ram_size):
            raise ValueError(f"unsupported pointer target: {description}")
        if offset in offsets:
            raise ValueError(f"duplicate fixup at RAM offset {offset:#x}")
        offsets.add(offset)
    return sorted(offsets)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("table", type=Path)
    args = parser.parse_args()
    try:
        offsets = fixups(args.image)
    except (KeyError, ValueError) as error:
        parser.exit(1, f"{args.image}: {error}\n")
    args.table.write_bytes(b"".join(struct.pack(">I", offset) for offset in [*offsets, 0]))
    print(len(offsets))


if __name__ == "__main__":
    main()
