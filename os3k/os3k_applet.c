#include "os3k_applet_internal.h"
#include <stddef.h>

/* Capture A0 immediately: a C call through the scalar-return declarations
 * intentionally exposes only D0. The ordinary stub call is essential because
 * the A-line handler returns to its caller, not to the following instruction.
 * Function addresses use the compiler's normal PIC/GOT machinery.
 */
const AppletHeader_t* _OS3K_AppletHeaderById(uint16_t id) {
    register uint32_t result __asm__("d0");
    register const AppletHeader_t* header __asm__("a0");
    if(!id) return NULL;
    __asm__ volatile (
        "move.l %2,-(%%sp)\n\t"
        "jsr (%3)\n\t"
        "addq.l #4,%%sp"
        : "=d" (result), "=a" (header)
        : "d" ((uint32_t)id), "a" (AppletFindById)
        : "d1", "a1", "cc", "memory");
    return result ? header : NULL;
}

const AppletHeader_t* _OS3K_AppletHeaderByIndex(uint32_t index) {
    char name[37];
    unsigned length;
    register uint32_t result __asm__("d0");
    register const char* source_end __asm__("a0");
    const char* end;
    if(!index || index >= 32) return NULL;
    __asm__ volatile (
        "move.l %3,-(%%sp)\n\t"
        "move.l %2,-(%%sp)\n\t"
        "jsr (%4)\n\t"
        "addq.l #8,%%sp"
        : "=d" (result), "=a" (source_end)
        : "d" (index), "a" (name), "a" (AppletGetName)
        : "d1", "a1", "cc", "memory");
    if(!(uint8_t)result) return NULL;
    end = source_end;
    for(length = 0; length < 36 && name[length]; ++length) {}
    return (const AppletHeader_t*)(end-length-offsetof(AppletHeader_t,name));
}

uint32_t AppletGetFlags(uint32_t index) {
    const AppletHeader_t* header = _OS3K_AppletHeaderByIndex(index);
    return header ? header->flags : 0;
}

uint16_t AppletGetId(uint32_t index) {
    const AppletHeader_t* header = _OS3K_AppletHeaderByIndex(index);
    return header ? header->id : 0;
}
