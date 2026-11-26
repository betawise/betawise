"""Build the marker-search parser from the same tested block scanner."""
from fast_boundaries import generate as generate_fast


def generate(here):
    text=generate_fast(here).read_text()
    text=text.replace('static unsigned ScanBoundary(unsigned first, unsigned target, bool by_position) {',
        'static unsigned ParseBoundary(unsigned first, unsigned target, bool by_position, unsigned start) {')
    text=text.replace('    unsigned verse = first - 1, heading = 0;',
        '    stream.position = stream.loaded = start;\n    unsigned verse = first - 1, heading = 0;')
    text=text.replace('    ReaderProbeSet(phase, 710);\n','').replace('    ReaderProbeSet(phase, 711);\n','')
    text=text[:text.index('static const VerseBounds* LookupBoundary')]
    text+='\n#include "'+str(here/'marker_seek.h')+'"\n'
    output=here/'build/marker-boundaries.h'
    output.write_text(text)
    return output
