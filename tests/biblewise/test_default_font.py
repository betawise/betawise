"""Exhaustive installed-font ordering and built-in 6x16 fallback checks."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]

class DefaultFont(unittest.TestCase):
    def test_all_reading_font_subsets_and_system_fallback(self):
        source=(ROOT/'applets/BibleWise/BibleWise.c').read_text()
        start=source.index('static uint16_t DefaultReadingFont(')
        stop=source.index('/* The reading-font providers',start)
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);c=p/'test.c';binary=p/'test'
            c.write_text('''#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdbool.h>
#define READER_FONT_SYSTEM_SMALL 32
static unsigned mask;
static unsigned AppletFindById(unsigned id) { return id>=0xAFF0&&id<=0xAFFF&&(mask&(1u<<(id-0xAFF0))) ? id-0xAFF0+1 : 0; }
static unsigned AppletGetDisableMask(unsigned index) { (void)index;return 0; }
''' + source[start:stop].replace('(uint32_t)&font','(uintptr_t)&font')+'''
int main(void) {
 for(mask=0;mask<65536;++mask) printf("%u\\n",DefaultReadingFont());
 mask=0;printf("%u\\n",DefaultReadingFont());
}
''')
            subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror',str(c),'-o',str(binary)],check=True)
            actual=list(map(int,subprocess.check_output([str(binary)],text=True).splitlines()))
            order=[0xAFFA,0xAFF2,0xAFF6,0xAFFE,0xAFFB,0xAFF3,0xAFF7,0xAFFF,0xAFF9,0xAFF1,0xAFF5,0xAFFD,0xAFF8,0xAFF0,0xAFF4,0xAFFC]
            for mask in range(65536):
                expected=next((font for font in order if mask&(1<<(font-0xAFF0))),0xB002)
                self.assertEqual(actual[mask],0 if expected==0xB002 else expected-0xAFF0+1,mask)
            self.assertEqual(actual[-1],0)

if __name__=='__main__': unittest.main()
