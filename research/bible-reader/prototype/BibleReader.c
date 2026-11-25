#include "os3k.h"
#include "Decoder.h"
#include "Search.h"
#include "Navigation.h"
#include "../../fonts/glyphs.h"
#include <string.h>
/* Observed Neo 3.21 notifications; keep private while the public API evolves. */
#define READER_REDRAW_MESSAGE ((Message_e)0x1b)
#define READER_RELOAD_FONTS 0xfcu
#define READER_REFRESH_CARET 0xfeu
#ifndef BIBLE_VERSION
#define BIBLE_VERSION "KJV"
#endif
#ifndef BIBLE_APP_NAME
#define BIBLE_APP_NAME "BibleReader"
#endif
APPLET_HEADER_BEGIN
 APPLET_ID(0xFF21)
 APPLET_NAME(BIBLE_APP_NAME)
 APPLET_INFO("Bible reader: G reference, Find search, H help")
 APPLET_FLAGS(APPLET_FLAG_ALLOW_FONT_DIALOG)
 .fileCount=1,
 APPLET_VERSION(0,2,"a")
 APPLET_LANGUAGE_EN_US
APPLET_HEADER_END
extern const uint8_t BibleData[],BibleDataEnd[],BibleSearchData[],BibleSearchDataEnd[],BibleVerseCounts[];
static BibleDecoder decoder;
static BibleSearch search;
static TextEditor_t editor;
static FontHeader_t *faces[4],super_font;
static uint16_t verse_offsets[256];
#if NATIVE_STREAM_MODE >= 4
static uint8_t chunk[512]; /* Coalesce a page and its final word into one insert. */
#else
static uint8_t chunk[256];
#endif
#include "Superscript.h"
static uint16_t chapter,verse_count,ready,show_numbers=1,loaded,rendered_numbers;
static uint16_t history_count;
static uint16_t requested_word=65535;
#ifdef READER_TEST_FONT
static uint8_t test_font_applied;
#endif
static uint8_t overlay,entering,command_length,searching,have_search,search_mode;
static const char*const search_labels[]={"Match: Same verse [Tab]","Match: Exact phrase [Tab]","Match: Nearby 20 words [Tab]"};
static char command[64],notice[88];
static FontDialog_t *jump_dialog;
static void close_jump(void){if(jump_dialog){FontDialogDestroy(jump_dialog);jump_dialog=0;}}
static void read_jump(void){char input[82];FontDialogGetInput(0,input);command_length=strlen(input);if(command_length>63)command_length=63;memcpy(command,input,command_length);command[command_length]=0;}
/* Read-only observability; no emulator callbacks or injected actions in app code. */
volatile struct {uint32_t magic,serial,phase,error,chapter,verse,bytes,mode,searching,hits,copied,numbered,word;} g_reader;
static uint16_t be16(const volatile uint8_t*p){return ((uint16_t)p[0]<<8)|p[1];}
static unsigned book_for(unsigned ch){unsigned b=0;while(b<65&&books[b+1].first<=ch)++b;return b;}
static unsigned logical(unsigned raw){if(raw>=editor.gap_end)return raw-(editor.gap_end-editor.gap_start);return raw>editor.gap_start?editor.gap_start:raw;}
#if NATIVE_STREAM_MODE
static unsigned feed_abs(unsigned);
static void feed_capture_file(void);
#endif
static unsigned verse_for(unsigned raw){unsigned pos=
#if NATIVE_STREAM_MODE
 feed_abs(raw),
#else
 logical(raw),
#endif
 v=1;while(v<verse_count&&verse_offsets[v+1]<=pos)++v;return v;}
static void observe(void){g_reader.chapter=chapter;g_reader.verse=loaded?verse_for(editor.caret_offset):1;g_reader.mode=entering?entering:overlay?3:0;g_reader.searching=searching;g_reader.hits=history_count;g_reader.numbered=show_numbers;
#if NATIVE_STREAM_MODE
 feed_capture_file();
#endif
 g_reader.phase=4;++g_reader.serial;}
static void ui_line(unsigned row,const char*s){unsigned col=0;RasterOp(0,row*8,264,8,0,ROP_WHITENESS);while(*s&&col<44){DrawBitmap(col*6,row*8,6,8,GLYPHS[(uint8_t)*s++]);++col;}}
static void show_notice(const char*s){int32_t status=0;if(loaded)TextEditorHandleMessage(&editor,READER_REDRAW_MESSAGE,READER_REFRESH_CARET,0,&status);SetCursorMode(CURSOR_MODE_HIDE);ui_line(6,s);ui_line(7,"Esc: return    G: go to    Find: search");overlay=1;observe();}
static void redraw(void){int32_t status=0;overlay=0;entering=0;ClearScreen();SetCursorMode(CURSOR_MODE_SHOW);TextEditorHandleMessage(&editor,READER_REDRAW_MESSAGE,READER_REFRESH_CARET,0,&status);if(status)g_reader.error=status;observe();}
static void reference(char*out,unsigned ch,unsigned verse){unsigned b=book_for(ch);sprintf(out,"%s %u:%u (%s)",books[b].name,ch-books[b].first+1,verse,BIBLE_VERSION);}
/* Small top-aligned digits live only in an unregistered local face. The ordinary
 * text still uses the selected installed font; native flags 0x0c select face 3. */
