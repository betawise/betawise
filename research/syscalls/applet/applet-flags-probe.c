/* Production SDK adapters executed against original ROM and controlled headers. */
#include "os3k_applet_internal.h"
#include <stddef.h>
int sdk_flags_probe(void) {
    volatile uint32_t* result = (volatile uint32_t*)0x73c00;
    if(_OS3K_AppletHeaderById(0xafee) != (const AppletHeader_t*)0x39100) return 1;
    if(_OS3K_AppletHeaderById(0xffff) || _OS3K_AppletHeaderById(0)) return 2;
    if(_OS3K_AppletHeaderByIndex(1) != (const AppletHeader_t*)0x39100) return 3;
    if(_OS3K_AppletHeaderByIndex(2) != (const AppletHeader_t*)0x39200) return 4;
    if(_OS3K_AppletHeaderByIndex(3) != (const AppletHeader_t*)0x39300) return 5;
    if(_OS3K_AppletHeaderByIndex(31)) return 6;
    if(AppletGetFlags(1) != 0xff000030 || AppletGetFlags(2) || AppletGetFlags(3) != 0x20) return 7;
    if(AppletGetFlags(0) || AppletGetFlags(31) || AppletGetFlags(32) || AppletGetFlags(UINT32_MAX)) return 8;
    if(!AppletIsFont(1) || AppletIsFont(2) || !AppletIsFont(3)) return 9;
    if(AppletGetId(1)!=0xafee || AppletGetId(2)!=0xa123 || AppletGetId(3)!=0xafef || AppletGetId(31)) return 10;
    result[0] = 0x70617373;
    return 0;
}
