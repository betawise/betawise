"""Exercise production provider filtering and selection after table reordering."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class FontDiscovery(unittest.TestCase):
    def test_filter_and_resolve(self):
        source = (ROOT / 'applets/BibleWise/BibleWise.c').read_text()
        start = source.index('static bool FontAppletName(')
        end = source.index('/* First run only:', start)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            code = path / 'test.c'
            code.write_text('''#include <assert.h>
#include <stdbool.h>
#include <string.h>
static struct { unsigned font_applet; } g_settings;
#include <stdint.h>
#define READER_FONT_SYSTEM_SMALL 32
static uint16_t g_reading_font_id;
static uint16_t ids[8]={0,0xAF00,0xA100,0xAFFA,0xAF01};
static uint16_t AppletGetId(unsigned i) { return i<8 ? ids[i] : 0; }
static unsigned AppletFindById(uint16_t id) { for(unsigned i=1;i<8;i++) if(ids[i]==id)return i;return 0; }
static const char* names[8] = {0,"Neo Font - Small","Random app","BetaWise - Book", "Neo Font - Disabled"};
static bool AppletIsFont(unsigned i) { return i==1||i==3||i==4||i==6; }
static unsigned AppletGetName(unsigned i,char* n) { if(i>=8||!names[i])return 0;strcpy(n,names[i]);return 1; }
static unsigned AppletGetDisableMask(unsigned i) { return i==4; }
''' + source[start:end] + '''
int main(void) {
 char name[37];
 assert(FontAppletName(1,name));
 assert(!FontAppletName(2,name));
 assert(FontAppletName(3,name));
 assert(!FontAppletName(4,name));
 assert(!FontAppletName(7,name));
 SelectReadingFont(1);assert(g_settings.font_applet==1);
 names[6]=names[1];ids[6]=ids[1];names[1]="Other app";ids[1]=0xBEEF;
 names[5]="Another app";ids[5]=0xA101;
 assert(ResolveReadingFont()==6);
 names[6]="Renamed font";
 assert(ResolveReadingFont()==6);
 names[1]="Neo Font - Small";ids[1]=0xBEEF;
 assert(ResolveReadingFont()==6); /* Reused old slot/name must not win. */
 names[6]=0;ids[6]=0;
 assert(ResolveReadingFont()==0);
 SelectReadingFont(2);assert(g_settings.font_applet==0&&g_reading_font_id==0);
 SelectReadingFont(0);assert(g_settings.font_applet==0);
 SelectReadingFont(32);assert(ResolveReadingFont()==32);
 return 0;
}
''')
            binary = path / 'test'
            subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', str(code), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
