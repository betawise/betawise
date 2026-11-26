"""Check the production packed-H scan and fallback glyph placement."""
from pathlib import Path
import subprocess,tempfile,unittest,json
ROOT=Path(__file__).resolve().parents[2]
class Superscripts(unittest.TestCase):
 def test_packed_pages_and_clamping(self):
  source=(ROOT/'applets/BibleWise/BibleWise.c').read_text()
  scan=source[source.index('static unsigned CapitalTop('):source.index('static int ConfigureVerseFont(')]
  a=source.index('        unsigned top = CapitalTop(font), bank;')
  b=source.index('        g_verse_font.bitmap_data = superscript_bitmaps[bank];',a)+len('        g_verse_font.bitmap_data = superscript_bitmaps[bank];')
  placement=source[a:b].replace('return 0;','return;')
  gen={'__file__':str(ROOT/'applets/BibleWise/generate_superscript.py')};exec(compile((ROOT/'applets/BibleWise/generate_superscript.py').read_text(),'generator','exec'),gen)
  code='''#include <stdint.h>
#include <string.h>
#include <assert.h>
typedef struct { unsigned height,width; const uint8_t* glyph; const uint8_t* bitmap_data; } FontHeader_t;
static unsigned GlyphWidth(FontHeader_t* f,unsigned c){(void)c;return f->width;}
static const uint8_t* GlyphBitmap(FontHeader_t* f,unsigned c){(void)c;return f->glyph;}
static FontHeader_t g_verse_font;
static const uint8_t columns[10][4]=''' + json.dumps(json.loads((ROOT/'research/fonts/superscript-3x5.json').read_text())['columns']).replace('[','{').replace(']','}') + ';\n' + gen['generate']()+scan+'''static void build(FontHeader_t* font){unsigned height=font->height;
'''+placement+'''}
int main(void){
 uint8_t body[64];
 for(unsigned h=5;h<=64;h++)for(unsigned top=0;top<h;top++){
  memset(body,0,sizeof(body));body[top/8*3+2]=1u<<(top%8);
  FontHeader_t f={h,3,body,0};assert(CapitalTop(&f)==top);build(&f);
  unsigned aligned=top>h-5?h-5:top;
  aligned=aligned>=4?4:aligned>=2?2:aligned;
  assert(g_verse_font.height==(h>16?16:h));
  for(unsigned d=0;d<10;d++)for(unsigned y=0;y<g_verse_font.height;y++)for(unsigned x=0;x<4;x++){
   unsigned expected=x<4&&y>=aligned&&y<aligned+5 ? (columns[d][x]>>(y-aligned))&1:0;
   assert(((g_verse_font.bitmap_data[8*(d+1)+4*(y/8)+x]>>(y%8))&1)==expected);
  }
 }
 memset(body,0,sizeof(body));FontHeader_t blank={16,3,body,0};assert(CapitalTop(&blank)==0);
 return 0;
}
'''
  with tempfile.TemporaryDirectory()as directory:
   p=Path(directory);(p/'test.c').write_text(code)
   subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-Wno-unused-const-variable',str(p/'test.c'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
