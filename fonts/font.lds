/* Font providers dispatch directly to C. Only runtime descriptors use A5 RAM. */
OUTPUT_FORMAT(elf32-m68k)
ENTRY(Os3kEntry)
MEMORY {
    rom (rx) : ORIGIN = 0, LENGTH = 16M
    ram (rw) : ORIGIN = 0x80000000, LENGTH = 16M
}
SECTIONS {
    os3k_header (READONLY) : { KEEP(*(os3k_header)) } > rom
    .rom (READONLY) : {
        /* Put the regular face before the handler. Its start and the starts
         * of the remaining faces then fit GCC's signed PC16 references, even
         * when the complete font package is larger than 32 KiB. The header
         * stays at offset zero. The linker checks every actual displacement. */
        *(.rodata.GLYPHS .rodata.GLYPH_DATA .rodata.GLYPH_OFFSETS .rodata.GLYPH_WIDTHS)
        *(.text .text.*)
        *(.rodata.font_name)
        *(.rodata .rodata.*)
        . = ALIGN(2);
        KEEP(*(os3k_footer))
    } > rom
    .font.ram (NOLOAD) : { KEEP(*(.font.ram)) } > ram
    .unexpected : { *(.got* .data* .bss* COMMON) } > ram
    __os3k_rom_size = ADDR(.rom) + SIZEOF(.rom);
    __os3k_ram_size = SIZEOF(.font.ram);
    /DISCARD/ : { *(.comment .note* .eh_frame*) }
}
ASSERT(SIZEOF(os3k_header) == 0x94, "font header must be 148 bytes")
ASSERT(SIZEOF(.unexpected) == 0, "font must not contain GOT or implicit writable data")
ASSERT(__os3k_ram_size == 16 || __os3k_ram_size == 80, "only font descriptors may consume RAM")