static int make_super(void){
 unsigned h=faces[0]->height;
 if(!h||h>64)return 0;
 super_font.height=h;super_font.max_width=4;super_font.max_bytes=32;
 super_font.width_table=superscript_widths;super_font.offset_table=superscript_offsets;super_font.bitmap_data=superscript_bitmaps[(h-1)/8];return 1;
}
static int append(const void*p,unsigned n){
#if NATIVE_STREAM_MODE == 4
 if(loaded){TextScan_t tail;int32_t result;
#ifdef READER_PROFILE
  unsigned prior=g_reader.phase;g_reader.phase=32;
#endif
  if(FileOpen(1,FILE_OPEN_KEEP_POSITION)<0)return 0;
  if(TextScanInit(&editor,&tail,TEXT_POSITION_CARET))return 0;
  TextScanRead(&tail,UINT32_MAX,0,false,TEXT_BYTES_ENCODED,false,false,false,true,0);
  #ifdef READER_PROFILE
  g_reader.phase=33;
#endif
  result=TextScanInsert(&tail,(void*)p,n,TEXT_BYTES_ENCODED);
#ifdef READER_PROFILE
  g_reader.phase=34;g_reader.phase=prior;
#endif
  if(result){g_reader.error=result;return 0;}
 }else
#endif
 if(FileWriteBuffer(1,p,n,FILE_WRITE_APPEND)!=(int)n)return 0;
 g_reader.bytes+=n;return 1;
}
static int emit_byte(uint8_t c,unsigned*n){chunk[(*n)++]=c;if(*n==sizeof(chunk)){if(!append(chunk,*n))return 0;*n=0;}return 1;}
static int marker(unsigned v,unsigned*buffered){uint8_t b[12],digits[3];unsigned n=0,d=0;
#if NATIVE_STREAM_MODE >= 4
 /* Each native insertion must contain complete formatting tokens. */
 if(*buffered+12>sizeof(chunk)){if(!append(chunk,*buffered))return 0;*buffered=0;}
#endif
do{digits[d++]=0x90+v%10;v/=10;}while(v);b[n++]=0xb1;b[n++]=12;b[n++]=0xb1;while(d)b[n++]=digits[--d];b[n++]=0xb2;b[n++]=12;b[n++]=0xb2;for(d=0;d<n;++d)if(!emit_byte(b[d],buffered))return 0;return 1;}
#if NATIVE_STREAM_MODE
#include "NativeFeed.h"
#endif
static int move_to(unsigned position){TextScan_t scan;uint32_t pos=position;int32_t status=0;
#if NATIVE_STREAM_MODE
 g_feed.selected=0;
 if(pos<g_feed.base){if(!feed_rebuild(pos))return 0;}
 while(!g_feed.eof&&pos>=g_feed.end)if(!feed_more(feed_ahead))return 0;
 if(pos<g_feed.base||pos>g_feed.end)return 0;
 pos-=g_feed.base;
#endif
 if(editor.selection_state)TextEditorHandleMessage(&editor,MSG_KEY,KEY_LEFT,0,&status);
 if(TextScanInit(&editor,&scan,TEXT_POSITION_START))return 0;
 if(pos && pos>=editor.gap_start)pos+=editor.gap_end-editor.gap_start;
 TextScanRead(&scan,pos,0,false,TEXT_BYTES_ENCODED,false,false,false,true,0);
 ClearScreen();
 if(TextEditorSetScanPosition(&scan,true))return 0;
 SetCursorMode(CURSOR_MODE_SHOW);
 overlay=entering=0;observe();return 1;
}
static int jump(unsigned verse){if(verse<1||verse>verse_count)return 0;g_reader.word=65535;
#if NATIVE_STREAM_MODE
 if(!feed_verse(verse))return 0;
#endif
 return move_to(verse_offsets[verse]);}
