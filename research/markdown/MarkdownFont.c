#include "os3k.h"
#include "MarkdownGlyphs.h"
APPLET_HEADER_BEGIN
 APPLET_ID(0xA1EC)
 APPLET_FONT_NAME("Markdown Bitmap")
 APPLET_FLAGS(APPLET_FLAG_FONT|APPLET_FLAG_HIDDEN)
 APPLET_VERSION(0,3,"x")
 APPLET_LANGUAGE_EN_US
APPLET_HEADER_END
#define FACE(n) {12,16,32,0,md_widths_##n,md_offsets_##n,md_data_##n}
static FontHeader_t faces[4]={FACE(0),FACE(1),FACE(2),FACE(3)};
void ProcessMessage(Message_e msg,uint32_t param,uint32_t* status){
 *status=0;
 if(msg==0x1000001)*(const char**)param=APPLET_FONT_NAME_PTR;
 else if(msg>=0x1000002&&msg<=0x1000005)*(FontHeader_t**)param=&faces[msg-0x1000002];
}
