"""Derived body offsets and translation-specific table bounds."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'applets/BibleWise'
sys.path.insert(0, str(APP))
from build_data import write_navigation


class VerseOffsets(unittest.TestCase):
    def test_navigation_limit_comes_from_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for count in (3, 176, 220):
                write_navigation(path, [('Test', 0, 2)], [1, count])
                self.assertIn(f'#define BIBLE_MAX_CHAPTER_VERSES {count}\n',
                              (path / 'Navigation.h').read_text())

    def test_derived_offset_matches_emitted_marker_and_empty_verses(self):
        source = (APP / 'BibleWise.c').read_text()
        start = source.index('static int BufferVerseNumber(')
        stop = source.index('static int PositionCaretAtOffset(', start)
        definitions = '\n'.join(line for line in source.splitlines()
                                if line.startswith(('#define VERSE_', '#define READER_REGION_')))
        code = '''#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
static struct { bool verse_numbers; } g_settings;
static uint16_t g_verse_offsets[177], g_verse_ends[177];
static int BufferChapterByte(uint8_t byte,uint8_t* buffer,unsigned* count) {
 buffer[(*count)++]=byte;return 1;
}
''' + definitions + '\n' + source[start:stop] + '''
int main(void) {
 for(unsigned visible=0;visible<2;++visible) {
  g_settings.verse_numbers=visible;
  for(unsigned verse=1;verse<=176;++verse) {
   uint8_t bytes[VERSE_MARKER_BYTES];unsigned count=0;
   assert(BufferVerseNumber(verse,bytes,&count));
   g_verse_offsets[verse]=65000;
   g_verse_ends[verse]=65000+count+1;
   assert(VerseTextOffset(verse)==65000+count);
   g_verse_ends[verse]=65000;
   assert(VerseTextOffset(verse)==65000);
  }
 }
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'test.c').write_text(code)
            subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                            str(path / 'test.c'), '-o', str(path / 'test')], check=True)
            subprocess.run([str(path / 'test')], check=True)


if __name__ == '__main__':
    unittest.main()
