.section .rodata.bible,"a"
.balign 2
.global BibleData
BibleData:
.incbin "bible.bin"
.global BibleDataEnd
BibleDataEnd:
.section .rodata.bible_seek,"a"
.balign 2
.global BibleSeekData
BibleSeekData:
.incbin "seek.bin"
.global BibleSeekDataEnd
BibleSeekDataEnd:
.section .note.GNU-stack,"",@progbits
