"""Private glyphs recover source letters, with no old-encoding compatibility."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'applets/BibleWise'


class SmallCapsCopy(unittest.TestCase):
    def test_actual_native_filter_against_shared_descriptor(self):
        source=(APP/'BibleWise.c').read_text()
        start=source.index('typedef struct { unsigned token, flags; } NativeTextFilter;')
        stop=source.index('static int FindWordOffset',start)
        function=source[start:stop]
        descriptor=json.loads((ROOT/'os3k/charsets/neo-smallcaps.json').read_text())
        expected={int(letter[style],16):int(letter['canonical'],16)
                  for letter in descriptor['letters'] for style in descriptor['styles']}
        expected.update({c:c for c in range(48,58)})
        regular={int(letter['canonical'],16):int(letter['regular'],16)for letter in descriptor['letters']}
        encoded_word=','.join(hex(regular[ord(c)])for c in 'ord')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);driver=path/'filter.c';binary=path/'filter'
            driver.write_text('#include <stdio.h>\n#include "charsets/neo-smallcaps.h"\n'
                '#define VERSE_FONT_BEGIN 0xb1\n#define VERSE_FONT_END 0xb2\n'
                '#define NATIVE_WRAP_SPACE 0x81\n#define NATIVE_WRAP_HYPHEN 0xad\n'+function+'''
int main(void) {
 for(unsigned c=0;c<256;++c) {
  NativeTextFilter filter={0,12};
  printf("%d\\n",NativeTextCharacter(&filter,c));
 }
 const unsigned bytes[]={'L',0xb1,12,0xb1,
  PRIVATE_WORD,0xb2,12,0xb2,' ','G','o','d',0x92};
 NativeTextFilter filter={0,0};
 for(unsigned i=0;i<sizeof(bytes)/sizeof(*bytes);++i) {
  int c=NativeTextCharacter(&filter,bytes[i]);
  if(c>=0) putchar(c);
 }
}
''')
            driver.write_text(driver.read_text().replace('PRIVATE_WORD',encoded_word))
            subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-I'+str(ROOT/'os3k'),str(driver),'-o',str(binary)],check=True)
            raw=subprocess.check_output([str(binary)])
            values=raw.split(b'\n',256)
            actual=[int(v)for v in values[:256]]
            # Tag delimiters consume tokens rather than producing characters.
            for code,value in enumerate(actual):
                self.assertEqual(value,expected.get(code,-1),hex(code))
            self.assertEqual(values[256],b'Lord God\x92')


if __name__=='__main__': unittest.main()
