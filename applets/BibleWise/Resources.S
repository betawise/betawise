/* Paths are supplied by the Makefile for the selected translation. */
.section .rodata.bible.text,"a"
.balign 2
.global BibleData, BibleDataEnd
BibleData:
.incbin BIBLE_CONTAINER_PATH
BibleDataEnd:

.section .rodata.bible.search,"a"
.balign 2
.global BibleSearchData, BibleSearchDataEnd
BibleSearchData:
.incbin BIBLE_INDEX_PATH
BibleSearchDataEnd:

.section .rodata.bible.verses,"a"
.balign 2
.global BibleVerseCounts
BibleVerseCounts:
.incbin BIBLE_VERSES_PATH

.section .rodata.bible.pruning,"a"
.balign 2
.global BibleGrammarSummary
BibleGrammarSummary:
.incbin BIBLE_SUMMARIES_PATH

.section .note.GNU-stack,"",@progbits
