#!/usr/bin/env python3
"""Build isolated preallocation/copy comparisons without production changes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
from bounds import chapter_bounds

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PRODUCTION = ROOT / 'applets/BibleWise'
APP = HERE / 'reference'
BUILD = HERE / 'build'


def direct_decode(source):
    first = source.index('static bool MoveChapterGapToEnd(')
    last = source.index('static void OpenChapter(', first)
    source = source[:first] + (HERE / 'direct-decode.h').read_text() + '\n' + source[last:]
    first = source.index('static int AppendChapterBytes(')
    last = source.index('static int BufferVerseNumber(', first)
    source = source[:first] + '''static int BufferChapterByte(uint8_t byte, uint8_t* buffer, unsigned* buffered) {
    buffer[(*buffered)++] = byte;
    return 1;
}

''' + source[last:]
    source = source.replace('    uint8_t buffer[READER_IO_BYTES];\n    unsigned buffered, verse, face, first_atom, line_start, separator;',
        '    uint8_t* bytes;\n    unsigned written, capacity, verse, face, first_atom, line_start, separator;')
    marker = 'static int FlushAlignedLine('
    helper = '''static int DirectChapterByte(ChapterOutput* output, uint8_t byte) {
    if(output->written == output->capacity) return 0;
    output->bytes[output->written++] = byte;
    return 1;
}

'''
    source = source.replace(marker, helper + marker)
    source = source.replace("BufferChapterByte(' ', output->buffer, &output->buffered)", "DirectChapterByte(output, ' ')")
    source = source.replace('BufferChapterByte(output->aligned[index], output->buffer, &output->buffered)', 'DirectChapterByte(output, output->aligned[index])')
    source = source.replace('BufferChapterByte(character, output->buffer, &output->buffered)', 'DirectChapterByte(output, character)')
    source = source.replace('    output.verse = output.first_atom = output.line_start = 1;', '''    output.verse = output.first_atom = output.line_start = 1;
    output.capacity = ChapterCapacity();
    if(FileGetCapacity(READER_FILE) < (int32_t)(output.capacity + 512)) return 0;
    output.bytes = FileBindState(READER_FILE, NULL, NULL, NULL, NULL);
    if(!output.bytes) return 0;''')
    source = source.replace('    return !output.buffered || AppendChapterBytes(output.buffer, output.buffered);', '''    g_chapter_file_bytes = output.written;
    memset(output.bytes + output.written, 0xa7, 512);
    g_editor.gap_start = output.written;
    g_editor.gap_end = output.written + 512;
    if(FileSetCurrentLength(output.written + 512) != (int32_t)(output.written + 512)) return 0;
    FileSetCurrentLength(FILE_LENGTH_RESERVE_CURRENT);
    return 1;''')
    first = source.index('    FileClose();\n', source.index('static void OpenChapter(unsigned chapter, unsigned verse, unsigned target_word, const ReadingView* reading_view) {'))
    last = source.index('    /* Initialize an empty file', first)
    source = source[:first] + '''    FileClose();
    FileDelete(READER_FILE);
    unsigned capacity = ChapterCapacity() + 512;
    if(FileCreate(0, "Chapter", capacity, capacity) != READER_FILE ||
        FileOpen(READER_FILE, FILE_OPEN_REWIND) < 0) goto failed;
''' + source[last:]
    source = source.replace('!DecodeChapterToFile() || !MoveChapterGapToEnd()', '!DecodeChapterToFile()')
    return source


def prepare(variant):
    for version in ('kjv', 'nkjv'):
        if not (APP/'build/data'/version/'container.bin').exists():
            subprocess.run(['make', '-s', '-C', str(APP), 'VERSION='+version.upper(), 'build/data/'+version+'/Navigation.h'], check=True)
    app = BUILD / variant / 'app'
    app.mkdir(parents=True, exist_ok=True)
    for pattern in ('*.c', '*.h', '*.S', '*.py'):
        for source in APP.glob(pattern): shutil.copy2(source, app / source.name)
    (app / 'build').mkdir(exist_ok=True)
    for name, target in [('upstream', APP/'upstream'), ('build/generated', APP/'build/generated')]:
        link = app/name
        if not link.exists(): link.symlink_to(target, target_is_directory=True)
    make = (APP/'Makefile').read_text().replace('include ../../../../Makefile.common', 'include '+str(ROOT/'Makefile.common'))
    make = make.replace('../../../../research/fonts/superscript-3x5.json', str(ROOT/'research/fonts/superscript-3x5.json'))
    make = re.sub(r'\$\(DATA_FILES\) &:.*?\n\tpython3 build_data.py[^\n]*\n', '# Immutable production data plus the research bound extension.\n', make, flags=re.S)
    (app/'Makefile').write_text(make)
    source = (APP/'BibleWise.c').read_text()
    source = source.replace('"../../tests/mame/asneo/BibleWiseProbe.h"', '"'+str(ROOT/'tests/mame/asneo/BibleWiseProbe.h')+'"')
    source = source.replace('static void CopySelectedVerses(void) {\n', 'static void CopySelectedVerses(void) {\n    ReaderProbeSet(phase, 900);\n')
    source = source.replace('    ShowStatusMessage("Copied", 2000);', '    ReaderProbeSet(phase, 901);\n    ShowStatusMessage("Copied", 2000);')
    if variant in ('native-copy', 'combined'):
        first = source.index('static void CopySelectedVerses(void) {')
        last = source.index('static bool AcceptInput(', first)
        source = source[:first] + (HERE/'native-copy.c').read_text() + '\n' + source[last:]
    if variant == 'fresh-file':
        first = source.index('    FileClose();\n', source.index('static void OpenChapter(unsigned chapter, unsigned verse, unsigned target_word, const ReadingView* reading_view) {'))
        last = source.index('    /* Initialize an empty file', first)
        source = source[:first]+'''    FileClose();
    FileDelete(READER_FILE);
    if(FileCreate(0, "Chapter", 0, 512) != READER_FILE ||
        FileOpen(READER_FILE, FILE_OPEN_REWIND) < 0) goto failed;
'''+source[last:]
    source = source.replace('    if(FileEraseCurrent() < 0) goto failed;', '''    ReaderProbeSet(phase, 910);
    int erased = FileEraseCurrent();
    ReaderProbeSet(phase, 911);
    if(erased < 0) goto failed;''')
    if variant in ('direct-decode', 'combined'):
        source = direct_decode(source)
        (app/'Decoder.c').write_text((APP/'Decoder.c').read_text().replace('KJVHUF02', 'KJVHUF03'))
    (app/'BibleWise.c').write_text(source)
    for version in ('KJV', 'NKJV'):
        data = app/'build/data'/version.lower(); data.mkdir(parents=True, exist_ok=True)
        for item in (APP/'build/data'/version.lower()).iterdir():
            target = data/item.name
            if item.name == 'container.bin' and variant in ('direct-decode', 'combined'):
                image = bytearray(item.read_bytes())
                bound_path = BUILD/('bounds-'+version+'.json')
                dependencies = [HERE/'bounds.py', APP/'BibleWise.c', APP/'Formatting.h', APP/'format_data.py', APP/'convert_source.py',
                    APP/'upstream/data/books.json', APP/'upstream/data'/version.lower()/(version.lower()+'.json')]
                signature = hashlib.sha256(b''.join(path.read_bytes() for path in dependencies)).hexdigest()
                cached = json.loads(bound_path.read_text()) if bound_path.exists() else None
                if isinstance(cached, dict) and cached.get('signature') == signature:
                    bounds = cached['bounds']
                else:
                    bounds = chapter_bounds(version)
                    bound_path.write_text(json.dumps(dict(signature=signature, bounds=bounds)))
                offset = 64 + sum(struct.unpack_from('>III', image, 8)[::2]) + struct.unpack_from('>I', image, 20)[0] + 4*struct.unpack_from('>I', image, 32)[0]
                # Keep the source length in low16; use formerly zero high16 for
                # a bound. HUF03 rejects accidental use by a HUF02 consumer.
                image[:8] = b'KJVHUF03'
                for chapter, bound in enumerate(bounds):
                    raw = struct.unpack_from('>I', image, offset+16*chapter+12)[0]
                    assert raw < 65536
                    struct.pack_into('>I', image, offset+16*chapter+12, (bound<<16)|raw)
                target.write_bytes(image)
            elif not target.exists(): target.symlink_to(item)
        if variant in ('direct-decode','combined'):
            report = json.loads((APP/'build/data'/version.lower()/'results.json').read_text())
            digest = hashlib.sha256((data/'container.bin').read_bytes()).hexdigest()
            report.update(container_format='KJVHUF03', capacity_bound_max=max(bounds), research_variant=variant, sha256=digest)
            report['resource_sha256']['container.bin'] = digest
            report_path = data/'results.json'
            if report_path.is_symlink(): report_path.unlink()
            report_path.write_text(json.dumps(report, indent=2)+'\n')
    return app


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('variant', choices=('baseline','fresh-file','direct-decode','native-copy','combined'))
    p.add_argument('--build', action='store_true')
    args = p.parse_args();app=prepare(args.variant)
    if args.build:
        for version in ('KJV','NKJV'):
            with(app/('release-'+version+'.log')).open('w')as log:
                subprocess.run(['make','-s','-C',str(app),'VERSION='+version],stdout=log,stderr=subprocess.STDOUT,check=True)
            image=app/'build'/version/('BibleWise'+(''if version=='KJV'else'-'+version)+'.OS3KApp')
            print(args.variant,version,struct.unpack_from('>II',image.read_bytes(),4),flush=True)
    else: print(app)


if __name__=='__main__':main()
