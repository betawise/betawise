# Vendor uses of 08, 16 and 90

This follow-up scans Neo 3.21 ROM and the 27 vendor SmartApplets in the existing
vendor-image inventory. Community `NeoFonts/` applets are excluded.

Reproduce from the repository root:

```
python3 research/bible-reader/font-specimens/audit_vendor_glyph_usage.py
```

[Recorded evidence and search candidates (archived)](../../../font-archive/README.md#useful-pages-after-extraction) includes source
paths, exact help bytes, keyboard descriptor outputs, and candidate immediate
constants/text runs. Disassembly of resource data can produce false instructions;
constants and byte occurrences are not counted as glyph use without context.
The text-run search is a heuristic, not a complete string-resource parser.
Compressed strings, dynamic text and indirect/table-based consumers can remain.

## Confirmed dot-above use

AlphaWord Plus contains the literal help line at file offset `0x17C76`:

```
08 (superscript dot): option-H
```

Here `08` denotes the literal native byte, not the two printed digits.
The containing International Characters help string ends at `0x17CBD`.

The ROM's TranslateKeyToChar keyboard pointer table at `0x44B526` resolves key
`0x11` (H) to descriptor `0x447C01`, whose bytes are `68 48 30 08 00`:
ordinary h/H and Option-modifier group 30 → output 08. The ROM routine at
`0x423C7C` selects this output byte; this is direct character entry, not a dead
accent. No live descriptor output in the 80-entry table is 16 or 90. A descriptor
with first byte zero is an unmapped key: the ROM returns before inspecting its
later bytes, so those bytes must not be mistaken for another output table.

The five dead-accent descriptors instead output spacing bytes B4, 60, 5E, A8
and 7E. Dot-above is not among them. See [the vendor review](vendor-glyph-review.md).
Thus U+02D9 DOT ABOVE remains appropriate; no evidence supports U+0307 as its
native text interpretation.

## 16

No verified text/glyph-producing use was found in this static audit beyond the
font bitmaps. Literal 16 values occur in code, but include unrelated quantities:
AlphaWord's comparison at file offset `0xF1A` is against a raw key code in a
modifier/key-event path (16 is physical D), not the return-arrow character.
Other immediate occurrences include lengths, resource indices and protocol
state. These are not evidence of a displayed return glyph.

The already executed native text-scanner probe independently establishes that
16 is an ordinary one-byte glyph, whereas 0D is carriage return. See
[record framing](../../../syscalls/text/token-records.md). That makes 16 a
usable printable return-arrow slot, but does not establish why the vendor added
it or identify a stock UI that emits it. Its U+21B5 alias is based on the vendor
font comparison, not a newly discovered call site.

## 90

No verified use as text/grave artwork was found beyond the font resources.
It is not an output of the standard keyboard character table, and the grave
accent fallback emits 60.

Several apparent uses have other meanings. At AlphaWord file offset `0x589C`,
`pea 0x90` passes resource index 90 to the string lookup routine at `0x64BE`.
That routine indexes the longword table at `0x14374`; entry 90 resolves to
`0x15B06`, the string `Beamer sending is disabled.` It is not a character draw.
ROM `0x412FFA` writes 90 in the flash identification command sequence (AA/55/90),
also unrelated to text. AlphaWord's 90 comparisons in its byte-protocol parser
at `0x832E` and `0x8C30` likewise do not demonstrate a grave glyph consumer.

No verified consumer found is not proof of global non-use. The mapping remains
a practical glyph correspondence to U+0060, supported by vendor Small's exact
60/90 equality and the other vendor grave-shaped artwork.

## Existing identity choices

The shared glyph map uses U+21B5 for both 0D and 16, U+25AF for 17, and U+221A
for 18. Font identity does not replace the text engine's CR/control semantics.
No map or bitmap changes were needed for this usage audit.
