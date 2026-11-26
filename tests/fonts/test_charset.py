"""Shared Neo byte mapping and editable BDF identity metadata."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'os3k'))
from charsets import glyph_name, load


def setUpModule():
    from font_inputs import ensure_fonts
    ensure_fonts()


class NeoCharset(unittest.TestCase):
    def test_mapping_covers_native_slots_and_aliases(self):
        mapping = load(ROOT / 'os3k/charsets/neo-us.txt')
        self.assertEqual(set(mapping), set(range(256)))
        for slot in range(32, 127):
            self.assertEqual(mapping[slot], slot)
        self.assertEqual(mapping[4], ord('Ń'))
        self.assertEqual(mapping[0xd1], ord('Ñ'))
        self.assertEqual(mapping[0x1f], ord('Σ'))
        self.assertEqual(mapping[0x16], mapping[0x0d])
        self.assertEqual(mapping[0x90], mapping[0x60])
        self.assertEqual(glyph_name(0x90, mapping), 'uni0060.alt90')
        self.assertEqual(glyph_name(0x16, mapping), 'uni21B5.alt16')
        self.assertEqual(glyph_name(4, mapping), 'uni0143')
        alias_map = {**mapping, 4: ord('Ñ')}
        self.assertEqual(glyph_name(4, alias_map), 'uni00D1.alt04')
        self.assertEqual(glyph_name(0xd1, mapping), 'uni00D1')

    def test_each_bdf_declares_the_shared_mapping(self):
        mapping = load(ROOT / 'os3k/charsets/neo-us.txt')
        paths = list((ROOT / 'fonts/build/bdf').glob('BetaWise*/*.bdf'))
        self.assertEqual(len(paths), 67, 'run make -C fonts bdfs before font tests')
        for path in paths:
            with self.subTest(font=path.name):
                lines = path.read_text().splitlines()
                self.assertIn('CHARSET_REGISTRY "NEO"', lines)
                self.assertIn('CHARSET_ENCODING "US"', lines)
                self.assertTrue(next(s for s in lines if s.startswith('FONT ')).endswith('-neo-us'))
                names = set()
                for index, line in enumerate(lines):
                    if line.startswith('STARTCHAR '):
                        slot = int(lines[index + 1].split()[1])
                        name = line.split()[1]
                        self.assertEqual(name, glyph_name(slot, mapping))
                        self.assertNotIn(name, names)
                        names.add(name)

    def test_incomplete_or_invalid_maps_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'mapping.txt'
            path.write_text('0x00 UNMAPPED\n')
            with self.assertRaisesRegex(ValueError, 'all 256'):
                load(path)
            path.write_text('0x00 0xD800\n')
            with self.assertRaisesRegex(ValueError, 'invalid Unicode'):
                load(path)


if __name__ == '__main__':
    unittest.main()
