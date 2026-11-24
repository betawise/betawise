.section .rodata.bible.text,"a"
.balign 2
.global BibleData,BibleDataEnd
BibleData:
.incbin "bible.bin"
BibleDataEnd:
.balign 2
.section .rodata.bible.search,"a"
.balign 2
.global BibleSearchData,BibleSearchDataEnd
BibleSearchData:
.incbin "search.bin"
BibleSearchDataEnd:
.balign 2
.section .rodata.bible.verses,"a"
.balign 2
.global BibleVerseCounts
BibleVerseCounts:
.incbin "verses.bin"
.balign 2
.section .rodata.bible.pruning,"a"
.balign 2
.global BibleGrammarSummary
BibleGrammarSummary:
.incbin "pruning.bin"
.section .rodata.bible.wide,"a"
.balign 2
.global BibleFastHuffmanTable
BibleFastHuffmanTable:
.incbin "wide.bin"
.section .rodata.bible.verseboost,"a"
.balign 2
.global BibleVerseBoost,BibleVerseBoostEnd
BibleVerseBoost:
.incbin "verse-boost.bin"
BibleVerseBoostEnd:
.section .note.GNU-stack,"",@progbits
