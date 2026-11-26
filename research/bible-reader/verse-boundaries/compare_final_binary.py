#!/usr/bin/env python3
"""Measure forward/backward direct binary searches, with EOF or movable gap."""
from pathlib import Path
import sys,subprocess
root=Path(__file__).resolve().parents[3];here=root/'research/bible-reader/verse-boundaries';sys.path.insert(0,str(here))
from prepare import prepare
backward='''/* Scan backward from each midpoint to a complete numbered record. */
static NumberedRecord FindEarlierRecord(unsigned target, bool by_position, const uint8_t* base) {
    unsigned first = 0, stop = g_chapter_file_bytes;
    NumberedRecord anchor = {0, 1};
    while(first < stop) {
        unsigned middle = first + (stop - first) / 2;
        BoundaryStream stream;
        stream.base = base;
        stream.position = middle;
        unsigned length, number;
        for(;;) {
            BoundaryFill(&stream);
            number = BoundaryMarker(&stream, &length);
            if(number || !stream.position) break;
            --stream.position;
        }
        if(number && (by_position ? stream.position >= target : number >= target)) stop = stream.position;
        else {
            if(number) { anchor.position = stream.position; anchor.number = number; }
            first = middle + 1;
        }
    }
    return anchor;
}
'''
forward='static bool NextNumberedRecord(BoundaryStream* stream, NumberedRecord* result) {\n    for(;;) {\n        BoundaryFill(stream);\n        if(!stream->available) return false;\n        unsigned skip = 0;\n        while(skip < stream->available && stream->look[skip] != VERSE_FONT_BEGIN) ++skip;\n        if(skip) { BoundaryAdvance(stream, skip); continue; }\n        unsigned length = 0;\n        unsigned number = BoundaryMarker(stream, &length);\n        if(number && number <= g_verse_count) {\n            result->position = stream->position;\n            result->number = number;\n            BoundaryAdvance(stream, length);\n            return true;\n        }\n        BoundaryAdvance(stream, 1);\n    }\n}\n\n/* Keep the last numbered record below the target as the parser anchor.\n * This removes backward-window scans and shares one search for both inputs. */\nstatic NumberedRecord FindEarlierRecord(unsigned target, bool by_position, const uint8_t* base) {\n    unsigned first = 0, stop = g_chapter_file_bytes;\n    NumberedRecord anchor = {0, 1};\n    while(first < stop) {\n        unsigned middle = first + (stop - first) / 2;\n        BoundaryStream stream;\n        stream.base = base;\n        stream.position = middle;\n        NumberedRecord found;\n        ReaderProbeSet(phase, 716);\n        bool present = NextNumberedRecord(&stream, &found);\n        ReaderProbeSet(phase, 717);\n        if(!present || (by_position ? found.position >= target : found.number >= target)) stop = middle;\n        else {\n            anchor = found;\n            first = stream.position;\n        }\n    }\n    return anchor;\n}\n\n\n'
for name in ('forward-final','backward-final'):
 app=prepare('baseline','-'+name)
 text=(root/'applets/BibleWise/BibleWise.c').read_text().replace('"../../tests/mame/asneo/BibleWiseProbe.h"','"'+str(root/'tests/mame/asneo/BibleWiseProbe.h')+'"')
 (app/'BibleWise.c').write_text(text)
 header=(root/'applets/BibleWise/ChapterPositions.h').read_text()
 start=header.index('static NumberedRecord FindEarlierRecord(');end=header.index('static unsigned ReconstructBinaryBoundary(',start)
 header=header[:start]+(backward if name.startswith('backward') else forward)+'\n'+header[end:]
 (app/'ChapterPositions.h').write_text(header)
 subprocess.run(['make','-s','-C',str(app),'VERSION=NKJV'],check=True,stdout=(app/'result.log').open('w'),stderr=subprocess.STDOUT)
 binary=app/'build/NKJV/BibleWise-NKJV.OS3KApp';data=binary.read_bytes()
 import struct
 print(name,struct.unpack_from('>II',data,4),flush=True)

app=prepare('baseline','-gap-final')
text=(root/'applets/BibleWise/BibleWise.c').read_text().replace('"../../tests/mame/asneo/BibleWiseProbe.h"','"'+str(root/'tests/mame/asneo/BibleWiseProbe.h')+'"')
start=text.index('static bool MoveChapterGapToEnd(void)');end=text.index('static void OpenChapter(',start)
text=text[:start]+text[end:];text=text.replace(' || !MoveChapterGapToEnd()','')
(app/'BibleWise.c').write_text(text)
header=(root/'applets/BibleWise/ChapterPositions.h').read_text()
header=header.replace('unsigned position, available;','unsigned position, available;\n    uint8_t seam[15];')
reference=(here/'direct_boundaries.h').read_text();start=reference.index('static void BoundaryFill(');end=reference.index('static void BoundaryAdvance(',start)
fill=reference[start:end];fill=fill[fill.index('#else')+5:fill.rindex('#endif')]+ '}\n\n'
start=header.index('static void BoundaryFill(');end=header.index('static void BoundaryAdvance(',start)
header=header[:start]+'static void BoundaryFill(BoundaryStream* stream) {'+fill+header[end:]
start=header.index('    if(g_editor.gap_start !=');end=header.index('    const uint8_t* base =',start)
header=header[:start]+header[end:];(app/'ChapterPositions.h').write_text(header)
subprocess.run(['make','-s','-C',str(app),'VERSION=NKJV'],check=True,stdout=(app/'result.log').open('w'),stderr=subprocess.STDOUT)
print('backward with gap seam:', struct.unpack_from('>II', (app/'build/NKJV/BibleWise-NKJV.OS3KApp').read_bytes(), 4))
