"""Private charset aliases, canonical decoding and Python/C parity."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'os3k'))
from charsets import smallcaps


class SmallCaps(unittest.TestCase):
    def setUp(self):
        self.descriptor=smallcaps.load()
        self.lookup=smallcaps.tables(self.descriptor)

    def test_table_free_assignment_and_styles(self):
        self.assertEqual(len(self.descriptor['letters']),62)
        for letter in self.descriptor['letters']:
            source=int(letter['canonical'],16)
            regular=int(letter['regular'],16)
            self.assertEqual(regular,smallcaps.regular_from_lowercase(source))
            self.assertEqual(int(letter['italic'],16),regular ^ 0x2B)
            self.assertEqual(int(letter['bold'],16),regular ^ 0x40)
        self.assertNotIn('Ń',{l['text'] for l in self.descriptor['letters']})
        self.assertEqual(smallcaps.encode(ord('a'),'regular'),0x4B)
        self.assertEqual(smallcaps.encode(ord('a'),'italic'),0x60)
        self.assertEqual(smallcaps.encode(ord('a'),'bold'),0x0B)

    def test_formulas_match_independent_descriptor_oracles(self):
        for style_index,style in enumerate(smallcaps.STYLES):
            for source in range(256):
                index=self.lookup['source_to_index'][source]
                expected=None if index==255 else self.lookup['variants'][index][style_index]
                self.assertEqual(smallcaps.encode(source,style),expected,(source,style))
        for slot in range(256):
            self.assertEqual(smallcaps.decode(slot),self.lookup['decode'][slot] or None,slot)
        header=(ROOT/'os3k/charsets/neo-smallcaps.h').read_text()
        self.assertNotIn('static const',header)
        self.assertNotIn('[256]',header)

    def test_assignment_is_automatic_and_excludes_reserved_slots(self):
        from charsets.assign_smallcaps import assign
        self.assertEqual(assign(self.descriptor), self.descriptor)
        import copy
        blocked = copy.deepcopy(self.descriptor)
        blocked['reserved'].append(self.descriptor['letters'][0]['italic'])
        with self.assertRaises(ValueError):
            assign(blocked)

    def test_ij_is_required_in_all_three_styles(self):
        ij=next(l for l in self.descriptor['letters'] if l['text']=='IJ')
        self.assertFalse(ij.get('optional',False))
        for style in smallcaps.STYLES:
            self.assertEqual(smallcaps.encode(5,style),int(ij[style],16))

    def test_lowercase_and_canonical_decode(self):
        for style in smallcaps.STYLES:
            for source in range(256):
                glyph=smallcaps.encode(source,style)
                if glyph is None:continue
                decoded=smallcaps.decode(glyph)
                self.assertIsNotNone(decoded)
                self.assertEqual(smallcaps.encode(decoded,style),glyph)
        for source,canonical in ((ord('a'),ord('a')),(0xDF,0xDF),(0xFF,0xFF),(5,5)):
            glyph=smallcaps.encode(source,'italic')
            self.assertEqual(smallcaps.decode(glyph),canonical)
        for source in (ord('A'), 0xC0, 0x8A, 0x9F, *range(0x30, 0x3A)):
            self.assertIsNone(smallcaps.encode(source, 'regular'))
        self.assertIsNone(smallcaps.encode(4,'regular'))
        for letter in self.descriptor['letters']:
            self.assertEqual(smallcaps.encode(int(letter['canonical'],16),'regular'),int(letter['regular'],16))
        self.assertIsNone(smallcaps.encode(ord(' '),'regular'))
        self.assertIsNone(smallcaps.encode(0xD7,'regular')) # multiplication
        self.assertEqual(smallcaps.decode(smallcaps.regular_from_lowercase(0xDF) ^ 0x2B),0xDF) # private Italic SS
        with self.assertRaises(ValueError):smallcaps.encode(65,'bolditalic')

    def test_generator_is_current(self):
        subprocess.run([sys.executable,str(ROOT/'os3k/charsets/generate_smallcaps.py'),'--check'],check=True,capture_output=True)

    @unittest.skipUnless(shutil.which('cc'),'host C compiler required')
    def test_c_matches_python_for_every_byte_and_style(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            source=path/'test.c';binary=path/'test'
            source.write_text('''#include <stdio.h>
#include "charsets/neo-smallcaps.h"
static const uint8_t regulars[]={REGULARS};
int main(void) {
 for (unsigned style=0;style<3;++style) for(unsigned c=0;c<256;++c) {
  uint8_t out=0xCC; bool ok=NeoSmallCapsEncodeByte(c,style,&out);
  printf("%d %u\\n",ok,out);
 }
 for(unsigned c=0;c<256;++c) {
  uint8_t out=0xCC; bool ok=NeoSmallCapsDecodeByte(c,&out);
  printf("%d %u\\n",ok,out);
 }
 for(unsigned style=0;style<3;++style) for(unsigned i=0;i<sizeof(regulars);++i)
  printf("1 %u\\n",NeoSmallCapsStyleRegularByte(regulars[i],style));
 if(NeoSmallCapsStyleRegularByte(0x41,(NeoSmallCapsStyle)-1)) return 3;
 uint8_t out=0xCC;
 if(NeoSmallCapsEncodeByte('A',(NeoSmallCapsStyle)-1,&out) || out!=0xCC) return 1;
 if(NeoSmallCapsEncodeByte('A',0,NULL) || NeoSmallCapsDecodeByte('A',NULL)) return 2;
 return 0;
}
'''.replace('REGULARS',','.join(str(v) for v in sorted({row[0] for row in self.lookup['variants']} | set(self.lookup['digits'])))))
            subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-I',str(ROOT/'os3k'),str(source),'-o',str(binary)],check=True,capture_output=True)
            actual=subprocess.check_output([str(binary)],text=True).splitlines()
            expected=[]
            for style in smallcaps.STYLES:
                for source in range(256):
                    glyph=smallcaps.encode(source,style)
                    expected.append(f'{int(glyph is not None)} {glyph if glyph is not None else 204}')
            for slot in range(256):
                source=smallcaps.decode(slot)
                expected.append(f'{int(source is not None)} {source if source is not None else 204}')
            regulars=sorted({row[0] for row in self.lookup['variants']} | set(self.lookup['digits']))
            for style in smallcaps.STYLES:
                for regular in regulars:
                    canonical=self.lookup['decode'][regular]
                    glyph=canonical if 0x30 <= canonical <= 0x39 else smallcaps.encode(canonical,style)
                    expected.append(f'1 {glyph}')
            self.assertEqual(actual,expected)


if __name__=='__main__':unittest.main()
