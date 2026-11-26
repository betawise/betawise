"""Host checks for the shared picker, independent of applets and ROM drawing."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class FontPicker(unittest.TestCase):
    def test_grouping_navigation_and_header_bounds(self):
        source = r'''
#include "os3k_font_picker.h"
#include <assert.h>
#include <string.h>
static unsigned reads;
static const char* names[32] = {
 0,"BetaWise - Book Tiny (6 lines)","BetaWise - Book Large (3 lines)",
 "BetaWise - Book Small (5 lines)","BetaWise - Book Medium (4 lines)",
 "BetaWise - Terminal Medium (44x8)","Neo Font - Medium (5 lines)",
 "Neo Font - Small (6 lines)","ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ",
 "Neo Font - Large (3 lines)"
};
static bool read_name(unsigned i,char output[37]) {
 ++reads;
 if(i>=32 || !names[i]) return false;
 strncpy(output,names[i],36);output[36]=0;return true;
}
uint16_t AppletGetId(uint32_t index) {
 return index==6 ? 0xAF75 : index==7 ? 0xAF00 : index==9 ? 0xAF02 : index==10 ? 0x7107 : index==11 ? 0x7108 : index;
}
int main(void) {
 assert(sizeof(FontPickerState)==6);
 FontPickerBegin(read_name,3);
 assert(FontPickerChoice()==3 && g_font_picker.target_lines==5);
 assert(FontPickerCanResize(-1) && FontPickerCanResize(1));
 FontPickerMove(1,0);assert(FontPickerChoice()==5); /* BetaWise Terminal. */
 FontPickerMove(1,0);assert(FontPickerChoice()==6); /* Neo Font five lines. */
 FontPickerMove(1,0);assert(FontPickerChoice()==0); /* System four lines. */
 FontPickerMove(0,1);assert(FontPickerChoice()==32 && g_font_picker.target_lines==7);
 FontPickerMove(-1,0);assert(FontPickerChoice()==7); /* Closest Neo: six. */
 FontPickerMove(-1,0);assert(FontPickerChoice()==5);
 FontPickerMove(-1,0);assert(FontPickerChoice()==1); /* Closest Book: six. */
 assert(g_font_picker.target_lines==7);
 FontPickerMove(0,-1);assert(FontPickerChoice()==3 && g_font_picker.target_lines==5);
 FontPickerMove(0,-1);assert(FontPickerChoice()==4 && g_font_picker.target_lines==4);
 FontPickerMove(1,0);FontPickerMove(-1,0);assert(FontPickerChoice()==4);
 names[4]=0;
 FontPickerBegin(read_name,3);FontPickerMove(0,-1);assert(FontPickerChoice()==2);
 assert(!FontPickerCanResize(-1) && FontPickerCanResize(1));
 FontPickerMove(0,-1);assert(FontPickerChoice()==2);
 FontPickerEdge(true);assert(FontPickerChoice()==8);
 assert(!FontPickerCanResize(-1) && !FontPickerCanResize(1));
 FontPickerEdge(false);assert(FontPickerChoice()==2);
 FontPickerBegin(read_name,31);assert(FontPickerChoice()==0);
 names[10]="Neo Font - Micro (7 lines)";
 names[11]="Neo Font - Small (6 lines)";
 FontPickerBegin(read_name,10);
 FontPickerMove(1,0);assert(FontPickerChoice()==7); /* Native Neo Font family. */
 FontPickerMove(1,0);assert(FontPickerChoice()==11); /* Community Small stays separate. */
 assert(!FontPickerCanResize(-1) && !FontPickerCanResize(1));
 assert(reads>32);return 0;
}

'''
        with tempfile.TemporaryDirectory(prefix='font-picker-model-') as directory:
            directory=Path(directory)
            (directory/'test.c').write_text(source)
            subprocess.run(['gcc','-std=c11','-ffunction-sections','-fdata-sections',
                '-I'+str(ROOT/'os3k'),
                str(directory/'test.c'),str(ROOT/'os3k/os3k_font_picker.c'),
                '-Wl,--gc-sections','-o',str(directory/'test')],check=True,capture_output=True)
            subprocess.run([str(directory/'test')],check=True)

if __name__=='__main__': unittest.main()
