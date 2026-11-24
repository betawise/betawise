"""Explicit device-text conversion, applied before tokenization/compression."""
REPLACEMENTS = {
    '’': "'", '‘': "'", '“': '"', '”': '"',
    '–': '-', '—': '-', '―': '-', '…': '...',
    '\u2006': ' ', '\u2009': ' ', 'á': 'a', 'í': 'i',
    '½': '1/2', '¾': '3/4', '⅓': '1/3', '¼': '1/4', '⅔': '2/3',
    'æ': 'ae', 'Æ': 'AE', 'é': 'e', 'Ē': 'E', '´': "'",
}


def convert(text):
    out = ''.join((' ' if c in '½¾⅓¼⅔' and i and text[i-1].isdigit() else '') + REPLACEMENTS.get(c, c) for i,c in enumerate(text))
    out.encode('ascii')  # Unknown characters fail; never drop them silently.
    return out
