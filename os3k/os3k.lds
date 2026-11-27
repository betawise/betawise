/* The ELF is linked at flash-relative addresses and tagged RAM addresses.
 * objcopy uses the LMAs to lay out the flat OS3K image in this order:
 * header, zero-terminated RAM fixup offsets, initial GOT/data, code/rodata,
 * and footer. The NOBITS section contributes only to the RAM allocation.
 */
OUTPUT_FORMAT(elf32-m68k)
ENTRY(Os3kEntry)
PROVIDE(__os3k_direct_entry = 0);

MEMORY
{
    rom (rx) : ORIGIN = 0, LENGTH = 16M
    ram (rw) : ORIGIN = 0x80000000, LENGTH = 16M
}

SECTIONS
{
    os3k_header : {
        KEEP(*(os3k_header))
    } > rom

    .data.reloc : {
        . += __os3k_reloc_size * 4;
        LONG(0)
    } > rom

    .rom.ram : {
        *(.got.plt)
        *(.got .got.*)
        __os3k_got_end = .;
        *(.data .data.*)
        . = ALIGN(2);
    } > ram AT > rom

    .rom : {
        /* Large font packages need tables on both sides of their handler. */
        *FontApplet.o(.rodata.GLYPHS .rodata.GLYPH_DATA .rodata.GLYPH_OFFSETS .rodata.GLYPH_WIDTHS)
        KEEP(*(.text.Os3kEntry))
        *(.text .text.*)
        *(.rodata .rodata.*)
        . = ALIGN(2);
        KEEP(*(os3k_footer))
    } > rom

    .ram (NOLOAD) : {
        __os3k_direct_ram_start = .;
        KEEP(*(.font.ram))
        __os3k_direct_ram_end = .;
        *(.bss .bss.*)
        *(COMMON)
        . = ALIGN(4);
        __os3k_heap_start = .;
        *(.os3k.heap .os3k.heap.*)
        __os3k_heap_end = .;
        . = ALIGN(2);
    } > ram

    __os3k_entry_offset = ABSOLUTE(Os3kEntry);
    __os3k_fixups_offset = ABSOLUTE(ADDR(.data.reloc));
    __os3k_image_offset = LOADADDR(.rom.ram);
    __os3k_image_size = SIZEOF(.rom.ram);
    __os3k_got_size = ABSOLUTE(__os3k_got_end - ORIGIN(ram));
    __os3k_bss_offset = ADDR(.ram) - ORIGIN(ram);
    __os3k_bss_size = SIZEOF(.ram);
    __os3k_rom_size = ADDR(.rom) + SIZEOF(.rom);
    __os3k_ram_size = __os3k_bss_offset + __os3k_bss_size;

    /DISCARD/ : {
        *(.comment .note* .eh_frame*)
    }
}

ASSERT(SIZEOF(os3k_header) == 0x94, "OS3K applet header must be 148 bytes")
ASSERT(ADDR(.rom.ram) == ORIGIN(ram), "GOT must begin at A5")
ASSERT(__os3k_got_size % 4 == 0, "GOT must contain whole longwords")

/* A direct entry may be called before MSG_INIT and cannot rely on startup. */
ASSERT(!__os3k_direct_entry || __os3k_image_size == 0,
       "direct entry must not require GOT or initialized writable data")
ASSERT(!__os3k_direct_entry || SIZEOF(.ram) == (__os3k_direct_ram_end - __os3k_direct_ram_start),
       "direct entry must not require implicit BSS")
