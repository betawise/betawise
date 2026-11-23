"""Offline format equivalence and proportional placement regression checks."""
import gzip
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from PIL import Image
import importlib.util

HERE = Path(__file__).resolve().parents[2] / 'fonts'
FIXTURES = Path(__file__).resolve().parent / 'fixtures'
SPEC = importlib.util.spec_from_file_location('fontgen', HERE / 'fontgen.py')
fontgen = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fontgen)


class FontConversion(unittest.TestCase):
    def test_terminal_sources(self):
        for name in ('glyphs', 'glyphs-5x7', 'glyphs-4x6'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
                a = fontgen.load(FIXTURES / (name+'.png'), 'iso8859-1')
                b = fontgen.load(HERE / (name+'.bdf'), 'iso8859-1')
                self.assertEqual(len(b), 256)
                self.assertEqual([(g.size,g.tobytes()) for g in a],
                                 [(g.size,g.tobytes()) for g in b])
                # Same output filename gives the same include guard.
                dest = Path(td)/'glyphs.h'
                fontgen.generate(FIXTURES/(name+'.png'), dest)
                expected = dest.read_bytes()
                fontgen.generate(HERE/(name+'.bdf'), dest)
                self.assertEqual(expected, dest.read_bytes())

    @unittest.skipUnless(shutil.which('bdftopcf'), 'bdftopcf not installed')
    def test_pcf_and_compressed_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            for name in ('glyphs','glyphs-5x7','glyphs-4x6'):
                source = HERE/(name+'.bdf')
                pcf = td/(name+'.pcf')
                subprocess.run(['bdftopcf','-o',str(pcf),str(source)],check=True,capture_output=True)
                dest = td/'font.h'
                fontgen.generate(source,dest);expected=dest.read_bytes()
                for path in (source,pcf):
                    compressed=td/(path.name+'.gz')
                    compressed.write_bytes(gzip.compress(path.read_bytes()))
                    for test in (path,compressed):
                        fontgen.generate(test,dest)
                        self.assertEqual(expected,dest.read_bytes())

    def test_overhang_and_proportional_packing(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'font.bdf';dest=Path(td)/'font.h'
            source.write_text('STARTFONT 2.1\nSTARTPROPERTIES 2\nFONT_ASCENT 2\nFONT_DESCENT 1\nENDPROPERTIES\nCHARS 256\n'+''.join(
                f'STARTCHAR c{c}\nENCODING {c}\nSWIDTH 500 0\nDWIDTH {1 if c==65 else 2} 0\nBBX 3 2 {-1 if c==65 else 0} -1\nBITMAP\nA0\n40\nENDCHAR\n' for c in range(256))+'ENDFONT\n')
            glyphs=fontgen.load(source,'iso8859-1')
            # Negative bearing is shifted; both cells preserve right overhang.
            self.assertEqual(glyphs[65].size,(3,3))
            self.assertEqual([list(glyphs[65].crop((0,y,3,y+1)).getdata())for y in range(3)],
                             [[0,0,0],[1,0,1],[0,1,0]])
            # Give the other glyphs wider advances to exercise variable output.
            source.write_text(source.read_text().replace('DWIDTH 2 0','DWIDTH 4 0'))
            fontgen.generate(source,dest)
            text=dest.read_text()
            self.assertIn('#define GLYPH_PROPORTIONAL 1',text)
            self.assertIn('GLYPH_WIDTHS[256]',text)
            self.assertIn('GLYPH_OFFSETS[256]',text)
            self.assertIn('GLYPH_DATA[1023]',text)
            # First glyph: one blank row, then 1010 and 0100 -> 2,4,2,0.
            self.assertIn('GLYPH_DATA[1023] = {2, 4, 2, 0,',text)

    def test_missing_slots_require_explicit_policy(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'missing.bdf'
            source.write_text('STARTFONT 2.1\nSTARTCHAR question\nENCODING 63\nDWIDTH 1 0\nBBX 1 1 0 0\nBITMAP\n80\nENDCHAR\nENDFONT\n')
            with self.assertRaisesRegex(ValueError,'missing slots'):
                fontgen.load(source,'iso8859-1')
            self.assertEqual(len(fontgen.load(source,'iso8859-1',63)),256)


if __name__=='__main__':
    unittest.main()
