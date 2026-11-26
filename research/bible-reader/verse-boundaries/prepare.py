#!/usr/bin/env python3
"""Prepare isolated applet variants; leave the working production tree untouched."""
import argparse
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parents[3]
APP=ROOT/'applets/BibleWise'
HERE=Path(__file__).resolve().parent


def prepare(variant, suffix="", relocation=False):
    target=HERE/'build'/(variant+suffix)/'app'
    target.mkdir(parents=True,exist_ok=True)
    for pattern in ('*.c','*.h','*.S','*.py'):
        for source in APP.glob(pattern):shutil.copy2(source,target/source.name)
    build=target/'build';build.mkdir(exist_ok=True)
    for name,path in [('upstream',APP/'upstream'),('build/data',APP/'build/data'),('build/generated',APP/'build/generated')]:
        link=target/name
        if not link.exists():link.symlink_to(path,target_is_directory=True)
    make=(APP/'Makefile').read_text().replace('include ../../Makefile.common','include '+str(ROOT/'Makefile.common'))
    make=make.replace('../../research/fonts/superscript-3x5.json',str(ROOT/'research/fonts/superscript-3x5.json'))
    make=re.sub(r'\$\(DATA_FILES\) &:.*?\n\tpython3 build_data.py[^\n]*\n', '# Uses the existing immutable production data resources.\n',make,flags=re.S)
    (target/'Makefile').write_text(make)
    source = HERE/'reference/pre-binary-lifecycle.c' if variant.startswith('cached-direct-') else HERE/'reference/BibleWise.c'
    text=source.read_text()
    text=text.replace('"../../tests/mame/asneo/BibleWiseProbe.h"','"'+str(ROOT/'tests/mame/asneo/BibleWiseProbe.h')+'"')
    if variant!='baseline':
        stride=1 if variant=='one' else 256 if variant in ('none','fast','binary','marker','marker-bmh','linear','lean','compact-binary','tiny-binary','small-binary','direct-linear','direct-binary','end-gap','eof-linear','eof-binary','readonly-view','readonly-prewrapped','eof-fast-linear','eof-fast-binary','editable-retained','editable-cached','cached-direct-binary','cached-direct-marker','cached-direct-bmh') else 16
        for name in ('g_search_offsets','g_verse_offsets','g_verse_ends'):
            text=re.sub(r'^static uint16_t '+name+r'\[.*?\];\n','',text,flags=re.M)
        location=text.index('static unsigned FindVerseAtOffset(')
        header='file_index.h' if variant in ('file','file-nocache') else 'boundaries.h'
        if variant=='fast':
            from fast_boundaries import generate
            header=str(generate(HERE).relative_to(HERE))
        elif variant in ('cached-direct-marker','cached-direct-bmh'):
            from direct_marker_boundaries import generate
            header=str(generate(HERE,variant=='cached-direct-bmh').relative_to(HERE))
        elif variant in ('direct-linear','direct-binary','end-gap','eof-linear','eof-binary','readonly-view','readonly-prewrapped','eof-fast-linear','eof-fast-binary','editable-retained','editable-cached','cached-direct-binary','cached-direct-marker','cached-direct-bmh'):
            header='direct_boundaries.h'
        elif variant=='small-binary':
            from small_binary_boundaries import generate
            header=str(generate(HERE).relative_to(HERE))
        elif variant=='tiny-binary':
            from tiny_binary_boundaries import generate
            header=str(generate(HERE).relative_to(HERE))
        elif variant=='compact-binary':
            from compact_binary_boundaries import generate
            header=str(generate(HERE).relative_to(HERE))
        elif variant=='lean':
            from lean_boundaries import generate
            header=str(generate(HERE).relative_to(HERE))
        elif variant=='linear':
            from linear_boundaries import generate
            header=str(generate(HERE).relative_to(HERE))
        elif variant=='marker-bmh':
            from marker_bmh_boundaries import generate
            header=str(generate(HERE).relative_to(HERE))
        elif variant=='marker':
            from marker_boundaries import generate
            header=str(generate(HERE).relative_to(HERE))
        elif variant=='binary':
            from binary_boundaries import generate
            header=str(generate(HERE).relative_to(HERE))
        elif variant=='file-nocache':
            from cache_free import generate
            header=str(generate(HERE).relative_to(HERE))
        options='#define RESEARCH_BOUNDARY_NONE 1\n' if variant in ('none','fast','binary','marker','marker-bmh','linear','lean','compact-binary','tiny-binary','small-binary','direct-linear','direct-binary','end-gap','eof-linear','eof-binary','readonly-view','readonly-prewrapped','eof-fast-linear','eof-fast-binary','editable-retained','editable-cached','cached-direct-binary','cached-direct-marker','cached-direct-bmh') else ''
        if variant in ('direct-linear','eof-linear','eof-fast-linear'): options+='#define DIRECT_LINEAR 1\n'
        if variant in ('eof-fast-linear','eof-fast-binary'): options+='#define DIRECT_CONTIGUOUS 1\n'
        text=text[:location]+options+f'#define RESEARCH_BOUNDARY_STRIDE {stride}\n#include "{HERE}/{header}"\n\n'+text[location:]
        start=text.index('static unsigned FindVerseAtOffset(');end=text.index('\nstatic void ObserveReaderForTesting',start)
        text=text[:start]+'''static unsigned FindVerseAtOffset(unsigned offset) {
    return FindBoundaryVerse(FileOffsetWithoutGap(offset));
}
'''+text[end:]
        text=text.replace('#include "../../research/bible-reader/offset-rebuild-probe.h"','static void ProbeRebuildVerseOffsets(void) {}')
        # Replace decoder bookkeeping with index-only writes before transforming readers.
        start=text.index('static int FlushAlignedLine(');end=text.index('static void OpenChapter(',start)
        block=text[start:end]
        if variant in ('file','file-nocache'):
            for name,field in [('g_search_offsets','search'),('g_verse_offsets','start'),('g_verse_ends','end')]:
                block=re.sub(name+r'\[([^\]]+)\]',r'output->verse_bounds[\1].'+field,block)
            # DecodeChapterToFile owns a value, whereas event callbacks receive a pointer.
            block=block.replace('static int DecodeChapterToFile(void) {','static int DecodeChapterToFile(void) {\n    g_boundary_cache_verse = 0;')
            block=block.replace('    return !output.buffered || AppendChapterBytes(output.buffer, output.buffered);',
                '    if(output.buffered && !AppendChapterBytes(output.buffer, output.buffered)) return 0;\n    return StoreFileIndex(output.verse_bounds);')
        else:
            block=re.sub(r'if\(g_search_offsets\[index\] >= base\) g_search_offsets\[index\] \+= padding;', 'ShiftSearchOffset(index, base, padding);',block)
            block=re.sub(r'^.*if\(g_verse_offsets\[index\].*\n','',block,flags=re.M)
            block=re.sub(r'^.*if\(index < output->verse && g_verse_ends\[index\].*\n','',block,flags=re.M)
            block=re.sub(r'g_search_offsets\[output->verse\] = ChapterOutputOffset\(output\);','RecordSearchOffset(output->verse, ChapterOutputOffset(output));',block)
            block=re.sub(r'^\s*g_verse_(?:offsets|ends)\[output->verse\] = ChapterOutputOffset\(output\);\n','\n',block,flags=re.M)
            block=block.replace('static int DecodeChapterToFile(void) {','static int DecodeChapterToFile(void) {\n    g_boundary_cache_verse = 0;')
        text=text[:start]+block+text[end:]
        if variant in ('file','file-nocache'):
            text=text.replace('    unsigned buffered, verse, face, first_atom, line_start, separator;', '    VerseBounds verse_bounds[BIBLE_MAX_CHAPTER_VERSES + 1];\n    unsigned buffered, verse, face, first_atom, line_start, separator;')
        for name,field in [('g_search_offsets','search'),('g_verse_offsets','start'),('g_verse_ends','end')]:
            text=re.sub(name+r'\[([^\]]+)\]',r'LookupBoundary(\1)->'+field,text)
    else:
        text=text.replace('"../../research/bible-reader/offset-rebuild-probe.h"','"'+str(ROOT/'research/bible-reader/offset-rebuild-probe.h')+'"')
    text=text.replace('    g_reader.verse = g_chapter_loaded ?', '    ReaderProbeSet(phase, 712);\n    g_reader.verse = g_chapter_loaded ?').replace('    g_reader.bytes = g_chapter_file_bytes;', '    ReaderProbeSet(phase, 713);\n    g_reader.bytes = g_chapter_file_bytes;')
    if variant not in ('baseline','file-nocache'):
        save='    VerseBounds observed_cache = g_boundary_cache;\n    unsigned observed_verse = g_boundary_cache_verse;\n'
        restore='    g_boundary_cache = observed_cache;\n    g_boundary_cache_verse = observed_verse;\n'
        if variant in ('sparse','none','file','fast','binary','marker','marker-bmh','linear','lean','compact-binary','tiny-binary','small-binary','direct-linear','direct-binary','end-gap','eof-linear','eof-binary','readonly-view','readonly-prewrapped','eof-fast-linear','eof-fast-binary','editable-retained','editable-cached','cached-direct-binary','cached-direct-marker','cached-direct-bmh'):
            save+='    unsigned observed_limit = g_boundary_cache_limit;\n'
            restore+='    g_boundary_cache_limit = observed_limit;\n'
        text=text.replace('    ReaderProbeSet(phase, 712);\n', '    ReaderProbeSet(phase, 712);\n'+save)
        text=text.replace('    ReaderProbeSet(phase, 713);\n', restore+'    ReaderProbeSet(phase, 713);\n')
    if variant in ('file','file-nocache'):
        text=text.replace('static int NativeTextCharacter(NativeTextFilter* filter, unsigned byte) {',
            'static int NativeTextCharacter(NativeTextFilter* filter, unsigned byte) {\n'
            '    if(filter->token >= 0x100) { if(--filter->token == 0x100) filter->token = 0; return -1; }\n'
            '    if(filter->token == 4) { filter->token = 0x100 | (byte - 2); return -1; }\n'
            '    if(!filter->token && byte == FILE_INDEX_RECORD) { filter->token = 4; return -1; }')
        first=text.index('static bool UpdateTextRegions(')
        last=text.index('static bool RestoreCaretInViewport',first)
        section=text[first:last].replace('            unsigned character = buffer[index];',
            '            unsigned character = buffer[index];\n'
            '            if(token >= 0x100) { if(--token == 0x100) token = 0; continue; }\n'
            '            if(token == 4) { token = 0x100 | (character - 2); continue; }\n'
            '            if(!token && character == FILE_INDEX_RECORD) { token = 4; continue; }')
        text=text[:first]+section+text[last:]
    if variant=='file-nocache':
        text=text.replace('    g_boundary_cache_verse = 0;\n','')
        for field,index in [('search',0),('start',1),('end',2)]:
            text=re.sub(r'LookupBoundary\(([^\n]+?)\)->'+field,r'ReadBoundaryField(\1, '+str(index)+')',text)
    if variant in ('end-gap','eof-linear','eof-binary','eof-fast-linear','eof-fast-binary'):
        marker = '    ReaderProbeSet(phase, 2);\n    g_chapter_loaded = 1;'
        insertion = """    /* Move native gap to EOF through public editor calls. */
    TextScan_t end_scan;
    if(TextScanInit(&g_editor, &end_scan, TEXT_POSITION_START)) goto failed;
    end_scan.offset = g_chapter_file_bytes + g_editor.gap_end - g_editor.gap_start;
    if(TextEditorSetScanPosition(&end_scan, false) || TextEditorSavePosition(&g_editor)) goto failed;
"""
        assert marker in text
        text=text.replace(marker, insertion+marker)
    if variant=='readonly-view':
        text=text.replace('    status = TextEditorInit(&g_editor, READER_FILE, TEXT_EDITOR_EDITABLE,',
            '    FileUpdateFlags(READER_FILE, 4, 1);\n    status = TextEditorInit(&g_editor, READER_FILE, TEXT_EDITOR_READ_ONLY,')
        text=text.replace('    int32_t status = TextEditorSetFonts(&g_editor, g_body_fonts[0], g_body_fonts[1],\n        g_body_fonts[2], &g_verse_font, false);',
            '    int32_t status = 0;\n    g_editor.fonts[0] = g_body_fonts[0];\n    g_editor.fonts[1] = g_body_fonts[1];\n    g_editor.fonts[2] = g_body_fonts[2];\n    g_editor.fonts[3] = &g_verse_font;')
        text=text.replace('    if(!draw) return 1;', '    if(!draw) return 1;\n    RedrawChapterWithMode(READER_PAINT_VIEWPORT);')
    if variant=='readonly-prewrapped':
        marker='    ObserveReaderForTesting();\n    return;\n\nfailed:'
        replacement="""    /* Research: preserve the ROM's wrap points, remove its gap, then
     * initialize a real read-only descriptor and install borrowed fonts. */
    TextEditor_t old = g_editor;
    unsigned top = FileOffsetWithoutGap(old.viewport_offset);
    unsigned caret = FileOffsetWithoutGap(old.caret_offset);
    unsigned anchor = FileOffsetWithoutGap(old.selection_anchor);
    unsigned gap = old.gap_end - old.gap_start;
    if(FileSeek(READER_FILE, old.gap_start, FILE_SEEK_START)<0 ||
        FileDeleteAtPosition(gap)!=(int32_t)gap) goto failed;
    FileUpdateFlags(READER_FILE,4,1);
    if(TextEditorInit(&g_editor,READER_FILE,TEXT_EDITOR_READ_ONLY,
        READER_MAX_FILE_BYTES,0,0,READER_TEXT_WIDTH,64)) goto failed;
    unsigned face;
    for(face=0;face<4;++face) g_editor.fonts[face]=old.fonts[face];
    g_editor.height=old.height;g_editor.layout_height=old.layout_height;
    g_editor.viewport_offset=top;g_editor.viewport_scan_flags=old.viewport_scan_flags;
    g_editor.viewport_scan_line=old.viewport_scan_line;
    g_editor.caret_offset=caret;g_editor.caret_x=old.caret_x;g_editor.caret_y=old.caret_y;
    g_editor.caret_scan_flags=old.caret_scan_flags;g_editor.caret_scan_line=old.caret_scan_line;
    g_editor.selection_anchor=anchor;g_editor.selection_flags=old.selection_flags;
    g_editor.selection_state=old.selection_state;
    RedrawChapterWithMode(READER_PAINT_VIEWPORT);
    ObserveReaderForTesting();
    return;

failed:"""
        assert marker in text
        text=text.replace(marker,replacement)
    if variant=='readonly-prewrapped':
        original='    int32_t status = TextEditorSetFonts(&g_editor, g_body_fonts[0], g_body_fonts[1],\n        g_body_fonts[2], &g_verse_font, false);'
        replacement="""    int32_t status=0;
    if(g_editor.read_only) {
        g_editor.fonts[0]=g_body_fonts[0];g_editor.fonts[1]=g_body_fonts[1];
        g_editor.fonts[2]=g_body_fonts[2];g_editor.fonts[3]=&g_verse_font;
    } else status=TextEditorSetFonts(&g_editor,g_body_fonts[0],g_body_fonts[1],g_body_fonts[2],&g_verse_font,false);"""
        assert original in text
        text=text.replace(original,replacement)
        text=text.replace('    status = TextEditorSavePosition(&g_editor);',
            '    status = g_editor.read_only ? (FileSeek(READER_FILE,g_editor.viewport_offset,FILE_SEEK_START)<0?-1:0) : TextEditorSavePosition(&g_editor);')
        text=text.replace('if(FileOpen(READER_FILE, FILE_OPEN_KEEP_POSITION) < 0 || TextEditorRefresh(&g_editor) ||\n                    SetReadingFonts() || !RestoreReadingView(&view))',
            'if(FileOpen(READER_FILE, FILE_OPEN_KEEP_POSITION) < 0 || (!g_editor.read_only && TextEditorRefresh(&g_editor)) ||\n                    SetReadingFonts() || (!g_editor.read_only && !RestoreReadingView(&view)))')
    if variant in ('editable-retained','editable-cached'):
        original='if(FileOpen(READER_FILE, FILE_OPEN_KEEP_POSITION) < 0 || TextEditorRefresh(&g_editor) ||\n                    SetReadingFonts() || !RestoreReadingView(&view))'
        assert original in text
        text=text.replace(original,'if(FileOpen(READER_FILE, FILE_OPEN_KEEP_POSITION)<0)')
        marker='                ClearScreen();\n                DrawSidebar();\n                RedrawChapterWithMode(READER_PAINT_VIEWPORT);'
        replacement="""                g_editor.fonts[0]=g_body_fonts[0];g_editor.fonts[1]=g_body_fonts[1];
                g_editor.fonts[2]=g_body_fonts[2];g_editor.fonts[3]=&g_verse_font;
"""+marker
        assert marker in text
        text=text.replace(marker,replacement)
    if variant=='editable-cached':
        original='    if(status || TextEditorSetScanPosition(&position, false)) return;'
        replacement="""    if(status) return;
    /* The viewport scanner already holds current-font layout state. */
    g_editor.caret_offset=position.offset;
    if(g_editor.caret_offset>=g_editor.gap_start && g_editor.caret_offset<g_editor.gap_end)
        g_editor.caret_offset=g_editor.gap_end;
    g_editor.caret_scan_flags=position.flags;
    g_editor.caret_scan_line=position.line_state;
    g_editor.caret_x=position.x;
    g_editor.caret_y=position.y;"""
        assert original in text
        text=text.replace(original,replacement)
    if relocation:
        marker='static char g_input[READER_FIND_MAX + 1];'
        text=text.replace(marker,'#if BIBLEWISE_TEST\nstatic bool g_test_relocation;\n#endif\n'+marker)
        marker='static void HandleCharacter(unsigned character) {'
        payload='word '*2048
        extra="""
#if BIBLEWISE_TEST
    if(character=='Z' || character=='z') {
        static const char payload[]="""+repr(payload).replace("'",'"')+""";
        ReaderProbeSet(rebuild_bytes,(uintptr_t)FileBindState(READER_FILE,NULL,NULL,NULL,NULL));
        g_test_relocation=true;
        if(ClipboardSet(payload,sizeof(payload)-1,1)<0) ReaderProbeSet(error,900);
        ObserveReaderForTesting();
        return;
    }
#endif
"""
        text=text.replace(marker,marker+extra)
        marker='    g_reader.bytes = g_chapter_file_bytes;'
        text=text.replace(marker,marker+'\n    if(g_test_relocation) ReaderProbeSet(rebuild_ok,(uintptr_t)FileBindState(READER_FILE,NULL,NULL,NULL,NULL));')
    from profile_modes import instrument
    text=instrument(text)
    (target/'BibleWise.c').write_text(text)
    return target


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant',choices=['baseline','one','sparse','none','file','fast','file-nocache','binary','marker','marker-bmh','linear','lean','compact-binary','tiny-binary','small-binary','direct-linear','direct-binary','end-gap','eof-linear','eof-binary','readonly-view','readonly-prewrapped','eof-fast-linear','eof-fast-binary','editable-retained','editable-cached','cached-direct-binary','cached-direct-marker','cached-direct-bmh'],required=True)
    print(prepare(parser.parse_args().variant))
