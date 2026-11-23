# Rhyming dictionary feasibility

A separate pronunciation lexicon is the clearest implementation path. The
verified Thesaurus API provides semantic groups, related terms and antonyms;
SpellCheck provides spelling services. Neither verified interface returns
pronunciation. The CW dictionaries expose proprietary blobs: their complete
contents remain undecoded, so this research does **not** establish that those
blobs contain no phonetic information.

## Proposed behavior

For a perfect-rhyme search, index the phoneme suffix from the final stressed vowel
through the end of the pronunciation. Retain alternate pronunciations and union
their results. Exclude the input spelling, deduplicate output spellings, and make
homophone inclusion a deliberate product choice. Accent and pronunciation
variants affect results; spelling suffixes alone are insufficient (`rough` and
`tough` rhyme, `rough` and `through` do not; `love` and `move` do not).

[CMUdict](https://github.com/cmusphinx/cmudict) is a suitable candidate source for
an English prototype. Its [phoneme symbols](https://github.com/cmusphinx/cmudict/blob/master/cmudict.symbols)
retain vowel stress markers 0/1/2; preserve those during the build. The
[CMUSphinx dictionary tutorial](https://cmusphinx.github.io/wiki/tutorialdict/)
describes phonetic entries and alternate pronunciations. Ship the required
copyright, license and disclaimer notices from the
[dataset license](https://github.com/cmusphinx/cmudict/blob/master/LICENSE).

A practical offline build can assign word IDs, front-code sorted spelling blocks,
map words to one or more rhyme-key IDs, and store each rhyme group's word IDs as
delta-coded postings. Runtime can binary-search block starts, decode one small
spelling block, and stream a paginated result list. Keep bulk data in flash rather
than copying the lexicon to applet RAM. This architecture has not yet been
implemented or qualified on the Neo.

## Measured storage baseline, with an explicit limitation

`measure-rhyme.py` measures a local PocketSphinx CMUdict-derived corpus. The local
file has **no stress markers**. Its last-vowel grouping is useful for measuring a
candidate encoding, but is **not** a correct implementation of stressed-rhyme
search: it incorrectly groups `station` with `pigeon`. Independently specified
stress-bearing fixtures verify that the proposed stressed key groups `station`
with `nation` and separates `pigeon`.

| Measured input/output | Value |
|---|---:|
| Input bytes | 3,272,051 |
| Pronunciation rows | 134,723 |
| Unique spellings | 125,945 |
| Last-vowel keys | 1,403 |
| Front-coded words | 582,351 bytes |
| Word-to-key references | 383,197 bytes |
| Delta-coded postings | 172,083 bytes |
| Directories, key pool and header | 61,379 bytes |
| Total candidate encoding | **1,199,010 bytes** |

This total excludes executable code and UI. It is a storage baseline, not a
claim that a production perfect-rhyme dictionary fits that size. A full
stress-preserving source will produce different groups and must be remeasured.
Flash packaging, available device space, build integration, runtime RAM, search
latency and regional pronunciation behavior remain acceptance work.

Reproduce from the workspace root:

```sh
python3 betawise/research/dictionaries/measure-rhyme.py /tmp/rhyme-layout
```

The default source is
`/usr/share/pocketsphinx/model/en-us/cmudict-en-us.dict`; SHA-256
`9de99dd2a24b63c653c1c30ab39388d05185cae36d0875f15c319b4ad6dc43af`.
Use `--help` for a source override. Outputs include encoded components and a
JSON report; the corpus and generated binary components are not checked in.
The checked-in [measurement report](rhyme-measurement.json) records provenance,
examples, the known false positive and the explicit accuracy limitation.

Before an applet implementation: build with stress retained, remeasure, decide
homophone/variant policy, then qualify bounded-memory lookup and deterministic
on-device result text. Existing synonym services can be offered separately;
their related-word lists should not be presented as rhyming results.
