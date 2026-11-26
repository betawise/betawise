"""Native quote encoding, word identity and pinned ROM glyph contracts."""
import hashlib
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
APP = ROOT/'betawise/applets/BibleWise'
sys.path.insert(0,str(APP))
from convert_source import convert_text, encode_native, decode_native
from compress_text import build_container
from build_index import build_index, grammar_summaries, WORD


class NativeTextTests(unittest.TestCase):
    def test_curly_quotes_survive_normalization_and_encoding(self):
        text = '“The LORD’s word,” ‘He said.’'
        self.assertEqual(convert_text(text),text)
        raw = encode_native(text)
        self.assertEqual(raw,b'\x93The LORD\x92s word,\x94 \x91He said.\x92')
        self.assertEqual(decode_native(raw),text)

    def test_other_normalization_remains_explicit(self):
        self.assertEqual(convert_text('æ Æ — … 2½'), 'ae AE - ... 2 1/2')
        for text in ['a\x00b','a\x92b','a\nb','snowman ☃']:
            with self.assertRaises(ValueError): convert_text(text)

    def test_curly_apostrophes_are_one_index_word(self):
        raw=encode_native('“LORD’s” man’s man\'s “said”')
        words=WORD.findall(raw.replace(b'\x92',b"'").lower())
        self.assertEqual(words,[b"lord's",b"man's",b"man's",b'said'])
        image,dictionary=build_container([raw+b'\n'],[['Genesis',0,1]], [len(raw)+64])
        index,vocabulary=build_index([raw+b'\n'],dictionary)
        self.assertEqual(vocabulary,3)
        self.assertEqual(index[:8],b'IDXEXP02')
        self.assertIn('man’s',[word.lstrip(' ')for word in dictionary])
        self.assertEqual(len(grammar_summaries(dictionary,image)),3*struct.unpack_from('>I',image,32)[0])

    def test_quote_slots_match_the_pinned_native_font(self):
        # Explicit source-ROM glyph shapes, not inferred from a display capture.
        path=ROOT/'Ghidra/Alphasmart Neo/SmartApplets/os3kneorom.os3kos'
        rom=path.read_bytes()
        self.assertEqual(hashlib.sha256(rom).hexdigest(),'32fe55bb50c1b58326bd303f14973b8402ddf8bf6662b210e4d5e9f931c7e6c0')
        expected={
            0x91:['...#..','..#...','..##..','..##..'],
            0x92:['..##..','..##..','...#..','..#...'],
            0x93:['.#..#.','#..#..','##.##.','##.##.'],
            0x94:['##.##.','##.##.','.#..#.','#..#..'],
        }
        height,width,stride,_,wp,op,bp=struct.unpack_from('>4B3I',rom,0x3af8e)
        self.assertEqual((height,width,stride,wp,op),(16,6,12,0,0))
        for code,ink in expected.items():
            data=rom[bp-0x410000+code*stride:bp-0x410000+(code+1)*stride]
            rows=[''.join('#' if data[y//8*width+x]>>(y%8)&1 else '.' for x in range(width))for y in range(height)]
            self.assertEqual(rows,['......',*ink]+['......']*11)
            self.assertEqual(rom[0x3c7e0+code],0,'quote must be an ordinary scanner glyph')


if __name__=='__main__': unittest.main()