static int jump_word(unsigned verse,unsigned wanted){
#if NATIVE_STREAM_MODE
 BibleDecoder d=decoder;unsigned v=1,g=show_numbers?7:0,ordinal=0,state=0;int c;
 if(!BibleOpenChapter(&d,chapter))return 0;
 while((c=BibleReadByte(&d))>=0){
  if(c=='\n'){if(++v>verse_count)break;++g;if(show_numbers){unsigned n=v;g+=7;while(n>=10){++g;n/=10;}}ordinal=state=0;continue;}
  if(v==verse){if((c>='A'&&c<='Z')||(c>='a'&&c<='z')){if(!state&&ordinal++==wanted){g_reader.word=wanted;return move_to(g);}state=1;}else if(c=='\''&&state==1)state=2;else state=0;}
  ++g;
 }
 return 0;
#else
 unsigned start=verse_offsets[verse],end,pos,n=0,state=0;int32_t saved=FileTell(1),count;unsigned i;
 if(show_numbers){unsigned digits=1,v=verse;while(v>=10){++digits;v/=10;}start+=6+digits;}
 end=verse<verse_count?(unsigned)verse_offsets[verse+1]-1:(uint32_t)FileQuerySize(1)-(editor.gap_end-editor.gap_start);
 pos=start;
 while(pos<end){unsigned raw=pos+(pos>=editor.gap_start?editor.gap_end-editor.gap_start:0),limit=end-pos;
  if(pos<editor.gap_start&&limit>editor.gap_start-pos)limit=editor.gap_start-pos;
  if(limit>sizeof(chunk))limit=sizeof(chunk);
  if(FileSeek(1,raw,FILE_SEEK_START)<0)return 0;
  count=FileReadBuffer(1,chunk,limit);if(count<=0)return 0;
  for(i=0;i<(unsigned)count;++i){unsigned c=chunk[i];
   if((c>='A'&&c<='Z')||(c>='a'&&c<='z')){if(!state){if(n++==wanted){FileSeek(1,saved,FILE_SEEK_START);g_reader.word=wanted;return move_to(pos+i);}}state=1;}
   else if(c=='\''&&state==1)state=2;else state=0;
  }
  pos+=count;
 }
 FileSeek(1,saved,FILE_SEEK_START);return 0;
#endif
}
static void open_chapter(unsigned target,unsigned verse){
#if !NATIVE_STREAM_MODE
 int c;unsigned n=0,v=1;
#endif
 unsigned initial_font=!faces[0],word=requested_word;int32_t status=0;FontHeader_t*font=0;uint32_t reply=0;
 requested_word=65535;g_reader.phase=1;g_reader.error=0;
 if(target>=1189||verse<1||verse>be16(BibleVerseCounts+2*target)){show_notice("Invalid chapter or verse");return;}
 if(loaded && target==chapter && rendered_numbers==show_numbers){
  if(FileOpen(1,FILE_OPEN_KEEP_POSITION)<0
#if !NATIVE_STREAM_MODE
 || TextEditorRefresh(&editor)
#endif
 || !(word==65535?jump(verse):jump_word(verse,word)))goto fail;
  observe();return;
 }
 g_reader.bytes=0;chapter=target;verse_count=be16(BibleVerseCounts+2*chapter);loaded=0;
 FileClose();if(FileOpen(1,FILE_OPEN_REWIND)<0||FileEraseCurrent()<0)goto fail;
 /* Establish native gap/layout state while the file is empty. No text can be
  * painted using the default fourth face before our superscript face exists. */
 SetCursorMode(CURSOR_MODE_SHOW);status=TextEditorInit(&editor,1,TEXT_EDITOR_EDITABLE,65500,0,0,264,64);if(status)goto fail;
 if(!faces[0]){unsigned i;for(i=0;i<4;++i)faces[i]=editor.fonts[i];}
#ifdef READER_TEST_FONT
 #ifndef READER_TEST_FONT_ID
 #define READER_TEST_FONT_ID 0xA1F0
 #endif
 {uint8_t i=AppletFindById(READER_TEST_FONT_ID);if(initial_font&&!test_font_applied){if(i)AppletSendMessage(i,MSG_FONT_GET_NORMAL,(uint32_t)&font,&reply);if(!font)goto fail;faces[0]=faces[1]=faces[2]=font;test_font_applied=1;}}
#else
 (void)font;(void)reply;(void)initial_font;
#endif
 if(!make_super())goto fail;
 status=TextEditorSetFonts(&editor,faces[0],faces[1],faces[2],&super_font,false);if(status)goto fail;
 /* The ROM derives this extent from its global font, which can differ from
  * borrowed faces. Use complete rows within the physical 64-pixel viewport. */
 editor.height=(64/faces[0]->height)*faces[0]->height;
 editor.layout_height=editor.height;
 g_reader.phase=3;
#if NATIVE_STREAM_MODE
 if(!feed_start()||!feed_verse(verse))goto fail;
#if (NATIVE_STREAM_MODE == 5 && READER_OPEN_TEST == 3) || NATIVE_STREAM_MODE == 7
 /* Isolate first display with the entire chapter already decoded. */
 while(!g_feed.eof)if(!feed_more(feed_ahead))goto fail;
#endif
#else
 if(!BibleOpenChapter(&decoder,chapter))goto fail;
 verse_offsets[1]=0;if(show_numbers&&!marker(v,&n))goto fail;
 while((c=BibleReadByte(&decoder))>=0){
  if(c=='\n'){
   ++v;if(v>verse_count)break;
   if(!emit_byte(' ',&n))goto fail;
   if(g_reader.bytes+n>65500)goto fail;
   verse_offsets[v]=g_reader.bytes+n;
   if(show_numbers&&!marker(v,&n))goto fail;
  }else{if(c<32||c>126||!emit_byte(c,&n))goto fail;}
 }
 if(n&&!append(chunk,n))goto fail;
 if(decoder.error||v!=(unsigned)verse_count+1)goto fail;
#endif
 g_reader.phase=2;
 /* Comparison builds isolate reconciliation from final caret/layout. */
#if READER_OPEN_TEST == 1 || NATIVE_STREAM_MODE
 status=0;
#else
 status=TextEditorRefresh(&editor);
#endif
 if(status)goto fail;
 g_reader.phase=6;loaded=1;rendered_numbers=show_numbers;
#if NATIVE_STREAM_MODE >= 5
 /* At chapter start, avoid SetScanPosition's unconditional whole-file layout.
  * Param zero of native repaint draws the cached viewport without relayout. */
 if(verse==1&&word==65535){
#if NATIVE_STREAM_MODE == 5
  if(!feed_cache_viewport())goto fail;
#endif
#if NATIVE_STREAM_MODE >= 6
  /* Native repaint covers complete text rows only; erase dialog residue in
   * the unused bottom margin without clearing/redrawing the text viewport. */
  if(editor.height<64)RasterOp(0,editor.height,264,64-editor.height,0,ROP_WHITENESS);
#endif
  TextEditorHandleMessage(&editor,READER_REDRAW_MESSAGE,0,0,&status);
  if(status)goto fail;
  observe();return;
 }
#endif
#if READER_OPEN_TEST == 2
 if(verse==1&&word==65535){SetCursorMode(CURSOR_MODE_SHOW);observe();return;}
#endif
 if(!(word==65535?jump(verse):jump_word(verse,word)))goto fail;
 observe();return;
fail:g_reader.error=status?status:1;g_reader.phase=5;SetCursorMode(CURSOR_MODE_HIDE);ui_line(0,"Unable to open Bible chapter");
}
/* Status stays in A5; the native file position holds the saved viewport. */
volatile struct {uint32_t calls,status,position,chapter,numbered;} g_saved;
static void save(void){g_reader.phase=15;g_saved.status=TextEditorSavePosition(&editor);g_saved.position=FileTell(1);g_saved.chapter=chapter;g_saved.numbered=show_numbers;++g_saved.calls;FileClose();g_reader.phase=16;}
static void prompt(unsigned kind){close_jump();entering=kind;overlay=0;command_length=0;command[0]=0;SetCursorMode(CURSOR_MODE_HIDE);
 if(kind==1){uint32_t extended=0;CallSysInt(0,SYS_INT_8000,&extended);
  jump_dialog=extended?FontDialogCreate(FONT_DIALOG_LAYOUT_14):0;
  /* Extended native dialogs are absent on older Neo firmware. */
  if(jump_dialog){
   FontDialogActivate(jump_dialog,0);
   FontDialogSetProperty(jump_dialog,0,FONT_DIALOG_SHOW_TITLE,false);
   FontDialogSetProperty(jump_dialog,0,FONT_DIALOG_SHOW_BODY,false);
   FontDialogSetProperty(jump_dialog,0,FONT_DIALOG_ENABLE_INPUT,true);
   FontDialogSetInput(jump_dialog,0,"Go to:");observe();return;
  }
 }
 ui_line(5,kind==1?"Go to: John 3:16 (book number also works)":search_labels[search_mode]);ui_line(6,"");ui_line(7,kind==1?"Enter: accept   Esc: cancel":"Tab: mode  *: prefix  Enter: search");observe();}
