"""Combine the direct parser with an optional synthesized marker search."""


def generate(here, bmh=False):
    text=(here/'direct_boundaries.h').read_text()
    marker='static unsigned ReconstructBinaryBoundary'
    code=(here/'direct_marker_seek.h').read_text()
    if bmh: code='#define MARKER_BMH 1\n'+code
    text=text.replace(marker,code+'\n'+marker)
    text=text.replace('NumberedRecord anchor = FindEarlierRecord(target, by_position, base);',
        'NumberedRecord anchor = by_position ? FindEarlierRecord(target, true, base) : FindPatternAnchor(target, base);')
    path=here/'build'/('direct-marker-bmh.h' if bmh else 'direct-marker.h')
    path.write_text(text)
    return path
