#include "os3k.h"
#include "ProbeGlyphs.h"
APPLET_HEADER_BEGIN
 APPLET_ID(0xFF12)
 APPLET_FONT_NAME("Probe faces")
 APPLET_FLAGS(APPLET_FLAG_FONT|APPLET_FLAG_HIDDEN)
 APPLET_VERSION(0,1,"x")
 APPLET_LANGUAGE_EN_US
APPLET_HEADER_END
static FontHeader_t fonts[4];
void ProcessMessage(Message_e msg,uint32_t param,uint32_t* status){
 unsigned i;*status=0;
 if(msg==MSG_INIT)for(i=0;i<4;++i){fonts[i].height=8;fonts[i].max_width=8;fonts[i].max_bytes=8;fonts[i].bitmap_data=probe_glyphs[i][0];}
 else if(msg==0x1000001)*(const char**)param=APPLET_FONT_NAME_PTR;
 else if(msg>=0x1000002&&msg<=0x1000005)*(FontHeader_t**)param=&fonts[msg-0x1000002];
}
