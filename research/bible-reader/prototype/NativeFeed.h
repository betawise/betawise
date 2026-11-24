/* Native incremental-file experiments. Modes 6/7 prepare wrap cache in C;
 * earlier modes use ROM wrapping.
 * Mode 1 evicts at a ROM-reported viewport boundary. Mode 2 retains the prefix.
 * Positions in this module are chapter-global native encoded-byte positions. */
volatile struct {uint32_t base,end,verse,eof,refills,trims,peak,capacity,anchor,selected,replays,source;} g_feed;
static void *feed_file;
static void feed_capture_file(void){(void)FileBindState(1,&feed_file,0,0,0);}
static unsigned feed_ahead,feed_limit,feed_marker,feed_seeking,feed_dirty,feed_defer;
static int move_to(unsigned);
static unsigned feed_abs(unsigned p){return g_feed.base+logical(p);}
static void feed_stats(void){int32_t length=FileQuerySize(1),cap=FileGetCapacity(1);
 if(length>0&&(uint32_t)length>g_feed.peak)g_feed.peak=length;
 if(cap>0&&(uint32_t)cap>g_feed.capacity)g_feed.capacity=cap;
}
static int feed_position(unsigned p){TextScan_t s;uint32_t raw=p;int32_t r;
 if(TextScanInit(&editor,&s,TEXT_POSITION_START))return 0;
 if(raw>=editor.gap_start)raw+=editor.gap_end-editor.gap_start;
 TextScanRead(&s,raw,0,false,TEXT_BYTES_ENCODED,false,false,false,true,0);
 r=TextEditorSetScanPosition(&s,true);return !r;
}
#if NATIVE_STREAM_MODE == 1
static int feed_drop(void){
 TextScan_t s;unsigned cut,old=logical(editor.caret_offset);int32_t r;
 editor.selection_state=0;
 if(!logical(editor.viewport_offset)){
  if(!feed_position(g_reader.bytes?g_reader.bytes-1:0))return 0;
 }
 cut=logical(editor.viewport_offset);if(!cut)return 0;
 if(TextScanInit(&editor,&s,TEXT_POSITION_START))return 0;
 /* Encoded scan counts include the raw gap; the chapter base does not. */
 r=TextScanDelete(&s,cut+(cut>=editor.gap_start?editor.gap_end-editor.gap_start:0),TEXT_BYTES_ENCODED,false,false);if(r)return 0;
 g_feed.base+=cut;g_reader.bytes-=cut;++g_feed.trims;
 if(!feed_position(old>cut?old-cut:0))return 0;
 return 1;
}
#endif
#if NATIVE_STREAM_MODE == 5
/* Neo 3.21 research only: private layout helper, not a portable SDK contract.
 * A clone keeps the live caret/viewport unchanged while caching two screens.
 * This assumes layout does not change encoded length; assert that below. */
