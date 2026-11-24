# Native soft-hyphen experiment

Run `python3 betawise/research/bible-reader/soft-hyphen/check.py` from the
workspace root on fresh output storage. It builds a separate disposable probe
applet, not a BibleWise option. The six cases use the original Neo 3.21 editor
and fixed ROM 6x16 font, widths 254 and 72 pixels, and explicit expected text.
The production Bible representation is unchanged.

| Input | Wide display / normalized bytes | Narrow display / normalized bytes |
|---|---|---|
| abcdefghij + byte AD + klmnop | abcdefghij-klmnop / byte 2D | abcdefghij- then klmnop / byte AD |
| Ordinary ASCII hyphen | Identical | Identical |
| abcdefghijklmnop | One uninterrupted word | abcdefghijkl then mnop / inserted byte 8F |

Byte AD is a cached ordinary hyphen, not a discretionary soft hyphen. It remains
visible when no break is needed. Byte 8F lets the editor split an overlong word
without displaying a hyphen. This experiment does not establish that no other
native mechanism could implement discretionary hyphenation; it rules out simply
injecting AD into the chapter file. No UTF-8 bytes are introduced.

Final evidence is under .research-work/bible-compression/native-soft-hyphen-v4:
six complete exact 264x65 pixel comparisons, original font glyphs, file bytes
excluding the editor gap, controller records, cursor hide/restore observations,
three stable RAM samples, source snapshot/hashes and logs.

Earlier failed characterizations are retained. A width argument of 36 is legacy
console columns on Neo and expands to 216 pixels; the corrected probe uses 72.
Other characterization revisions corrected reading from the editor gap and
including an inserted 8F byte when reading the entire encoded text. Expected
bitmaps are explicitly authored from literal strings and original font bytes,
never generated from a failing capture.
