/* Version-pinned experiment: access to AlphaWord globals is not a public API. */
#include "os3k.h"
#include <string.h>
void _OS3K_ClearScreen(void);
APPLET_HEADER_BEGIN
#ifdef BEAMER_HOOK_PROBE
 APPLET_ID(0xFF14)
 APPLET_NAME("Markdown Hook Probe")
#elif defined(LIVE_MARKDOWN)
 APPLET_ID(0xFF11)
 APPLET_NAME("CoWriter Markdown Probe")
#else
 APPLET_ID(0xFF10)
 APPLET_NAME("CoWriter Markdown Probe")
#endif
 APPLET_FLAGS(APPLET_FLAG_HIDDEN)
 APPLET_VERSION(0,1,"x")
 APPLET_LANGUAGE_EN_US
APPLET_HEADER_END
struct Control {uint8_t state,action;uint32_t length;const uint8_t* text;};
_Static_assert(sizeof(struct Control)==10,"companion ABI");
volatile struct {
 uint32_t magic,serial,command,done,error,keys,chars,hotkeys,preview,alpha,editor;
 uint32_t length,caret,gap_start,gap_end,caret_flags,viewport,source_length;
 uint32_t before_length,before_caret,before_gap_start,before_gap_end,selected;
 uint8_t source[256];
 uint32_t clip_length;uint8_t clip[128];uint32_t clipboard_format;
} g_probe;
static uint8_t preview;
static CursorMode_e previous_mode;
static TextEditor_t* ed;
static FontHeader_t* faces[4];
static uint8_t open_token[3] __attribute__((aligned(2)))={0xb1,4,0xb1};
static uint8_t close_token[3] __attribute__((aligned(2)))={0xb2,4,0xb2};
static uint8_t keyboard_tokens[]={0xb1,4,0xb1,'w','o','r','d',0xb2,4,0xb2};
static int locate(void){
 uint32_t index=AppletFindById(0xa000),alpha;
 if(!index)return 0;
 alpha=*(volatile uint32_t*)(0x355e + 4*index);
 if(alpha<0x1000||alpha+3472>=0x80000)return 0;
 ed=(TextEditor_t*)(alpha+0x12);g_probe.alpha=alpha;g_probe.editor=(uint32_t)ed;
 return ed->file_id!=0;
}
#ifdef LIVE_MARKDOWN
static int live_read(void);static void live_observe(void);
#endif
static void snapshot(void){
 TextScan_t scan;unsigned n;
 if(!locate()){g_probe.error=1;return;}
#ifdef LIVE_MARKDOWN
 if(g_probe.command==10||g_probe.command==11){int error=live_read();if(error)g_probe.error=error;else live_observe();return;}
#endif
 g_probe.length=FileQuerySize(ed->file_id);g_probe.caret=ed->caret_offset;g_probe.gap_start=ed->gap_start;g_probe.gap_end=ed->gap_end;
 g_probe.clipboard_format=ClipboardGetFormat();g_probe.caret_flags=ed->caret_scan_flags;g_probe.viewport=ed->viewport_offset;g_probe.selected=ed->selection_state;
 if(TextScanInit(ed,&scan,TEXT_POSITION_START)){g_probe.error=2;return;}
 n=TextScanRead(&scan,255,(uint8_t*)g_probe.source,false,TEXT_BYTES_PLAIN,false,false,false,true,0);
 g_probe.source_length=n;g_probe.source[n]=0;
}
static int fonts(void){
 unsigned i;uint32_t reply=0,index=AppletFindById(
#ifdef LIVE_MARKDOWN
 0xFF13
#else
 0xFF12
#endif
 );
 if(!index)return 0;
 for(i=0;i<4;++i)if((g_probe.done=100+i),!AppletSendMessage(index,(Message_e)(0x1000002+i),(uint32_t)&faces[i],&reply)||!faces[i])return 0;
 g_probe.done=110;return TextEditorSetFonts(ed,faces[0],faces[1],faces[2],faces[3],false)==0;
}
static int position(TextScan_t* scan,unsigned n){
 if(TextScanInit(ed,scan,TEXT_POSITION_START))return 0;
 return TextScanRead(scan,n,0,false,TEXT_BYTES_PLAIN,false,false,false,true,0)==n;
}
static int style(void){
 TextScan_t scan;
 g_probe.done=120;if(!position(&scan,2)||TextScanInsert(&scan,open_token,3,TEXT_BYTES_ENCODED))return 0;
 g_probe.done=121;if(!position(&scan,6)||TextScanInsert(&scan,close_token,3,TEXT_BYTES_ENCODED))return 0;
 g_probe.done=122;if(TextEditorRefresh(ed)||!position(&scan,8)||TextEditorSetScanPosition(&scan,false))return 0;
 return 1;
}
static int overwrite(unsigned offset,uint8_t* data){
 uint32_t raw=offset+(offset>=ed->gap_start?ed->gap_end-ed->gap_start:0);
 return FileSeek(ed->file_id,raw,FILE_SEEK_START)==(int32_t)raw&&FileWriteBuffer(ed->file_id,data,3,FILE_WRITE_OVERWRITE)==3;
}
static int padding(void){
 int32_t saved=FileTell(ed->file_id);
 if(!overwrite(0,open_token)||!overwrite(7,close_token))return 0;
 FileSeek(ed->file_id,saved,FILE_SEEK_START);
 return TextEditorRefresh(ed)==0;
}
static void draw_preview(void){
 unsigned i,x=0;const uint8_t* s=(const uint8_t*)g_probe.source;
 /* Keep ROM roll and controller start-line synchronized. */
 _OS3K_ClearScreen();SetCursorMode(CURSOR_MODE_HIDE);
 /* Fixture preview: remove literal asterisks and use face 1. */
 for(i=0;i<g_probe.source_length;++i)if(s[i]!='*'){
  if(x+8>264)break;
  DrawBitmap(x,0,8,8,faces[1]->bitmap_data+8*s[i]);x+=8;
 }
}
#ifdef LIVE_MARKDOWN
volatile struct {uint32_t events,rewrites,fastpath,decoded,parsed,message,param;uint16_t phase,reserved;} g_perf;
volatile uint32_t g_seed_length;
#include "live-markdown.inc"
#endif
void ProcessMessage(Message_e msg,uint32_t param,uint32_t* status){
 struct Control* c=(struct Control*)status;uint32_t command;
 if(msg==MSG_INIT){g_probe.magic=0x4d445052;g_probe.command=
#ifdef LIVE_MARKDOWN
 11;
#else
 9;
#endif
 return;}
#ifdef BEAMER_HOOK_PROBE
 if(msg==0x1000001||msg==0x1000003){++g_probe.hotkeys;g_probe.done=msg;g_probe.preview=param;snapshot();*status=1;return;}
 *status=0;return;
#endif
 if(msg<0x1000000||msg>0x1000005){*status=0;return;}
 c->state=msg==0x1000004?0:1;c->action=1;c->length=0;c->text=0;
 ++g_probe.serial;
 if(msg==0x1000003)++g_probe.keys;
 if(msg==0x1000001)++g_probe.chars;
 if(msg==0x1000000){snapshot();return;}
 if(msg==0x1000002){preview=0;g_probe.preview=0;return;}
 if(msg!=0x1000003||param!=0x9046){
#ifdef LIVE_MARKDOWN
 if((g_probe.command==10||g_probe.command==11)&&(msg==0x1000001||msg==0x1000003)&&live_event(msg,param,c))return;
#endif
 if(preview)c->action=0;return;}
 ++g_probe.hotkeys;snapshot();command=g_probe.command;if(command==9)command=preview?6:5;g_probe.error=0;
 g_probe.before_length=g_probe.length;g_probe.before_caret=g_probe.caret;g_probe.before_gap_start=g_probe.gap_start;g_probe.before_gap_end=g_probe.gap_end;
 #ifdef LIVE_MARKDOWN
 if(command==12){g_probe.error=live_seed();g_probe.command=11;}
 else if(command==10||command==11){g_probe.command=command==10?11:10;g_probe.error=live_restyle();}
 else
#endif
 if(command==1){if(!fonts())g_probe.error=3;}
 else if(command==2){if(!style())g_probe.error=4;}
 else if(command==3){c->action=2;c->length=sizeof(keyboard_tokens);c->text=keyboard_tokens;}
 else if(command==4){if(!padding())g_probe.error=5;}
 else if(command==5){unsigned i;for(i=0;i<4;++i)faces[i]=ed->fonts[i];GetCursorMode(&previous_mode);preview=1;draw_preview();}
 else if(command==8){if(ClipboardSet(keyboard_tokens,sizeof(keyboard_tokens),0)!=(int32_t)sizeof(keyboard_tokens))g_probe.error=8;}
 else if(command==7){g_probe.clip_length=ClipboardGet((void*)g_probe.clip,127,CLIPBOARD_TEXT_PLAIN);}
 else if(command==6){preview=0;SetCursorMode(previous_mode);c->action=3;}
 snapshot();g_probe.preview=preview;g_probe.done=command;
 if(command!=3)c->action=preview?0:3;
}