static int parse_reference(const char*s,unsigned*ch,unsigned*verse){
 char name[32];unsigned n=0,b=66,c=0,v=1,i=0,end;
 /* Reference name is everything before the last one/two numeric fields. */
 end=strlen(s);while(end&&s[end-1]==' ')--end;
 i=end;while(i&&s[i-1]>='0'&&s[i-1]<='9')--i;if(i==end)return 0;
 for(n=i;n<end;++n){c=c*10+s[n]-'0';if(c>255)return 0;}
 if(i&&(s[i-1]==':'||s[i-1]==' ')){
  unsigned stop=i-1,start=stop;while(start&&s[start-1]==' ')--start;stop=start;
  while(start&&s[start-1]>='0'&&s[start-1]<='9')--start;
  if(start<stop&&start&&s[start-1]==' '){v=c;c=0;for(n=start;n<stop;++n){c=c*10+s[n]-'0';if(c>150)return 0;}i=start;}
 }
 while(i&&s[i-1]==' ')--i;
 if(!i||i>=sizeof(name)||!c)return 0;
 for(n=0;n<i;++n)name[n]=(s[n]>='A'&&s[n]<='Z')?s[n]+32:s[n];
 name[i]=0;
 if(name[0]>='0'&&name[0]<='9'&&i<3){b=0;for(n=0;n<i;++n){if(name[n]<'0'||name[n]>'9')return 0;b=b*10+name[n]-'0';}if(!b||b>66)return 0;--b;}
 else{unsigned matches=0;for(n=0;n<66;++n){const char*p=books[n].name;unsigned k=0;while(k<i&&p[k]&&((p[k]>='A'&&p[k]<='Z')?p[k]+32:p[k])==name[k])++k;if(k==i){b=n;++matches;}}if(matches!=1)return 0;}
 if(c>books[b].chapters)return 0;
 *ch=books[b].first+c-1;*verse=v;return v&&v<=be16(BibleVerseCounts+2*(*ch));
}
/* Count source words up to the native caret; file position is preserved. */
static unsigned reading_word(void){
 unsigned verse=verse_for(editor.caret_offset),end=logical(editor.caret_offset),pos=verse_offsets[verse],n=0,state=0;int32_t saved=FileTell(1);unsigned i;
#if NATIVE_STREAM_MODE
 BibleDecoder d=decoder;unsigned v=1,g=show_numbers?7:0;int c;end=feed_abs(editor.caret_offset);
 if(!BibleOpenChapter(&d,chapter))return 0;
 while(g<end&&(c=BibleReadByte(&d))>=0){if(c=='\n'){++v;++g;if(show_numbers){unsigned x=v;g+=7;while(x>=10){++g;x/=10;}}n=state=0;continue;}
  if(v==verse){if((c>='A'&&c<='Z')||(c>='a'&&c<='z')){if(!state)++n;state=1;}else if(c=='\''&&state==1)state=2;else state=0;}++g;
 }
#else
 if(show_numbers){unsigned digits=1,v=verse;while(v>=10){++digits;v/=10;}pos+=6+digits;}
 while(pos<end){unsigned raw=pos+(pos>=editor.gap_start?editor.gap_end-editor.gap_start:0),limit=end-pos;int count;
  if(pos<editor.gap_start&&limit>editor.gap_start-pos)limit=editor.gap_start-pos;
  if(limit>sizeof(chunk))limit=sizeof(chunk);
  if(FileSeek(1,raw,FILE_SEEK_START)<0)break;
  count=FileReadBuffer(1,chunk,limit);if(count<=0)break;
  for(i=0;i<(unsigned)count;++i){unsigned c=chunk[i];if((c>='A'&&c<='Z')||(c>='a'&&c<='z')){if(!state)++n;state=1;}else if(c=='\''&&state==1)state=2;else state=0;}pos+=count;
 }
 FileSeek(1,saved,FILE_SEEK_START);
#endif
 return n&&state?n-1:n;
}
static void search_direction(int direction,unsigned inclusive){
 if(!have_search){prompt(2);return;}
 SearchFrom(&search,chapter,verse_for(editor.caret_offset),reading_word(),direction,inclusive);
 searching=1;show_notice(direction<0?"Searching previous... Esc cancels":"Searching... Esc cancels");
}
static void search_next(void){search_direction(1,0);}
static void search_previous(void){search_direction(-1,0);}
static void search_step(void){int result;uint32_t start=GetUptimeMilliseconds();
#ifdef READER_PROFILE
 g_reader.phase=11;
#endif
 /* Native idle messages are sparse. Spend up to 200 ms per callback, checking queued keys between blocks,
  * rather than leaving most of each half-second idle interval unused. */
 do{result=SearchStep(&search,64);}while(result==0&&!IsKeyReady()&&GetUptimeMilliseconds()-start<200);
#ifdef READER_PROFILE
 g_reader.phase=12;
#endif
 if(result==0)return;
 searching=0;if(result<0){show_notice(result==-1?(history_count?"No more matches":"No matches"):"Search decode error");return;}
 if(history_count<65535)++history_count;
 requested_word=search.hit_word;
 open_chapter(search.chapter,search.verse);
}
static void copy_verses_impl(void){
 unsigned a=verse_for(editor.caret_offset),b=a,v=1,n=0;int c;char citation[88];int32_t result;
 if(editor.selection_state){unsigned other=verse_for(editor.selection_anchor);if(other<a){b=a;a=other;}else b=other;
  /* A selection ending exactly at the next verse does not include that verse. */
  {unsigned end=logical(editor.caret_offset>editor.selection_anchor?editor.caret_offset:editor.selection_anchor);if(b>a&&end==verse_offsets[b])--b;}}
 if(!BibleOpenChapter(&decoder,chapter)){show_notice("Cannot copy verse");return;}
 if(ClipboardSet(chunk,0,1)<0){show_notice("Clipboard unavailable");return;}
 g_reader.copied=0;
 while((c=BibleReadByte(&decoder))>=0){
  int newline=c=='\n';
  if(v>=a&&v<=b){if(c=='\n')c=(v==b?'\r':' ');chunk[n++]=c;if(n==sizeof(chunk)){result=FileWriteBuffer(FILE_ID_CLIPBOARD,chunk,n,FILE_WRITE_APPEND);if(result!=(int)n)goto fail;g_reader.copied+=n;n=0;}}
  if(newline){if(v==b)break;++v;}
 }
 if(n){if(FileWriteBuffer(FILE_ID_CLIPBOARD,chunk,n,FILE_WRITE_APPEND)!=(int)n)goto fail;g_reader.copied+=n;}
 reference(citation,chapter,a);if(b>a){unsigned book=book_for(chapter);sprintf(citation,"%s %u:%u-%u (%s)",books[book].name,chapter-books[book].first+1,a,b,BIBLE_VERSION);}
 n=strlen(citation);if(FileWriteBuffer(FILE_ID_CLIPBOARD,citation,n,FILE_WRITE_APPEND)!=(int)n)goto fail;g_reader.copied+=n;
 show_notice("Copied verse(s) with citation");return;
fail:ClipboardClear();show_notice("Not enough clipboard memory");
}
#if NATIVE_STREAM_MODE
static void copy_feed_selection(void){BibleDecoder d=decoder;unsigned lo=g_feed.anchor,hi=feed_abs(editor.caret_offset),g=show_numbers?7:0,v=1,n=0,first=0,last=0;int c;
 if(lo>hi){unsigned t=lo;lo=hi;hi=t;}
 if(!BibleOpenChapter(&d,chapter)||ClipboardSet(chunk,0,1)<0)return;
 g_reader.copied=0;
 while((c=BibleReadByte(&d))>=0){
  if(c=='\n'){
   if(v>=verse_count)break;
   if(g>=lo&&g<hi){chunk[n++]=' ';if(!first)first=v;last=v;}
   ++g;++v;if(show_numbers){unsigned z=v;g+=7;while(z>=10){++g;z/=10;}}
  }else{if(g>=lo&&g<hi){chunk[n++]=c;if(!first)first=v;last=v;}++g;}
  if(n==sizeof(chunk)){if(FileWriteBuffer(FILE_ID_CLIPBOARD,chunk,n,FILE_WRITE_APPEND)!=(int)n)return;g_reader.copied+=n;n=0;}
  if(g>=hi)break;
 }
 if(n){FileWriteBuffer(FILE_ID_CLIPBOARD,chunk,n,FILE_WRITE_APPEND);g_reader.copied+=n;}
 if(first){unsigned b=book_for(chapter);char cite[88];
  if(first==last)sprintf(cite,"\r%s %u:%u (%s)",books[b].name,chapter-books[b].first+1,first,BIBLE_VERSION);
  else sprintf(cite,"\r%s %u:%u-%u (%s)",books[b].name,chapter-books[b].first+1,first,last,BIBLE_VERSION);
  FileWriteBuffer(FILE_ID_CLIPBOARD,cite,strlen(cite),FILE_WRITE_APPEND);
 }
 FileOpen(1,FILE_OPEN_KEEP_POSITION);show_notice("Copied verse(s) with citation");
}
#endif
static void copy_verses(void){
#if NATIVE_STREAM_MODE
 BibleDecoder saved=decoder;if(g_feed.selected&&g_feed.anchor!=feed_abs(editor.caret_offset))copy_feed_selection();else copy_verses_impl();decoder=saved;
#else
 copy_verses_impl();
#endif
}
static void accept(void){unsigned ch,v;if(jump_dialog){read_jump();close_jump();}command[command_length]=0;
 if(entering==1){if(!parse_reference(command,&ch,&v)){entering=0;show_notice("Invalid or ambiguous reference");return;}entering=0;open_chapter(ch,v);}
 else{entering=0;history_count=0;
#ifdef READER_PROFILE
 g_reader.phase=9;
#endif
 have_search=SearchBegin(&search,BibleData,BibleDataEnd-BibleData,BibleSearchData,BibleSearchDataEnd-BibleSearchData,command,search_mode);
#ifdef READER_PROFILE
 g_reader.phase=10;
#endif
 if(!have_search){show_notice("Use 1-8 words, at most 63 characters");return;}search_direction(1,1);}
}
#ifdef READER_PROFILE
static void profile_decode(void){int c;uint32_t bytes=0;
#if NATIVE_STREAM_MODE
 BibleDecoder saved=decoder;
#endif
 g_reader.phase=7;
 if(!BibleOpenChapter(&decoder,chapter)){g_reader.error=1;return;}
 while((c=BibleReadByte(&decoder))>=0)++bytes;
 if(c!=-1||decoder.error){g_reader.error=1;return;}
 g_reader.copied=bytes;
#if NATIVE_STREAM_MODE
 decoder=saved;
#endif
 g_reader.phase=8;observe();
}
#endif
#ifdef READER_PROFILE
static void profile_search_all(void){unsigned hits=0;int result;g_reader.phase=13;
 if(!SearchStartMode(&search,BibleData,BibleDataEnd-BibleData,BibleSearchData,BibleSearchDataEnd-BibleSearchData,"Jesus Jesus",1)){g_reader.error=1;return;}
 do{result=SearchStep(&search,4096);if(result==1)++hits;}while(result>=0);
 if(result!=-1){g_reader.error=1;return;}have_search=0;g_reader.copied=hits;g_reader.phase=14;observe();
}
#endif
#ifdef READER_PROFILE
volatile struct {uint32_t query,hits,hash,first_chapter,first_verse,first_word,candidates;} g_search_bench;
#include "SearchBench.h"
static void profile_navigation(void){unsigned q;
 for(q=0;q<sizeof(navigation_cases)/sizeof(*navigation_cases);++q){int r;
  memset((void*)&g_search_bench,0,sizeof(g_search_bench));g_search_bench.query=q;g_search_bench.first_chapter=UINT32_MAX;g_reader.phase=40;
  if(!SearchStartMode(&search,BibleData,BibleDataEnd-BibleData,BibleSearchData,BibleSearchDataEnd-BibleSearchData,navigation_cases[q].query,1)){g_reader.error=32;return;}
  SearchFrom(&search,navigation_cases[q].chapter,navigation_cases[q].verse,navigation_cases[q].word,navigation_cases[q].direction,0);g_reader.phase=41;
  do{r=SearchStep(&search,4096);}while(!r);
  if(r==-2){g_reader.error=33;return;}
  if(r==1){g_search_bench.hits=1;g_search_bench.first_chapter=search.chapter;g_search_bench.first_verse=search.verse;g_search_bench.first_word=search.hit_word;g_reader.phase=42;}
  g_reader.phase=43;
 }
 have_search=0;g_reader.copied=g_search_bench.hits;observe();
}
#include "SearchModesBench.h"
static void profile_modes(void){unsigned q;
 for(q=0;q<sizeof(mode_cases)/sizeof(*mode_cases);++q){int r;
  memset((void*)&g_search_bench,0,sizeof(g_search_bench));g_search_bench.query=q;g_search_bench.first_chapter=UINT32_MAX;g_reader.phase=40;
  if(!SearchBegin(&search,BibleData,BibleDataEnd-BibleData,BibleSearchData,BibleSearchDataEnd-BibleSearchData,mode_cases[q].query,mode_cases[q].mode)){g_reader.error=34;return;}
  SearchFrom(&search,mode_cases[q].chapter,mode_cases[q].verse,mode_cases[q].word,mode_cases[q].direction,0);g_reader.phase=41;
  do{r=SearchStep(&search,4096);}while(!r);
  if(r==-2){g_reader.error=35;return;}
  if(r==1){g_search_bench.hits=1;g_search_bench.first_chapter=search.chapter;g_search_bench.first_verse=search.verse;g_search_bench.first_word=search.hit_word;g_reader.phase=42;}
  g_reader.phase=43;
 }
 have_search=0;g_reader.copied=g_search_bench.hits;observe();
}
static void profile_prefix_queries(void){
 static const char*const queries[]={"Methus","believ","love","God","in the beg","Jesus Jesus","th"};unsigned q;
 for(q=0;q<sizeof(queries)/sizeof(*queries);++q){unsigned i;int r;
  if(READER_BENCH_QUERY>=0&&q!=READER_BENCH_QUERY)continue;
  memset((void*)&g_search_bench,0,sizeof(g_search_bench));g_search_bench.query=q;g_search_bench.first_chapter=UINT32_MAX;g_search_bench.hash=UINT32_C(2166136261);g_reader.phase=40;
  if(!SearchStartMode(&search,BibleData,BibleDataEnd-BibleData,BibleSearchData,BibleSearchDataEnd-BibleSearchData,queries[q],1)){g_reader.error=30;return;}
  for(i=0;i<1189;++i)if(search.candidates[i/8]&(1<<(i&7)))++g_search_bench.candidates;
  g_reader.phase=41;
  while((r=SearchStep(&search,4096))>=0)if(r==1){uint32_t h=g_search_bench.hash;
   h=(h<<5)^(h>>27)^(search.chapter*257u)^((uint32_t)search.verse<<8)^search.hit_word;g_search_bench.hash=h;
   if(!g_search_bench.hits){g_search_bench.first_chapter=search.chapter;g_search_bench.first_verse=search.verse;g_search_bench.first_word=search.hit_word;g_reader.phase=42;}
   ++g_search_bench.hits;
  }
  if(r!=-1){g_reader.error=31;return;}g_reader.phase=43;
 }
 have_search=0;g_reader.copied=g_search_bench.hits;observe();
}
#endif
static void character(unsigned c){
 if(entering==2&&c==9){search_mode=(search_mode+((GetKeyModifiers()&KEY_MOD_SHIFT)?2:1))%3;ui_line(5,search_labels[search_mode]);observe();return;}
#ifdef READER_PROFILE
 if(!entering){
 if(c=='a'||c=='A'){open_chapter(books[39].first+1,1);return;}
 if(c=='b'||c=='B'){open_chapter(books[39].first+1,12);return;}
 if(c=='c'||c=='C'){open_chapter(books[42].first+2,1);return;}
 if(c=='r'||c=='R'){g_reader.phase=20;redraw();g_reader.phase=21;observe();return;}
 if(c=='t'||c=='T'){profile_decode();return;}
 if(c=='y'||c=='Y'){profile_search_all();return;}
 if(c=='z'||c=='Z'){profile_prefix_queries();return;}
 if(c=='x'||c=='X'){profile_navigation();return;}
 if(c=='w'||c=='W'){profile_modes();return;}
 }
#endif
 if(entering){if(jump_dialog && c!='\r' && c!='\n'){if(c==8)FontDialogHandleKey(0x8003);else if(c>=32&&c<=126&&command_length<63)FontDialogHandleKey(c);read_jump();observe();return;}if(c=='\r'||c=='\n'){accept();return;}if(c==8){if(command_length){command[--command_length]=0;ui_line(6,command);observe();}return;}if(c>=32&&c<=126&&command_length<sizeof(command)-1){command[command_length++]=c;command[command_length]=0;ui_line(6,command);observe();}return;}
 if(overlay){redraw();if(c!='g'&&c!='G'&&c!='h'&&c!='H'&&c!='n'&&c!='N'&&c!='p'&&c!='P')return;}
 if(c=='g'||c=='G')prompt(1);
 else if(c=='/'||c=='f'||c=='F')prompt(2);
 else if(c=='n'||c=='N')search_next();
 else if(c=='p'||c=='P')search_previous();
 else if(c=='v'||c=='V'){unsigned v=verse_for(editor.caret_offset);show_numbers=!show_numbers;open_chapter(chapter,v);}
 else if(c=='['){if(chapter)open_chapter(chapter-1,1);}
 else if(c==']'){if(chapter<1188)open_chapter(chapter+1,1);}
 else if(c=='?'){reference(notice,chapter,verse_for(editor.caret_offset));show_notice(notice);}
 else if(c=='h'||c=='H'){ClearScreen();ui_line(0,"BibleReader " BIBLE_VERSION);ui_line(1,"G/Ctrl+G reference; Find search");ui_line(2,"Cmd+Find next; Shift+Cmd+Find previous");ui_line(3,"Arrows move; Shift+arrows select");ui_line(4,"Space/Shift+Space page; V verse numbers");ui_line(5,"Ctrl+C copy verse(s) with citation");ui_line(6,"? location; system font key selects font");ui_line(7,"Find: Tab mode, * prefix; Esc returns");overlay=1;observe();}
 else if(c==' '){int32_t status;unsigned i,rows=64/faces[0]->height;
#ifdef READER_PROFILE
 g_reader.phase=20;
#endif
#if NATIVE_STREAM_MODE
 if(!feed_key((GetKeyModifiers()&KEY_MOD_SHIFT)?KEY_UP:KEY_DOWN,KEY_MOD_CMD)){g_reader.error=11;return;}
#endif
#if READER_PAGE_TEST
 (void)i;(void)rows;
 TextEditorHandleMessage(&editor,MSG_KEY,KEY_MOD_CMD|((GetKeyModifiers()&KEY_MOD_SHIFT)?KEY_UP:KEY_DOWN),0,&status);
#else
 for(i=0;i<rows;++i)TextEditorHandleMessage(&editor,MSG_KEY,(GetKeyModifiers()&KEY_MOD_SHIFT)?KEY_UP:KEY_DOWN,0,&status);
#endif
#ifdef READER_PROFILE
 g_reader.phase=21;
#endif
 observe();}
}
void ProcessMessage(Message_e message,uint32_t param,uint32_t *reply){
 int32_t status=0;unsigned key=param&0x7f;*reply=0;
 if(message==MSG_SETFOCUS){if(!ready){g_reader.magic=0x42524452;ready=BibleInit(&decoder,BibleData,BibleDataEnd-BibleData);g_reader.verse=1;}if(ready){if(loaded){if(FileOpen(1,FILE_OPEN_KEEP_POSITION)<0||TextEditorRefresh(&editor)){g_reader.error=1;return;}redraw();}else open_chapter(chapter,1);}}
 else if(message==MSG_KILLFOCUS){close_jump();if(ready&&loaded)save();}
 else if(ready&&message==MSG_IDLE){if(searching)search_step();
#if NATIVE_STREAM_MODE >= 4 && NATIVE_STREAM_MODE != 7
 else if(loaded&&!entering&&!overlay&&!g_feed.eof&&!IsKeyReady()&&!IsKeyDownNow()&&g_feed.end-feed_abs(editor.caret_offset)<2*feed_ahead){
  g_reader.phase=30;if(!feed_more(feed_ahead)&&!g_reader.error)g_reader.error=14;feed_capture_file();g_reader.phase=31;g_reader.phase=4;
 }
#endif
#if NATIVE_STREAM_MODE == 3
 else if(loaded&&!entering&&!overlay&&!g_feed.eof){uint32_t start=GetUptimeMilliseconds();g_reader.phase=30;feed_defer=1;
  do{if(!feed_more(256)){g_reader.error=14;break;}if(IsKeyReady()||IsKeyDownNow())break;}while(!g_feed.eof&&GetUptimeMilliseconds()-start<50);
  feed_defer=0;feed_capture_file();g_reader.phase=31;g_reader.phase=4;}
#endif
 }
 else if(ready&&message==READER_REDRAW_MESSAGE){if(loaded){unsigned v=verse_for(editor.caret_offset);
  if(param==READER_RELOAD_FONTS){close_jump();entering=0;faces[0]=0;loaded=0;open_chapter(chapter,v);}else redraw();
 }}
 else if(ready&&message==MSG_KEY&&!(param&KEY_MOD_KEY_UP)){
  if(key==KEY_ESC){close_jump();searching=0;
#if NATIVE_STREAM_MODE
 g_feed.selected=0;editor.selection_state=0;
#endif
 redraw();}
  else if(searching)return;
  else if(entering){if(jump_dialog&&key==KEY_BACKSPACE){FontDialogHandleKey(0x8003);read_jump();observe();}else if(jump_dialog&&key==KEY_CLEAR_FILE){FontDialogSetInput(jump_dialog,0,"Go to:");read_jump();observe();}else if(key==KEY_ENTER)accept();else if(!jump_dialog&&key==KEY_BACKSPACE&&command_length){command[--command_length]=0;ui_line(6,command);observe();}}
  else if(key==KEY_G&&(param&KEY_MOD_CTRL))prompt(1);
  else if(key==KEY_FIND&&(param&KEY_MOD_CMD)){
   if(param&KEY_MOD_SHIFT)search_previous();
   else search_next();
  }
  else if(key==KEY_FIND || (key==KEY_F&&(param&(KEY_MOD_CMD|KEY_MOD_CTRL))))prompt(2);
  else if(key==KEY_G&&(param&KEY_MOD_CMD)){
   if(param&KEY_MOD_SHIFT)search_previous();
   else search_next();
  }
#if NATIVE_STREAM_MODE
  else if(key==KEY_A&&(param&KEY_MOD_CTRL)){g_reader.phase=20;if(!feed_select_all())g_reader.error=13;g_reader.phase=21;observe();}
#endif
  else if(key==KEY_C&&(param&KEY_MOD_CTRL))copy_verses();
  else if(!overlay&&(key==KEY_DOWN||key==KEY_UP||key==KEY_LEFT||key==KEY_RIGHT||key==KEY_HOME||key==KEY_END)){
   #ifdef READER_PROFILE
   g_reader.phase=20;
   #endif
#if NATIVE_STREAM_MODE
   int action=feed_key(key,param);if(!action){g_reader.error=12;return;}
   if(action!=2)
#endif
   TextEditorHandleMessage(&editor,message,param,0,&status);
   #ifdef READER_PROFILE
   g_reader.phase=21;
   #endif
#if NATIVE_STREAM_MODE
   feed_key_done();
#endif
   if(status)g_reader.error=status;
   observe();
  }
 }
 else if(ready&&!searching&&message==MSG_CHAR){if(param==3&&!entering){copy_verses();return;}if(!(GetKeyModifiers()&(KEY_MOD_CTRL|KEY_MOD_CMD|KEY_MOD_ALT)))character(param);}
}
