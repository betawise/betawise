"""Conservative native-file bounds, independent of installed glyph widths."""
from itertools import groupby
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent / 'reference'))
from convert_source import encode_native
from format_data import read_formatting


def chapter_bounds(version):
    source = read_formatting(version.lower(), ROOT / 'applets/BibleWise/upstream')
    results = []
    for atoms, headings, raw in zip(source['atoms'], source['headings'], source['blocks']):
        verses = raw.count(b'\n')
        size = sum(12 + len(str(verse)) for verse in range(1, verses + 1))
        for atom in atoms:
            text = encode_native(atom['text'])
            assert all(32 <= c <= 126 or 0x91 <= c <= 0x94 for c in text), atom['text']
            style, layout = atom['style'], atom['layout']
            # A separator and, when requested, a paragraph CR. Indentation is
            # literal spaces. Each active face run needs at most two 3B records.
            size += len(text) + 1 + bool(layout)
            size += 4 if layout & 8 else 2 if layout & 4 else 0
            if style & 4:
                runs = sum(1 for _ in groupby(97 <= c <= 122 for c in text))
                size += 6 * runs
            elif style & 3:
                size += 6
            # Width is 252px. Even a zero-width space uses divisor 1; reserve
            # 252 bytes for each aligned line regardless of installed font.
            if layout & (16 | 32):
                size += 252
        for _, _, heading in headings:
            # Visibility wrappers 6B, bold start/end 6B, two possible CRs.
            size += len(encode_native(heading)) + 14
        assert 0 < size <= 65500, size
        results.append(size)
    assert len(results) == 1189
    return results
