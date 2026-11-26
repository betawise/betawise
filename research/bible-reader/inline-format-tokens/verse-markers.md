# Native superscript verse markers in the Huffman stream

Host-only NKJV extension to the semantic-formatting experiment. Production is
unchanged. This stores the exact visible, protected native superscript records
inside the compressed stream; it does not synthesize the digits at runtime.

The previous experiment did not have an index entry for every verse. Its
`verses.bin` held **one uint16 verse count per chapter**, totaling 2,378 bytes.
Verse boundaries remained newline tokens, from which the writer generated the
superscript labels. Production already finds displayed verses from the markers
in its decoded file, rather than keeping a per-verse offset index.

| Representation | All resources (bytes) | vs production | vs semantic-only inline |
|---|---:|---:|---:|
| Current production text + sidecars + chapter counts | 1,419,827 | — | — |
| Previous combined semantic tokens + chapter counts | 1,404,528 | −15,299 | — |
| Whole native verse marker as one terminal | **1,449,947** | **+30,120** | **+45,419** |
| Native open/close terminals plus digit tokens | 1,454,486 | +34,659 | +49,958 |

Totals include the text container, dictionary, control expansions, model, cache,
full search index and grammar summaries. Neither new variant has `verses.bin`,
style or layout sidecars. They exclude app code and fonts, which have not been
ported or measured. These are file-byte totals before linker alignment; alignment
adds one byte to production and whole-marker totals, so their delta is unchanged.

## Representation

For verse 16 the literal expansion is:

```text
B1 0C B1   B1 02 B1   31 36   B2 02 B2   B2 0C B2
face on    protected   "16"    protected off  face off
```

There is no following space. This matches the existing visible verse-number
writer byte-for-byte. Hiding numbers remains a display operation on the flags.

The whole-marker variant adds 176 literal terminal expansions for labels 1–176,
plus the 18 semantic formatting controls from the earlier combined prototype.
Its dictionary/dispatch region stores the actual marker bytes. The component
variant instead uses two six-byte expansions and existing ASCII digit terminals.
Models and the 2,048-rule phrase grammar are trained separately for both variants.

Both variants produce identical expanded markup: **4,861,644 bytes**, at most
**17,824 bytes per chapter**. The existing chapter record's fourth uint32 now
packs `verse_count << 16 | expanded_size`. This reuses spare bits without growing
the record and preserves immediate reference validation without another table.
The count is derived from the inline labels, not a separately stored number list
or per-verse offset index.

Newline source boundaries remain for the existing search/semantic formatting
contract. The native verse labels are additional nonword terminals, with no
search word contribution. Canonical search records, postings and existing word
normalization IDs are unchanged. The normalization table grows to cover the new
nonword terminals, and that cost is included above.

This is still a **hybrid research stream**: verse labels expand to native editor
bytes, while body typography/layout retains the earlier semantic controls.
It does not measure compression of a fully precompiled native chapter file or
claim that the remaining renderer can yet be deleted. Alignment-to-spaces is not
performed in this host experiment. No renderer-code savings or decode timing
claims are included in the resource totals.

## Verification and reproduction

The literal marker definitions are checked against a host build of the actual
production `BufferVerseNumber()` for all labels 1–176. Both encoder and serialized
container reader check **all 31,102 verse labels**, their order, chapter counts,
exact expanded lengths, all 1,189 chapter texts, 768,823 body atoms and 2,992
headings. Every body atom retains its style/layout flags and source case.
The index verifier checks all canonical records, postings, and normalization IDs.

From the betawise directory:

```sh
python3 research/bible-reader/inline-format-tokens/compare.py --modes verse-whole verse-parts --output research/bible-reader/inline-format-tokens/build/native-verse-markers
python3 research/bible-reader/inline-format-tokens/check_native_markers.py --output research/bible-reader/inline-format-tokens/build/native-verse-markers
python3 research/bible-reader/inline-format-tokens/verify_index.py research/bible-reader/inline-format-tokens/build/native-verse-markers
python3 research/bible-reader/inline-format-tokens/verify_container.py research/bible-reader/inline-format-tokens/build/native-verse-markers
```

`verse-results.json` preserves accepted sizes, hashes and verification results;
derived binary artifacts remain under ignored `build/native-verse-markers/`.
