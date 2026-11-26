#!/usr/bin/env python3
"""Compare the candidate parser with the accepted parser on every captured offset."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
accepted = (HERE / 'reference/ChapterPositions.h').read_text()
first = accepted.index('static unsigned ParseBoundary(')
last = accepted.index('/* Seek existing numbered records;', first)
marker = accepted[accepted.index('static unsigned BoundaryMarker('):first]
reference = (marker + accepted[first:last]).replace('ParseBoundary(', 'ReferenceParseBoundary(').replace('BoundaryMarker(', 'ReferenceBoundaryMarker(')
script = (HERE / 'check_final_binary.py').read_text()
script = script.replace("header=root/'applets/BibleWise/ChapterPositions.h'",
                        "header=folder/'baseline-simpler-parser/app/ChapterPositions.h'")
# Insert the old linear parser unchanged; it shares only the unchanged marker
# reader/types. Its result is saved before calling the candidate implementation.
script = script.replace('int main(int argc,char**argv){', reference.replace('\\', '\\\\') + '\nint main(int argc,char**argv){')
script = script.replace('want=ParseBoundary(', 'want=ReferenceParseBoundary(')
marker_checks = '''for(unsigned p=0;p<g_chapter_file_bytes;++p){
 BoundaryStream s={0};s.base=data;s.position=p;BoundaryFill(&s);
 unsigned old_length=0,new_length=0;
 unsigned old_number=ReferenceBoundaryMarker(&s,&old_length),new_number=BoundaryMarker(&s,&new_length);
 assert(old_number==new_number && (!old_number || old_length==new_length));
 }
'''
script = script.replace(' for(unsigned mode=0;', marker_checks+' for(unsigned mode=0;')
exec(compile(script, str(HERE / 'check_final_binary.py'), 'exec'),
     {'__name__': '__main__', '__file__': str(HERE / 'check_final_binary.py')})
