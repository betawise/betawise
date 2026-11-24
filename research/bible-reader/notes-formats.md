# Deferred Bible notes: standalone interchange formats

Notes are still deferred; no format has been selected. JSON Lines is not an
agreed format. USFM/USX/USJ carries scripture documents with embedded notes,
which is different from a separate personal notebook.

## OSIS commentary: the clearest established standalone model

[CrossWire's OSIS commentary documentation](https://wiki.crosswire.org/OSIS_Commentaries)
explicitly describes commentary text associated with scripture references, rather
than requiring the original verse text to be duplicated. A note uses a section
with `annotateType="commentary"` and `annotateRef="John.3.16"`; a range is
`John.3.16-John.3.18`. Multiple references are also supported.

A fragment inside the standard OSIS document/header is:

```xml
<div type="section" annotateType="commentary" annotateRef="John.3.16">
  <p>My note about this verse.</p>
</div>
```

This is a proposed representation, not an implemented or schema-validated notes
writer. A complete file needs the OSIS root/header, XML escaping and explicit
reference/versification metadata. It can be read directly as XML on a computer;
SWORD can import it using osis2mod. That import builds a compiled module, not a
requirement for simply reading the original file. It is the best researched
candidate when established standalone commentary interchange is the priority.

## Door43 Study Notes TSV: a lighter text alternative

[unfoldingWord/Door43's Parascriptural TSV v2 specification](https://forum.door43.org/t/parascriptural-tab-separated-value-format-specification-v2/870)
includes a distinct **Study Notes (SN)** resource, separate from the Bible.
It uses a file per book, e.g. `sn_JHN.tsv`, with seven columns:

`Reference`, `ID`, `Tags`, `SupportReference`, `Quote`, `Occurrence`, `Note`.

Notes contain Markdown or plain text. References include chapter/verse and
verse ranges. Newlines, tabs and backslashes inside fields are escaped. This is
more compact and simpler to generate than XML; ordinary text/spreadsheet tools
can open the exported file. However, it is designed around the Door43 content
ecosystem, including original-language quotation/occurrence fields and resource
metadata, rather than being a universally supported personal notebook format.
Before selecting it, validate how general verse notes and translation identity
should be represented and which computer Bible applications actually import SN.
A subset/custom variation must not be presented as conforming without validation.

## Formats to avoid adopting blindly

- [SWORD RawFiles personal commentary](https://wiki.crosswire.org/DevTools:JSword/Personal_Commentary)
  is an actual editable personal-commentary storage format, but needs index/data
  files and a separate file per note. CrossWire recommends using its API rather
  than depending on binary module internals; it is a poor direct Neo interchange
  choice. See [SWORD file formats](https://wiki.crosswire.org/File_Formats).
- [IMP](https://wiki.crosswire.org/DevTools:IMP_Format) offers simple reference
  headers and multiline text, but CrossWire discourages it for commentary module
  submissions and prefers validated OSIS. Simplicity alone does not make it the
  best compatibility choice.

No device-side notes work is included in the layout/codec comparison. File
transfer encoding and preservation of tabs/newlines remain to be verified when
notes are implemented.
