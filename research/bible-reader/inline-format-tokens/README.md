# In-stream Huffman formatting terminals (NKJV)

Historical host-only research against HUF03 BibleWise data. Inline formatting
is now production; see [adoption measurements](adoption.md) for the actual
HUF04 implementation, release sizes and MAME timings. Source: the pinned bible-data NKJV JSON, SHA-256
`e031c595ee156596944afe315ab06b039f210e20e1bb7b3fe4b1a2240cb969cc`.

The experiment preserves precisely the current body text, smart quotes,
headings, italics, bold, small caps and all paragraph/line/indent/alignment flags.
Upstream red-letter flags are excluded, matching production. No footnotes,
cross-references or additional source annotations are introduced.

| Representation | Text + formatting | Search index | All reader resources | Difference |
|---|---:|---:|---:|---:|
| Current text plus two sidecars | 1,142,336 | 268,969 | 1,419,827 | baseline |
| Separate style/layout Huffman terminals | 1,129,127 | 268,988 | 1,406,637 | −13,190 |
| Combined style/layout Huffman terminals | 1,127,006 | 269,000 | 1,404,528 | **−15,299** |

All numbers are bytes. All-resources includes text/container, full search index,
grammar pruning and verse counts, plus both sidecars for the baseline. It excludes
application code and fonts. The best result saves **14.94 KiB / 1.08%** of the
baseline resources. The text container grows 42,998 bytes, replacing 58,328 bytes
of sidecars; 31 additional search-normalization bytes reduce the net saving to
15,299. Two-byte resource alignment adds the same one byte to both compared totals.

## Encoding

Use the production tokenizer, front dictionary, 2,048-rule phrase grammar,
canonical Huffman model, eight-bit lookup table, word cache and independently
padded chapter streams. Retain the existing text dictionary IDs, adding empty
nonword dictionary entries for control terminals. The container includes a small
control dispatch table; no formatting sidecar or learned word-default table is
needed. Models are trained independently for each representation.

A style terminal changes the current source style. A layout terminal specifies
an override for the next body atom. The combined variant uses a terminal for
`(style, next layout)` whenever either changes. Its 18 control terminals cover
80,771 occurrences. Text, whitespace and heading markers remain unchanged.
Formatting controls precede the preceding separator so that a text terminal
such as ` love` remains intact. Grammar rules may include control terminals;
their expansion preserves the control order. The existing search postings remain
identical; only the per-terminal normalization table grows. Control entries are
nonwords with zero word/verse contribution in grammar summaries.

The third `explicit` run checks a zero verse-layout default. NKJV's current
translation default is already zero, so it is byte-identical to the separate
variant. There is no claimed additional gain from that duplicate control.

## Exact decompression size

Each control expands to a fixed four-byte intermediate record:
`0x02, kind, style, layout`. The fourth word of each 16-byte chapter record holds
its exact expanded markup length. The combined variant expands to 4,436,695 bytes
in total, at most 15,292 bytes for one chapter. These records are research bytecode,
not native editor formatting records.

**This establishes exact intermediate markup size, not exact final native
editor-file size with the current renderer.** The latter still depends on
font-width-based alignment padding and whether the installed font supports the
small-caps face. Superscript records and face/provenance transitions also need
rendering. Direct expansion into the editor file would require a further native
record encoding experiment or a renderer whose output lengths are fixed. This
experiment does not claim to eliminate that renderer or the current capacity
bound merely by placing semantic tokens in the Huffman stream.

## Validation

Every variant round-trips all 1,189 chapters, 768,823 body atoms and 2,992 headings,
checking every atom's source text, style and layout. An additional reader decodes
the serialized front dictionary, dispatch table, Huffman model, grammar and
chapter records from the emitted files; it checks the same source oracle and the
exact expanded-size fields. Search checks compare all canonical records, all
postings and every existing normalization ID against the production index.

There is no MAME runtime port or speed/decoder-ROM claim in this experiment.
The current production decoder will not load the `NKJVIF01` research container.
An initial over-specified run included upstream red-letter flags; its artifacts
remain in ignored `build/with-redletter/` and are excluded from these results.

From the betawise directory:

```sh
python3 research/bible-reader/inline-format-tokens/compare.py
python3 research/bible-reader/inline-format-tokens/verify_index.py research/bible-reader/inline-format-tokens/build/production-typography
python3 research/bible-reader/inline-format-tokens/verify_container.py research/bible-reader/inline-format-tokens/build/production-typography
```

Generated containers and intermediate records remain under ignored `build/`.
`results.json` retains the accepted counts, component sizes and source hashes.
`finalize.py` only migrates the first encoder run's chapter length fields to the
explicit intermediate-bytecode lengths; fresh builds already write them directly.

## Native verse-label extension

[Native superscript marker measurements](verse-markers.md) include the actual
superscript bytes in the Huffman stream and remove the separate chapter-count
table. The best variant totals 1,449,947 resource bytes: 30,120 more than current
production, or 45,419 more than this semantic-only experiment.

## Archived sidecar implementation

`sidecar-reference/` preserves the former application and build encoders;
`prepare_sidecar.py` reconstructs a buildable comparison without restoring unused
code to production. The host comparisons above now read that frozen baseline.
