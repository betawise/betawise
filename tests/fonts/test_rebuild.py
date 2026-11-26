"""Source recipe invariants, independent of the archived hand-edited glyphs."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('rebuild', ROOT / 'research/fonts/build_fonts.py')
recipe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recipe)


def setUpModule():
    from font_inputs import ensure_fonts
    ensure_fonts()


class Rebuild(unittest.TestCase):
    def test_smallcaps_encoding(self):
        sys.path.insert(0, str(ROOT / 'research/fonts'))
        from smallcaps_sources import write_encoding
        encoding = write_encoding()
        self.assertEqual(len(encoding['letters']), 62)
        slots = [int(slot, 16) for letter in encoding['letters'] for slot in letter['slots'].values()]
        slots += [int(slot, 16) for slot in encoding['superscript_slots'].values()]
        self.assertEqual(len(slots), 196)
        self.assertEqual(len(set(slots)), 196)
        self.assertFalse(set(slots) & {int(s,16) for s in encoding['reserved_slots']})
        by_text = {letter['text']: letter for letter in encoding['letters']}
        for name in ('IJ', 'SS', 'Ÿ'):
            for style, slot in by_text[name]['slots'].items():
                self.assertEqual(encoding['decode'][int(slot,16)]['text'], name)
                self.assertEqual(encoding['decode'][int(slot,16)]['style'], style)
        self.assertNotIn('04',encoding['source_to_regular'])
        self.assertEqual(encoding['source_to_regular']['05'], '7A')
        self.assertEqual(encoding['source_to_regular']['DF'], '55')

    def test_accent_move_preserves_body(self):
        body = {(0, -2), (1, -1), (0, 0)}
        glyph = dict(advance=3, points=body | {(1, -4)})
        moved, operation = recipe.move_accent(ord('á'), glyph, {ord('a'): dict(points=body)}, -3, 1)
        self.assertEqual(moved['points'], body | {(1, -3)})
        self.assertEqual(operation['operation'], 'accent_down')

    def test_generated_mono_is_fixed_across_styles(self):
        for size in recipe.SIZES.values():
            widths = set()
            for style in recipe.STYLES:
                glyphs, _, _ = recipe.fontgen.load_bdf(ROOT / f'fonts/build/bdf/BetaWiseMono/BetaWiseMono-{size}-{style}.bdf')
                widths.update(g[0][0] for g in glyphs if g)
            self.assertEqual(len(widths), 1, size)

    def test_native_bodies_and_euro_exception(self):
        report = json.loads((ROOT / 'fonts/build/bdf/generation-report.json').read_text())
        mapping = recipe.load(ROOT / 'os3k/charsets/neo-us.txt')
        codes = tuple(sorted(set(mapping.values()) - {None}))
        for record in report['fonts']:
            if record['family'] == 'Mono' and record['lines'] == 3:
                self.assertEqual(record['pixels'], 20)
                euro = [o for o in record['operations'] if o['slot'] == '80' and o['style'] == 'Bold']
                self.assertEqual(len(euro), 1)
                self.assertEqual({x for x, y in euro[0]['horizontal']}, {12})
            if record['lines'] != 6:
                continue
            self.assertEqual(record['pixels'], 8)
            for index, filename in enumerate(record['files']):
                _, face = recipe.source(Path(record['sources'][index]), codes)
                actual = recipe.fontgen.load(ROOT / 'fonts/build/bdf' / filename, 'iso8859-1', 63)
                for slot in map(ord, 'acmCG'):
                    glyph = face[slot]
                    if record['family'] == 'Mono' and index == 0 and slot == ord('m'):
                        _, bold = recipe.source(Path(record['sources'][1]), codes)
                        glyph = bold[slot]
                    width, points, _ = recipe.horizontal(glyph, record['mono_width'], record['family'] == 'Mono' and index >= 2)
                    expected = {(x, y + record['baseline']) for x, y in points
                                if 0 <= x < width and 0 <= y + record['baseline'] < record['usable_ink_rows']}
                    image = actual[slot]
                    found = {(x, y) for y in range(image.height) for x in range(image.width) if image.getpixel((x, y))}
                    self.assertEqual(found, expected, (filename, chr(slot)))


if __name__ == '__main__':
    unittest.main()
