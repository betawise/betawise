# Small-cap encoding research summary

Earlier searches tried direct bit transforms on native character positions,
including masked XORs, shifts and permutations. Native positions and reserved
editor controls constrained those schemes; moving Regular into private slots
allowed a table-free solution for all 62 letter forms in three styles.

The adopted arithmetic encoder, reverse decoder and exhaustive tests replace
these experimental programs. See the [current summary](../../fonts/smallcaps/README.md#encoding-research-summary)
and [shared charset](../../../os3k/charsets/README.md#private-small-capitals).
