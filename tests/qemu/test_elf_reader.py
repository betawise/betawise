"""Structured ELF identity and addend regressions using real GNU objects."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from elf_reader import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "os3k"))
from fixups import fixups


class ReaderTests(unittest.TestCase):
    def test_duplicate_locals_and_signed_addends(self):
        prefix = os.environ.get('CROSS_COMPILE', 'm68k-linux-gnu-')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for i, section in enumerate(('.text', '.data')):
                source = root / f'{i}.s'
                source.write_text(f'{section}\n.local duplicate\nduplicate: .long 0\n'
                                  '.section .refs,"a"\n.long 0\n.reloc .-4,R_68K_32,duplicate-4\n')
                subprocess.run([prefix+'as', '-m68000', str(source), '-o', str(root/f'{i}.o')], check=True)
            output = root/'combined.o'
            subprocess.run([prefix+'ld', '-r', str(root/'0.o'), str(root/'1.o'), '-o', str(output)], check=True)
            image = Image(output)
            refs = [rel for rel in image.relocations if rel.symbol.name == 'duplicate']
            self.assertEqual(len(refs), 2)
            self.assertEqual(len({rel.symbol.key for rel in refs}), 2)
            self.assertEqual({image.sections[rel.symbol.section] for rel in refs}, {'.text', '.data'})
            self.assertTrue(all(rel.kind == 1 and rel.addend == -4 and rel.target == -4 for rel in refs))
            self.assertEqual(Image(image).relocations, image.relocations)

    def test_linker_null_symbol_constants_are_not_runtime_pointers(self):
        prefix = os.environ.get('CROSS_COMPILE', 'm68k-linux-gnu-')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root/'zero.s'
            source.write_text('.text\n.long 0\n.reloc .-4,R_68K_32,0\n')
            subprocess.run([prefix+'as', str(source), '-o', str(root/'zero.o')], check=True)
            output = root/'zero.elf'
            definitions = [f'--defsym={name}={value}' for name, value in {
                '__os3k_got_size': 0, '__os3k_image_size': 0,
                '__os3k_rom_size': 4, '__os3k_ram_size': 0}.items()]
            subprocess.run([prefix+'ld', '-e', '0', '-Ttext=0', '--emit-relocs',
                            *definitions, str(root/'zero.o'), '-o', str(output)], check=True)
            image = Image(output)
            self.assertTrue(any(rel.symbol.key[1] == 0 for rel in image.relocations))
            self.assertEqual(fixups(image), [])

    def test_reject_other_architecture(self):
        with self.assertRaisesRegex(ValueError, 'big-endian ELF32 m68k'):
            Image('/bin/true')


if __name__ == '__main__':
    unittest.main()
