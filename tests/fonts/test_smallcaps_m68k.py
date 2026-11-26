"""Execute the production table-free codec on m68000, using JSON as the oracle."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('m68k-linux-gnu-gcc') and shutil.which('qemu-m68k'), 'm68k compiler and QEMU required')
class SmallCapsM68K(unittest.TestCase):
    def test_all_inputs_styles_and_decodes(self):
        descriptor=json.loads((ROOT/'os3k/charsets/neo-smallcaps.json').read_text())
        encoding=[[0]*256 for _ in range(3)]
        decoding=[0]*256
        for letter in descriptor['letters']:
            for index,style in enumerate(descriptor['styles']):
                slot=int(letter[style],16)
                decoding[slot]=int(letter['canonical'],16)
                for alias in letter['source']:encoding[index][int(alias,16)]=slot
        for c in range(0x30,0x3A):
            decoding[c]=c
        arrays='static const uint8_t expected[3][256] = {'+','.join('{'+','.join(map(str,row))+'}' for row in encoding)+'};\n'
        arrays+='static const uint8_t decoded[256] = {'+','.join(map(str,decoding))+'};\n'
        letters=[int(letter['canonical'],16) for letter in descriptor['letters']]
        arrays+='static const uint8_t letters[] = {'+','.join(map(str,letters))+'};\n'
        source='''#include "charsets/neo-smallcaps.h"
'''+arrays+'''
int check(void) {
    for (unsigned c=0;c<256;c++) {
        for (unsigned s=0;s<3;s++) {
            uint8_t out=0xCC;
            bool ok=NeoSmallCapsEncodeByte(c,(NeoSmallCapsStyle)s,&out);
            if (ok != !!expected[s][c]) return 1;
            if (out != (ok ? expected[s][c] : 0xCC)) return 2;
        }
        uint8_t out=0xCC;
        bool ok=NeoSmallCapsDecodeByte(c,&out);
        if (ok != !!decoded[c]) return 3;
        if (out != (ok ? decoded[c] : 0xCC)) return 4;
    }
    for (unsigned i=0;i<sizeof(letters);i++) {
        uint8_t c=letters[i],r=NeoSmallCapsRegularFromLowercase(c);
        if(r!=expected[0][c] || (r^0x40)!=expected[1][c] || (r^0x2B)!=expected[2][c]) return 5;
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='smallcaps-sdk-') as directory:
            directory=Path(directory)
            (directory/'test.c').write_text(source)
            (directory/'start.s').write_text('.text\n.globl _start\n_start:\n jsr check\n move.l %d0,%d1\n moveq #1,%d0\n trap #0\n')
            flags=['m68k-linux-gnu-gcc','-m68000','-msoft-float','-fshort-enums','-Os','-ffreestanding','-fno-builtin','-I'+str(ROOT/'os3k')]
            subprocess.run(flags+['-nostdlib','-static','-Wl,--build-id=none',str(directory/'test.c'),str(directory/'start.s'),'-o',str(directory/'test')],check=True,capture_output=True)
            subprocess.run(['qemu-m68k','-cpu','m68000',str(directory/'test')],check=True,timeout=10)
            (directory/'fast.c').write_text('#include "charsets/neo-smallcaps.h"\nuint8_t fast(uint8_t c) { return NeoSmallCapsRegularFromLowercase(c); }\n')
            subprocess.run(flags+['-c',str(directory/'fast.c'),'-o',str(directory/'fast.o')],check=True,capture_output=True)
            symbols=subprocess.check_output(['m68k-linux-gnu-nm','-S',str(directory/'fast.o')],text=True)
            self.assertFalse(any(kind in symbols for kind in (' R ',' r ',' D ',' d ')),symbols)
            size=int(next(line.split()[1] for line in symbols.splitlines() if line.endswith(' fast')),16)
            print(f'Production fast helper: {size} bytes with this compiler; no data tables')
            (directory/'codec.c').write_text('#include "charsets/neo-smallcaps.h"\nuint8_t encode(uint8_t c, unsigned s) { uint8_t v=0; NeoSmallCapsEncodeByte(c,(NeoSmallCapsStyle)s,&v); return v; }\nuint8_t decode(uint8_t c) { uint8_t v=0; NeoSmallCapsDecodeByte(c,&v); return v; }\n')
            subprocess.run(flags+['-c',str(directory/'codec.c'),'-o',str(directory/'codec.o')],check=True,capture_output=True)
            sections=subprocess.check_output(['m68k-linux-gnu-objdump','-h',str(directory/'codec.o')],text=True)
            for line in sections.splitlines():
                fields=line.split()
                if len(fields)>2 and fields[1].startswith(('.rodata','.data')):
                    self.assertEqual(int(fields[2],16),0,sections)



if __name__ == '__main__':unittest.main()
