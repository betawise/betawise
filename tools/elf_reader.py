"""Read resolved m68k ELF metadata without binutils text output.

Relocations retain their linked symbol-table identity, including local symbols
with identical names. ld remains responsible for applying relocations.
"""
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

try:
    from elftools.elf.elffile import ELFFile
    from elftools.elf.sections import SymbolTableSection
    from elftools.elf.relocation import RelocationSection
except ImportError as error:
    raise ImportError('OS3K builds require pyelftools: install python3-pyelftools '
                      'or run python3 -m pip install pyelftools in your build environment') from error


# Numeric ELF ABI types; parsing does not require relocation execution support.
R_68K_32, R_68K_16, R_68K_PC16 = 1, 2, 5
R_68K_GOT32O, R_68K_GOT16O, R_68K_GOT8O = 10, 11, 12
GOT_OFFSETS = {R_68K_GOT32O, R_68K_GOT16O, R_68K_GOT8O}


@dataclass(frozen=True)
class Symbol:
    key: tuple
    name: str
    value: int
    section: object
    kind: str


@dataclass(frozen=True)
class Relocation:
    offset: int
    kind: int
    symbol: Symbol
    addend: int

    @property
    def target(self):
        return self.symbol.value + self.addend


class Image:
    def __init__(self, path):
        if isinstance(path, Image):
            self.__dict__.update(path.__dict__)
            return
        elf = ELFFile(BytesIO(Path(path).read_bytes()))
        if elf.elfclass != 32 or elf.little_endian or elf['e_machine'] != 'EM_68K':
            raise ValueError(f'{path}: expected big-endian ELF32 m68k')
        self.sections = {i: section.name for i, section in enumerate(elf.iter_sections())}
        self.symbols = []
        tables = {}
        for i, section in enumerate(elf.iter_sections()):
            if isinstance(section, SymbolTableSection):
                table = [Symbol((i, j), sym.name, sym['st_value'],
                                sym['st_shndx'], sym['st_info']['type'])
                         for j, sym in enumerate(section.iter_symbols())]
                tables[i] = table
                # Prefer the full symbol table over a duplicate dynamic table.
                if section['sh_type'] == 'SHT_SYMTAB':
                    self.symbols.extend(table)
        self.values = {sym.name: sym.value for sym in self.symbols
                       if sym.name and sym.section != 'SHN_UNDEF'}
        self.relocations = []
        for section in elf.iter_sections():
            if not isinstance(section, RelocationSection):
                continue
            if not section.is_RELA():
                raise ValueError(f'{path}: unsupported implicit-addend relocation section {section.name}')
            table = tables[section['sh_link']]
            for rel in section.iter_relocations():
                self.relocations.append(Relocation(rel['r_offset'], rel['r_info_type'],
                                                    table[rel['r_info_sym']], rel['r_addend']))