static int feed_cache_viewport(void){TextEditor_t preview=editor;int32_t before=FileQuerySize(1),r;
 if(*(volatile uint32_t*)0x42b5d0!=UINT32_C(0x48e73f3a))return 0;
 preview.layout_height=2*editor.layout_height;
 preview.caret_offset=preview.viewport_offset;preview.selection_state=0;
 r=((int32_t(*)(TextEditor_t*,uint32_t))0x42b5d0)(&preview,0);
 return !r&&FileQuerySize(1)==before;
}
#endif
#if NATIVE_STREAM_MODE >= 6
#include "NativePrewrap.h"
#endif
static int feed_more(unsigned want){unsigned n=0,start=g_reader.bytes;int c=-1;
#if NATIVE_STREAM_MODE == 1
 if(g_reader.bytes+want+96>feed_limit&&!feed_drop())return 0;
 start=g_reader.bytes;
#endif
 if(g_feed.eof)return 1;
 ++g_feed.refills;
 if(feed_marker){verse_offsets[g_feed.verse]=g_feed.base+g_reader.bytes;if(show_numbers&&!marker(g_feed.verse,&n))return 0;feed_marker=0;}
 do{
  c=BibleReadByte(&decoder);if(c<0){if(c!=-1)return 0;g_feed.eof=1;break;}++g_feed.source;
  if(c=='\n'){
   ++g_feed.verse;if(g_feed.verse>verse_count){g_feed.eof=1;break;}
   if(!emit_byte(' ',&n))return 0;
   verse_offsets[g_feed.verse]=g_feed.base+g_reader.bytes+n;
   if(show_numbers&&!marker(g_feed.verse,&n))return 0;
  }else if(c<32||c>126||!emit_byte(c,&n))return 0;
 }while(g_reader.bytes+n-start<want||(c!=' '&&c!='\n'));
 if(n&&!append(chunk,n))return 0;
 g_feed.end=g_feed.base+g_reader.bytes;feed_stats();
#if NATIVE_STREAM_MODE >= 6
 if(!prewrap_more())return 0;
#endif
#if NATIVE_STREAM_MODE == 5
 if(loaded&&!feed_cache_viewport())return 0;
#endif
 if(loaded&&!feed_seeking&&NATIVE_STREAM_MODE<4){if(feed_defer)feed_dirty=1;else{if(!feed_position(logical(editor.caret_offset)))return 0;feed_dirty=0;}}
 return !decoder.error;
}
static void feed_geometry(void){unsigned c,min=faces[0]->max_width,rows=64/faces[0]->height;
 if(faces[0]->width_table){min=64;for(c=32;c<127;++c){unsigned w=faces[0]->width_table[c];if(w&&w<min)min=w;}}
 if(!min)min=1;
 feed_ahead=((264/min*(rows+4)+128+255)/256)*256;
 if(NATIVE_STREAM_MODE>=4)feed_ahead=((264/min*rows+64+255)/256)*256;
 feed_limit=feed_ahead*2;if(feed_limit<4096)feed_limit=4096;
}
static int feed_start(void){
 feed_capture_file();
 memset((void*)&g_feed,0,sizeof(g_feed));memset(verse_offsets,0xff,sizeof(verse_offsets));g_feed.verse=1;feed_marker=1;feed_dirty=0;feed_geometry();
#if NATIVE_STREAM_MODE >= 6
 prewrap_start();
#endif
 return BibleOpenChapter(&decoder,chapter)&&feed_more(feed_ahead);
}
static int feed_rebuild(unsigned goal){uint32_t peak=g_feed.peak,capacity=g_feed.capacity,replays=g_feed.replays+1;int32_t r;
 FileClose();if(FileOpen(1,FILE_OPEN_REWIND)<0||FileEraseCurrent()<0)return 0;g_reader.bytes=0;
 r=TextEditorInit(&editor,1,TEXT_EDITOR_EDITABLE,65500,0,0,264,64);if(r)return 0;
 if(TextEditorSetFonts(&editor,faces[0],faces[1],faces[2],&super_font,false))return 0;
 editor.height=editor.layout_height=(64/faces[0]->height)*faces[0]->height;
 if(!feed_start())return 0;
 g_feed.peak=peak;g_feed.capacity=capacity;g_feed.replays=replays;
 feed_seeking=1;
 while(!g_feed.eof&&g_feed.end<goal)if(!feed_more(feed_ahead))return 0;
 if(goal<g_feed.base||!feed_position(goal-g_feed.base))return 0;
 /* Establish the real caret before extending lookahead: eviction must retain
  * its line, not the end of a speculative prefix beyond the requested point. */
 while(!g_feed.eof&&g_feed.end<goal+feed_ahead)if(!feed_more(feed_ahead))return 0;
 feed_seeking=0;return goal>=g_feed.base&&feed_position(goal-g_feed.base);
}
static int feed_verse(unsigned v){
 while(!g_feed.eof&&g_feed.verse<=v)if(!feed_more(feed_ahead))return 0;
 if(verse_offsets[v]<g_feed.base)return feed_rebuild(verse_offsets[v]);
 return 1;
}
static int feed_view(unsigned top,unsigned caret){TextScan_t s;unsigned raw;
 if(top<g_feed.base||caret<g_feed.base)return 0;
 raw=top-g_feed.base;if(raw>=editor.gap_start)raw+=editor.gap_end-editor.gap_start;
 if(TextScanInit(&editor,&s,TEXT_POSITION_START))return 0;
 TextScanRead(&s,raw,0,false,TEXT_BYTES_ENCODED,false,false,false,true,0);
 editor.viewport_offset=s.offset;editor.viewport_scan_flags=s.flags;editor.viewport_scan_line=s.line_state;
 return feed_position(caret-g_feed.base);
}
static int feed_finish(void){unsigned prior=feed_defer;feed_defer=1;
 while(!g_feed.eof)if(!feed_more(feed_ahead)){feed_defer=prior;return 0;}
 feed_defer=prior;
 if(feed_dirty&&!feed_defer){if(!feed_position(logical(editor.caret_offset)))return 0;feed_dirty=0;}
 return 1;
}
static int feed_ready(unsigned key,unsigned param){unsigned cur=feed_abs(editor.caret_offset);int back=key==KEY_UP||key==KEY_LEFT||key==KEY_HOME;
 if(feed_dirty){if(!feed_position(logical(editor.caret_offset)))return 0;feed_dirty=0;}
 if(key==KEY_HOME&&g_feed.base){if(!feed_rebuild(0))return 0;}
 if(back&&g_feed.base&&logical(editor.viewport_offset)==0){unsigned top=feed_abs(editor.viewport_offset);if(!feed_rebuild(cur)||!feed_view(top,cur))return 0;}
 if(key==KEY_END||(key==KEY_HOME&&(param&(KEY_MOD_CTRL|KEY_MOD_CMD)))){
  if(key==KEY_END){if(!feed_finish())return 0;}
  else if(g_feed.base&&!feed_rebuild(0))return 0;
 }else if(!back&&!g_feed.eof&&g_feed.end-cur<feed_ahead){if(!feed_more(feed_ahead))return 0;}
#if NATIVE_STREAM_MODE == 5
 /* Font-dependent pages need cache preparation even without a refill. */
 if(!feed_cache_viewport())return 0;
#endif
 return 1;
}
/* Keep a chapter-global selection when its anchor has left the resident file.
 * The native editor sees the intersection; clipboard decoding uses the full span. */
