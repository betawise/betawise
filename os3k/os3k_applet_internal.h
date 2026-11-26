#ifndef OS3K_APPLET_INTERNAL_H
#define OS3K_APPLET_INTERNAL_H
#include "os3k_applet.h"
/* Private adapters for secondary A0 results. Instruction bodies were verified
 * on AS3000 3.01, Neo 3.01 and Neo 3.21; these are not new firmware syscalls.
 * Missing/zero IDs and missing/zero/out-of-range indices return NULL.
 */
const AppletHeader_t* _OS3K_AppletHeaderById(uint16_t id);
const AppletHeader_t* _OS3K_AppletHeaderByIndex(uint32_t index);
#endif