static void feed_selection(void){TextScan_t s;unsigned p,raw;
 if(!g_feed.selected){editor.selection_state=0;return;}
 p=g_feed.anchor<g_feed.base?0:g_feed.anchor-g_feed.base;if(p>g_reader.bytes)p=g_reader.bytes;
 raw=p;if(raw>=editor.gap_start)raw+=editor.gap_end-editor.gap_start;
 TextScanInit(&editor,&s,TEXT_POSITION_START);TextScanRead(&s,raw,0,false,TEXT_BYTES_ENCODED,false,false,false,true,0);
 editor.selection_anchor=s.offset;editor.selection_flags=s.flags;editor.selection_state=1;
}
static int feed_key(unsigned key,unsigned param){unsigned cur=feed_abs(editor.caret_offset),oldanchor=g_feed.anchor,oldselected=g_feed.selected;int shift=param&KEY_MOD_SHIFT;
 if(shift){if(!g_feed.selected){g_feed.anchor=cur;g_feed.selected=1;}}
 else if(g_feed.selected&&(key==KEY_LEFT||key==KEY_RIGHT)){
  unsigned goal=key==KEY_LEFT?(g_feed.anchor<cur?g_feed.anchor:cur):(g_feed.anchor>cur?g_feed.anchor:cur);
  g_feed.selected=0;if(!move_to(goal))return 0;return 2;
 }else g_feed.selected=0;
 oldanchor=g_feed.anchor;oldselected=g_feed.selected;
 if(!feed_ready(key,param))return 0;
 g_feed.anchor=oldanchor;g_feed.selected=oldselected;feed_selection();return 1;
}
static void feed_key_done(void){if(g_feed.selected&&g_feed.anchor==feed_abs(editor.caret_offset)){g_feed.selected=0;editor.selection_state=0;}}
static int feed_select_all(void){
 g_feed.selected=0;editor.selection_state=0;if(!feed_finish())return 0;
 g_feed.selected=0;if(!move_to(g_feed.end))return 0;g_feed.anchor=0;g_feed.selected=1;feed_selection();
 {int32_t status;TextEditorHandleMessage(&editor,READER_REDRAW_MESSAGE,READER_REFRESH_CARET,0,&status);if(status)return 0;}
 return 1;
}
