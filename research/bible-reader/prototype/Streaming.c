/* Neo 3.21 ROM reader: chapter-anchored layout, native fonts and incremental selection. */
#include "os3k.h"
#include "Decoder.h"
#include "Search.h"
#include "Navigation.h"
#ifndef BIBLE_VERSION
#define BIBLE_VERSION "KJV"
#endif
#ifndef BIBLE_APP_NAME
#define BIBLE_APP_NAME "BibleReader-Stream"
#endif
#include <string.h>
APPLET_HEADER_BEGIN
 APPLET_ID(0xA1B1)
 APPLET_NAME(BIBLE_APP_NAME)
 APPLET_INFO("Bible reader: G jump, Find search, Shift selects, Ctrl+C")
 APPLET_FLAGS(APPLET_FLAG_ALLOW_FONT_DIALOG)
 .fileCount=0,
 APPLET_VERSION(0,3,"a")
 APPLET_LANGUAGE_EN_US
APPLET_HEADER_END
extern const uint8_t BibleData[],BibleDataEnd[],BibleVerseCounts[];
extern const uint8_t BibleSearchData[],BibleSearchDataEnd[];
static BibleSearch search;
static uint16_t searching,have_search,entering,search_mode;
static const char*const search_labels[]={"Find: Same verse [Tab]","Find: Exact phrase [Tab]","Find: Nearby 20 words [Tab]"};
static char command[64];static unsigned command_length;
#define CACHE_LINES 32
#define MAX_ROWS 16
#define NO_LINE 65535u
typedef struct {BiblePoint codec;uint16_t source,verse,marker,skip,line;} LinePoint;
typedef struct {uint16_t start,end,width,verse;} LineInfo;
_Static_assert(sizeof(LinePoint)==20,"compact line checkpoint");
static LinePoint cache[CACHE_LINES],word_point;
static uint8_t valid[CACHE_LINES],fragment[64],copy_chunk[256];
static LineInfo visible[MAX_ROWS],measured;
static uint16_t sx[MAX_ROWS],ex[MAX_ROWS];
static BibleDecoder decoder;
FontHeader_t *stream_font;
static FontHeader_t cursor_font,*ui_font;
static uint16_t top_trim,extra_space,cap_top,clip_top,clip_bottom=65,target_offset=NO_LINE,target_verse,target_word,restore_offset=NO_LINE;
static uint16_t command_cursor;
/* Same Neo cursor ABI used by the existing display wrapper. The public raw
 * SetCursorMode syscall does the actual drawing/hiding/blinking. */
typedef struct {FontHeader_t*font;uint8_t cols,rows;uint16_t oy,ox,x,y;uint8_t visible,pause;} NeoCursor;
#define NATIVE_CURSOR ((volatile NeoCursor*)0x5c68)
static uint16_t chapter,start_verse=1,start_word,current_verse,next_marker,numbered=1,ready;
static uint16_t pending_size,pending_index,pending_offset,pending_verse,pending_marker,has_word;
static char pending[64];
static uint16_t stride,rows,roll,top_line,cursor_line,caret,anchor,anchor_line,selecting,cursor_x,cursor_y,cursor_verse=1,goal_x=65535;
static uint16_t source_pos,origin,eof_line=NO_LINE,eof_offset,suppress,render_row,probe_x=65535,probe_offset,probe_best,probe_cx,probe_verse;
static uint16_t geom_line=NO_LINE,geom_offset,geom_x,geom_verse;
static uint16_t line_x,line_start,line_end,line_verse,found_cursor,selection_low,selection_high;

static char notice[88];
#ifdef READER_TEST_FONT
static uint8_t test_font_applied;
#endif
/* First 22 words preserve the old benchmark record; appended state is read-only. */
volatile struct {uint32_t magic,serial,phase,error,chapter,verse,bytes,mode,searching,hits,copied,numbered,page,start_ms,seek_ms,layout_ms,paint_ms,symbols,source_bytes,seek_bytes,checkpoint_hits,start_word;
 uint32_t top,caret,anchor,selection,cursor_x,cursor_y,roll,pitch,rows,cursor_verse,lines_painted,rolls,cursor_height;} g_stream;
static const uint8_t digits[10][3]={{31,17,31},{18,31,16},{29,21,23},{21,21,31},{7,4,31},{23,21,29},{31,21,29},{1,1,31},{31,21,31},{23,21,31}};
static uint16_t be16(const volatile uint8_t*p){return((uint16_t)p[0]<<8)|p[1];}
static unsigned book_for(unsigned ch){unsigned b=0;while(b<65&&books[b+1].first<=ch)++b;return b;}
static unsigned width(unsigned c){return stream_font->width_table?stream_font->width_table[c]:stream_font->max_width;}
static const uint8_t*bitmap(unsigned c){return stream_font->bitmap_data+(stream_font->offset_table?stream_font->offset_table[c]:c*stream_font->max_bytes);}
static void hide(void){SetCursorMode(CURSOR_MODE_HIDE);}
static void set_roll(unsigned n){roll=n&63;LCD_CMD_REG_LEFT=LCD_CMD_REG_RIGHT=LCD_CMD_START_LINE(roll);}
#if STREAM_LCD_ROLL
/* Recovered reader8 LCD-ring primitives; optional comparison build. */
static int row_y(unsigned row){return row*stride;}
static unsigned band_y(unsigned row){return row*stride;}
static unsigned band_h(unsigned row){(void)row;return stride;}
static void rect(unsigned x,unsigned y,unsigned w,unsigned h,RopCode_e op){unsigned py=(roll+y)&63,first=64-py;if(first>h)first=h;if(w&&first)RasterOp(x,py,w,first,0,op);if(h>first)RasterOp(x,0,w,h-first,0,op);}
static void blit(unsigned x,unsigned y,unsigned w,unsigned h,const uint8_t*b){unsigned py=(roll+y)&63,first=64-py,off,dx,n,shift;
 if(first>=h){DrawBitmap(x,py,w,h,b);return;}DrawBitmap(x,py,w,first,b);
 for(off=first;off<h;off+=n){n=h-off;if(n>8)n=8;shift=off&7;
  for(dx=0;dx<w;++dx){unsigned v=b[(off/8)*w+dx]>>shift;if(shift&&off/8+1<(h+7)/8)v|=(unsigned)b[(off/8+1)*w+dx]<<(8-shift);fragment[dx]=v;}
  DrawBitmap(x,off-first,w,n,fragment);
 }
}
#else
static int row_y(unsigned row){return (int)(row*stride+(rows>1?row*extra_space/(rows-1):0))-top_trim;}
static unsigned band_y(unsigned row){int y=row_y(row);return y<0?0:(unsigned)y;}
static unsigned band_h(unsigned row){return (row+1<rows?band_y(row+1):65)-band_y(row);}
static void rect(unsigned x,int y,unsigned w,unsigned h,RopCode_e op){int end=y+(int)h;if(y<(int)clip_top)y=clip_top;if(end>(int)clip_bottom)end=clip_bottom;if(w&&end>y)RasterOp(x,y,w,end-y,0,op);}
static void blit(unsigned x,int y,unsigned w,unsigned h,const uint8_t*b){unsigned skip=0,off,dx,n,shift;int end=y+(int)h;if(end>(int)clip_bottom)end=clip_bottom;
 if(y<(int)clip_top){skip=clip_top-y;y=clip_top;}if(end<=y||!w)return;
 if(!skip){DrawBitmap(x,y,w,end-y,b);return;}
 for(off=skip;off<skip+(unsigned)(end-y);off+=n){n=skip+end-y-off;if(n>8)n=8;shift=off&7;
  for(dx=0;dx<w;++dx){unsigned v=b[(off/8)*w+dx]>>shift;if(shift&&off/8+1<(h+7)/8)v|=(unsigned)b[(off/8+1)*w+dx]<<(8-shift);fragment[dx]=v;}
  DrawBitmap(x,y+off-skip,w,n,fragment);
 }
}
#endif
static void font(void){uint32_t reply=0;stream_font=0;
#ifdef READER_TEST_FONT
#ifndef READER_TEST_FONT_ID
#define READER_TEST_FONT_ID 0xA1F0
#endif
 if(!test_font_applied){unsigned id=AppletFindById(READER_TEST_FONT_ID);if(id)AppletSendMessage(id,MSG_FONT_GET_NORMAL,(uint32_t)&stream_font,&reply);test_font_applied=1;}
#endif
 if(!stream_font){/* The native font picker maintains its current face here. */stream_font=*(FontHeader_t*volatile*)0x5c7a;if(!stream_font)CallSysInt(0,SYS_INT_GET_SYSTEM_FONT_PTR,&stream_font);}
 if(!stream_font||!stream_font->height||stream_font->height>64||stream_font->max_width>64){g_stream.error=1;return;}
 stride=stream_font->height;if(stride<4)stride=4;
 cap_top=0;{unsigned dx,w=width('A');const uint8_t*b=bitmap('A');for(;cap_top<stream_font->height;++cap_top){unsigned ink=0;for(dx=0;dx<w;++dx)ink|=b[(cap_top/8)*w+dx]&(1<<(cap_top&7));if(ink)break;}}
 top_trim=cap_top?1:0;rows=(65+top_trim)/stride;if(rows>MAX_ROWS)rows=MAX_ROWS;
 extra_space=65+top_trim-rows*stride;
#if STREAM_LCD_ROLL
 rows=64/stride;top_trim=extra_space=0;
#endif
 geom_line=NO_LINE;cursor_font=*stream_font;cursor_font.height=stride;(void)reply;
}

static int byte(void){int c=BibleReadByte(&decoder);if(c>=0)++source_pos;return c;}
static void save_point(LinePoint*p,unsigned line){BibleSavePoint(&decoder,&p->codec);p->source=source_pos;p->verse=current_verse;p->marker=next_marker;p->skip=0;p->line=line;}
static void cache_line(unsigned line){unsigned slot=line%CACHE_LINES;if(has_word){cache[slot]=word_point;cache[slot].skip=pending_index;}else save_point(cache+slot,line);cache[slot].line=line;valid[slot]=1;}
static int word(void){int c;unsigned n=0;if(has_word)return 1;save_point(&word_point,0);
 while((c=byte())>=0&&(c==' '||c=='\n'))if(c=='\n'){++current_verse;next_marker=1;}
 if(c<0)return c==-1?0:-1;
 pending_offset=source_pos-1;pending_verse=current_verse;pending_marker=next_marker;next_marker=0;
 do{if(c<32||c>126||n>=sizeof(pending)-1)return -1;pending[n++]=c;c=byte();}while(c>=0&&c!=' '&&c!='\n');
 if(c<-1)return -1;
 if(c=='\n'){++current_verse;next_marker=1;}
 pending[n]=0;pending_size=n;pending_index=0;has_word=1;
 if(target_offset==NO_LINE&&pending_verse>=target_verse){
  if((!start_word&&!target_word)||pending_verse>target_verse)target_offset=pending_offset;
  else {unsigned j,state=0;for(j=0;j<n;++j){unsigned q=(uint8_t)pending[j];if((q>='A'&&q<='Z')||(q>='a'&&q<='z')){if(!state){if(!target_word){target_offset=pending_offset+j;break;}--target_word;}state=1;}else if(q=='\''&&state==1)state=2;else state=0;}}
 }
 return 1;
}
static int restore_line(unsigned line){LinePoint*p=cache+line%CACHE_LINES;int r;
 if(!valid[line%CACHE_LINES]||p->line!=line)return 0;
 if(!BibleRestorePoint(&decoder,chapter,&p->codec))return 0;
 source_pos=p->source;current_verse=p->verse;next_marker=p->marker;has_word=0;
 if(p->skip){r=word();if(r<=0||p->skip>=pending_size)return 0;pending_index=p->skip;pending_marker=0;}
 ++g_stream.checkpoint_hits;return 1;
}
static unsigned marker_width(unsigned v){unsigned n=1;while(v>=10){++n;v/=10;}return n*4;}
static void boundary(unsigned off,unsigned x){unsigned d;if(off==caret){cursor_x=x;cursor_verse=pending_verse;found_cursor=1;}
 if(probe_x!=65535){d=x>probe_x?x-probe_x:probe_x-x;if(d<probe_best){probe_best=d;probe_offset=off;probe_cx=x;probe_verse=pending_verse;}}}
static void selected(unsigned x,unsigned w,unsigned off){if(render_row<rows&&selecting&&off>=selection_low&&off<selection_high){if(sx[render_row]==65535)sx[render_row]=x;ex[render_row]=x+w;}}
static void cell(unsigned c,unsigned off){unsigned w=width(c);boundary(off,line_x);selected(line_x,w,off);
 if(!suppress&&render_row<rows)blit(line_x,row_y(render_row),w,stream_font->height,bitmap(c));
 if(line_start==65535){line_start=off;line_verse=pending_verse;}line_x+=w;line_end=off+1;boundary(off+1,line_x);
}
static void marker(void){unsigned v=pending_verse,n=0;uint8_t ds[3];
 static const uint8_t tiny[10][3]={{15,9,15},{10,15,8},{9,13,10},{9,11,6},{7,4,15},{11,13,5},{14,13,13},{1,13,3},{15,11,15},{11,11,7}};
 do{ds[n++]=v%10;v/=10;}while(v);
 while(n){unsigned d=ds[--n];selected(line_x,4,pending_offset);if(!suppress&&render_row<rows)blit(line_x,row_y(render_row)+cap_top,3,stream_font->height<8?4:5,stream_font->height<8?tiny[d]:digits[d]);line_x+=4;}
}
/* Build exactly one wrapped line; pending words preserve source context. */
static int line(void){int r;unsigned i,w,cw;line_x=0;line_start=65535;line_end=source_pos;line_verse=current_verse;found_cursor=0;probe_best=65535;
 if(render_row<rows)sx[render_row]=ex[render_row]=65535;
 while((r=word())>0){w=numbered&&pending_marker?marker_width(pending_verse):0;for(i=pending_index;i<pending_size;++i)w+=width((uint8_t)pending[i]);
  if(line_x&&line_x+width(' ')+w>264)break;
  if(line_x){unsigned pv=pending_verse;if(pending_marker&&pending_verse>1)--pending_verse;cell(' ',pending_offset-1);pending_verse=pv;}
  if(numbered&&pending_marker){marker();pending_marker=0;}
  while(pending_index<pending_size){cw=width((uint8_t)pending[pending_index]);if(line_x+cw>264)goto complete;cell((uint8_t)pending[pending_index],pending_offset+pending_index);++pending_index;}
  has_word=0;
 }
complete:
 if(r<0){g_stream.error=2;return -1;}
 if(line_start==65535)line_start=line_end=source_pos;
 measured.start=line_start;measured.end=line_end;measured.width=line_x;measured.verse=line_verse;
 return line_x?1:0;
}
static int reopen(void){if(!BibleOpenChapter(&decoder,chapter))return 0;source_pos=0;current_verse=1;next_marker=1;has_word=0;origin=0;return 1;}
static int seek_line(unsigned target){unsigned i;int r;if(eof_line!=NO_LINE&&target>=eof_line){measured.start=measured.end=eof_offset;measured.width=0;measured.verse=current_verse;return 0;}if(restore_line(target))return 1;if(!reopen())return 0;suppress=1;render_row=MAX_ROWS;
 for(i=0;i<target;++i){cache_line(i);r=line();if(r<=0){eof_line=i;eof_offset=measured.end;suppress=0;return 0;}}
 suppress=0;cache_line(target);return 1;
}
static void range(void){selection_low=anchor<caret?anchor:caret;selection_high=anchor>caret?anchor:caret;}
static void invert_selection(void){unsigned i;for(i=0;i<rows;++i)if(sx[i]!=65535&&ex[i]>sx[i])rect(sx[i],band_y(i),ex[i]-sx[i],band_h(i),ROP_DSTINVERT);}
static int scan_line(unsigned key,unsigned row,unsigned draw){int r;if(!seek_line(key))return 0;cache_line(key);suppress=!draw;render_row=row;r=line();suppress=0;
 if(r==0){eof_line=key;eof_offset=measured.end;}else if(r>0)cache_line(key+1);
 if(key==cursor_line&&found_cursor){geom_line=cursor_line;geom_offset=caret;geom_x=cursor_x;geom_verse=cursor_verse;}
 if(draw)++g_stream.lines_painted;
 return r;
}
static void all(void){unsigned i;geom_line=NO_LINE;hide();set_roll(0);ClearScreen();range();for(i=0;i<rows;++i){if(scan_line(top_line+i,i,1)<0)return;visible[i]=measured;}
 invert_selection();
}
static void caret_show(void){unsigned row;if(cursor_line<top_line||cursor_line>=(unsigned)top_line+rows)return;row=cursor_line-top_line;probe_x=65535;if(geom_line!=cursor_line||geom_offset!=caret)scan_line(cursor_line,MAX_ROWS,0);cursor_x=geom_x;cursor_verse=geom_verse;cursor_y=band_y(row);
 if(cursor_x>263)cursor_x=263;
 cursor_font.height=band_h(row);
 g_stream.cursor_height=cursor_font.height;
 NATIVE_CURSOR->font=&cursor_font;NATIVE_CURSOR->x=cursor_x;
#if STREAM_LCD_ROLL
 NATIVE_CURSOR->y=(roll+cursor_y)&63;
#else
 NATIVE_CURSOR->y=cursor_y;
#endif
 SetCursorMode(CURSOR_MODE_SHOW);
}
static void observe(void){g_stream.chapter=chapter;g_stream.verse=start_verse;g_stream.numbered=numbered;g_stream.page=top_line/rows;g_stream.symbols=decoder.decoded_symbols;g_stream.source_bytes=source_pos;g_stream.start_word=start_word;
 g_stream.top=top_line;g_stream.caret=caret;g_stream.anchor=anchor;g_stream.selection=selecting&&anchor!=caret;g_stream.cursor_x=cursor_x;g_stream.cursor_y=cursor_y;g_stream.roll=roll;g_stream.pitch=stride;g_stream.rows=rows;g_stream.cursor_verse=cursor_verse;g_stream.phase=4;++g_stream.serial;}
static void begin(void){g_stream.start_ms=GetUptimeMilliseconds();g_stream.phase=1;g_stream.lines_painted=0;hide();range();}
static void finish(void){g_stream.layout_ms=GetUptimeMilliseconds();g_stream.phase=3;caret_show();g_stream.paint_ms=GetUptimeMilliseconds();observe();}
#if STREAM_LCD_ROLL
static void viewport(unsigned target){unsigned i;if(target==(unsigned)top_line+1){top_line=target;set_roll(roll+stride);rect(0,(rows-1)*stride,264,64-(rows-1)*stride,ROP_WHITENESS);for(i=0;i+1<rows;++i){visible[i]=visible[i+1];sx[i]=sx[i+1];ex[i]=ex[i+1];}
  scan_line(top_line+rows-1,rows-1,1);visible[rows-1]=measured;++g_stream.rolls;
 }else if(top_line==target+1){top_line=target;set_roll(roll+64-stride);rect(0,0,264,stride,ROP_WHITENESS);if(rows*stride<64)rect(0,rows*stride,264,64-rows*stride,ROP_WHITENESS);for(i=rows-1;i;--i){visible[i]=visible[i-1];sx[i]=sx[i-1];ex[i]=ex[i-1];}
  scan_line(top_line,0,1);visible[0]=measured;++g_stream.rolls;
 }else{top_line=target;all();}}
#else
static void viewport(unsigned target){top_line=target;all();}
#endif
static void reset_reference(unsigned ch,unsigned verse,unsigned word){unsigned n=0;int r;
 g_stream.mode=0;entering=0;chapter=ch;start_verse=verse;start_word=word;target_verse=verse;target_word=word;target_offset=restore_offset;restore_offset=NO_LINE;
 if(verse==1&&!word&&target_offset==NO_LINE)target_offset=0;
 memset(valid,0,sizeof(valid));eof_line=NO_LINE;geom_line=NO_LINE;top_line=cursor_line=anchor_line=0;selecting=0;goal_x=65535;begin();
 if(!reopen()){g_stream.error=3;return;}cache_line(0);
 if(target_offset!=0){suppress=1;render_row=MAX_ROWS;for(;n<65534;++n){cache_line(n);r=line();if(r<=0){if(n)--n;break;}if(target_offset!=NO_LINE&&measured.start<=target_offset&&target_offset<=measured.end)break;}suppress=0;}
 cursor_line=top_line=anchor_line=n;caret=anchor=target_offset==NO_LINE?measured.end:target_offset;
 g_stream.seek_bytes=source_pos;g_stream.seek_ms=GetUptimeMilliseconds();g_stream.phase=2;all();finish();
}
static void selection_refresh(void){unsigned i;uint16_t old_s[MAX_ROWS],old_e[MAX_ROWS];memcpy(old_s,sx,sizeof(sx));memcpy(old_e,ex,sizeof(ex));range();
 for(i=0;i<rows;++i){unsigned a=old_s[i],b=old_e[i],c,d;
  if(!selecting||!visible[i].width||selection_high<=visible[i].start||selection_low>=visible[i].end)sx[i]=ex[i]=65535;
  else if(selection_low<=visible[i].start&&selection_high>=visible[i].end){sx[i]=0;ex[i]=visible[i].width;}
  else{scan_line(top_line+i,i,0);visible[i]=measured;}
  c=sx[i];d=ex[i];
  if(a==65535||b<=a){if(c!=65535&&d>c)rect(c,band_y(i),d-c,band_h(i),ROP_DSTINVERT);}
  else if(c==65535||d<=c)rect(a,band_y(i),b-a,band_h(i),ROP_DSTINVERT);
  else if(b<=c||d<=a){rect(a,band_y(i),b-a,band_h(i),ROP_DSTINVERT);rect(c,band_y(i),d-c,band_h(i),ROP_DSTINVERT);}
  else {if(a!=c)rect(a<c?a:c,band_y(i),a<c?c-a:a-c,band_h(i),ROP_DSTINVERT);if(b!=d)rect(b<d?b:d,band_y(i),b<d?d-b:b-d,band_h(i),ROP_DSTINVERT);}
 }
}
static unsigned word_offset(unsigned right){unsigned i,best=0,have=0,bestsource=0,pos,last=origin,state=0;int c;LinePoint*p=0;
 for(i=0;i<CACHE_LINES;++i)if(valid[i]&&cache[i].source<=caret&&cache[i].line<=cursor_line&&(cache[i].line+1<cursor_line||cache[i].line==0))if(!have||cache[i].source>bestsource){have=1;bestsource=cache[i].source;best=i;}
 if(have)p=cache+best;
 if(p){if(!BibleRestorePoint(&decoder,chapter,&p->codec))return caret;pos=p->source;}else{if(!BibleOpenChapter(&decoder,chapter))return caret;pos=0;}
 while((c=BibleReadByte(&decoder))>=0){if((c>='a'&&c<='z')||(c>='A'&&c<='Z')){if(!state){if(right&&pos>caret)return pos;if(pos<caret&&pos>=origin)last=pos;}state=1;}else if(c=='\''&&state==1)state=2;else state=0;
  if(!right&&pos>=caret)return last;
  ++pos;
 }
 return pos?pos-1:0;
}
static void locate(unsigned off){unsigned n=cursor_line;for(;;){int r=scan_line(n,MAX_ROWS,0);if(r<=0){if(n)--n;else break;}else if(off<measured.start&&n)--n;else if(off>measured.end)++n;else break;}cursor_line=n;caret=off;goal_x=65535;}
static void move(unsigned key,unsigned mods){unsigned target=cursor_line,collapse=0,had_selection=selecting;int r;begin();if(mods&KEY_MOD_SHIFT){if(!selecting){anchor=caret;anchor_line=cursor_line;selecting=1;}}else{if(selecting&&anchor!=caret&&(key==KEY_LEFT||key==KEY_RIGHT)){if((key==KEY_LEFT&&anchor<caret)||(key==KEY_RIGHT&&anchor>caret)){caret=anchor;cursor_line=anchor_line;}collapse=1;}selecting=0;}
 target=cursor_line;probe_x=65535;if(cursor_line>=top_line&&cursor_line<top_line+rows)measured=visible[cursor_line-top_line];else scan_line(cursor_line,MAX_ROWS,0);
 if(collapse){goal_x=65535;}
 else if((mods&(KEY_MOD_CTRL|KEY_MOD_CMD))&&(key==KEY_LEFT||key==KEY_RIGHT)){unsigned off=word_offset(key==KEY_RIGHT);locate(off);}
 else if(key==KEY_LEFT){if(caret>measured.start)--caret;else if(cursor_line){--cursor_line;scan_line(cursor_line,MAX_ROWS,0);caret=measured.end;}goal_x=65535;}
 else if(key==KEY_RIGHT){if(caret<measured.end)++caret;else{r=scan_line(cursor_line+1,MAX_ROWS,0);if(r>0){++cursor_line;caret=measured.start;}}goal_x=65535;}
 else if(key==KEY_HOME){caret=measured.start;goal_x=65535;}
 else if(key==KEY_END){caret=measured.end;goal_x=65535;}
 else{if(goal_x==65535)goal_x=cursor_x;if(key==KEY_UP){if(target)--target;}else ++target;probe_x=goal_x;r=scan_line(target,MAX_ROWS,0);if(r>0){cursor_line=target;caret=probe_offset;geom_line=cursor_line;geom_offset=caret;geom_x=probe_cx;geom_verse=probe_verse;}probe_x=65535;}
 range();if(cursor_line<top_line)viewport(cursor_line);else if(cursor_line>=(unsigned)top_line+rows)viewport(cursor_line-rows+1);
 if(selecting||had_selection)selection_refresh();
 g_stream.seek_ms=GetUptimeMilliseconds();finish();}
static void page_move(int delta){unsigned target,old=cursor_line;int r;begin();selecting=0;target=delta>0?top_line+rows:top_line>rows?top_line-rows:0;probe_x=cursor_x;r=scan_line(target,MAX_ROWS,0);if(r>0){cursor_line=target;caret=probe_offset;viewport(target);}else{cursor_line=old;selection_refresh();}probe_x=65535;g_stream.seek_ms=GetUptimeMilliseconds();finish();}
static void reference(char*out,unsigned a,unsigned b){unsigned book=book_for(chapter);sprintf(out,"%s %u:%u",books[book].name,chapter-books[book].first+1,a);if(b!=a)sprintf(out+strlen(out),"-%u",b);sprintf(out+strlen(out)," (%s)",BIBLE_VERSION);}
static void ui_text(const char*text,unsigned y,unsigned centered){unsigned x=12,i,total=0;for(i=0;text[i];++i)total+=ui_font->width_table?ui_font->width_table[(uint8_t)text[i]]:ui_font->max_width;if(centered&&total<240)x=(264-total)/2;
 for(i=0;text[i]&&x<250;++i){unsigned c=(uint8_t)text[i],w=ui_font->width_table?ui_font->width_table[c]:ui_font->max_width;const uint8_t*b=ui_font->bitmap_data+(ui_font->offset_table?ui_font->offset_table[c]:c*ui_font->max_bytes);if(x+w>250)break;blit(x,y,w,ui_font->height,b);x+=w;}
}
static void ui(const char*text){hide();set_roll(0);DrawRectangle(6,14,252,36,false,true);ui_text(text,24,1);g_stream.paint_ms=GetUptimeMilliseconds();}
static void input_panel(void){unsigned first=command_cursor>38?command_cursor-38:0,x=12,j;hide();set_roll(0);DrawRectangle(6,14,252,36,false,true);ui_text(entering==1?"Go to:":search_labels[search_mode],16,1);ui_text(command+first,32,0);
 for(j=first;j<command_cursor;++j)x+=ui_font->width_table?ui_font->width_table[(uint8_t)command[j]]:ui_font->max_width;
 RasterOp(x,32,1,16,0,ROP_BLACKNESS);g_stream.paint_ms=GetUptimeMilliseconds();
}
static void restore_overlay(void){unsigned i;clip_top=14;clip_bottom=50;rect(0,14,264,36,ROP_WHITENESS);range();for(i=0;i<rows;++i){scan_line(top_line+i,i,1);visible[i]=measured;}invert_selection();clip_top=0;clip_bottom=65;}
static void copy(void){unsigned lo=anchor<caret?anchor:caret,hi=anchor>caret?anchor:caret,v=1,a=0,b=0,pos=0,n=0;int c;begin();if(!BibleOpenChapter(&decoder,chapter)||ClipboardSet(copy_chunk,0,1)<0){g_stream.error=4;return;}g_stream.copied=0;
 while((c=BibleReadByte(&decoder))>=0){unsigned take=selecting&&lo!=hi?(pos>=lo&&pos<hi):(v==cursor_verse&&c!='\n');if(take){if(!a)a=v;b=v;copy_chunk[n++]=c=='\n'?' ':c;if(n==sizeof(copy_chunk)){if(FileWriteBuffer(FILE_ID_CLIPBOARD,copy_chunk,n,FILE_WRITE_APPEND)!=(int)n)goto fail;g_stream.copied+=n;n=0;}}
  ++pos;if((selecting&&lo!=hi&&pos>=hi)||(!(selecting&&lo!=hi)&&c=='\n'&&v==cursor_verse))break;if(c=='\n')++v;
 }
 if(n&&FileWriteBuffer(FILE_ID_CLIPBOARD,copy_chunk,n,FILE_WRITE_APPEND)!=(int)n)goto fail;
 g_stream.copied+=n;copy_chunk[0]='\r';if(FileWriteBuffer(FILE_ID_CLIPBOARD,copy_chunk,1,FILE_WRITE_APPEND)!=1)goto fail;reference(notice,a?a:cursor_verse,b?b:cursor_verse);n=strlen(notice);if(FileWriteBuffer(FILE_ID_CLIPBOARD,notice,n,FILE_WRITE_APPEND)!=(int)n)goto fail;g_stream.copied+=n+1;g_stream.mode=3;ui("Copied");observe();return;
fail:g_stream.error=5;
}
static void end_chapter(unsigned all_select,unsigned shift){unsigned line_no=0,last_end=0,old_caret=caret,old_anchor=selecting?anchor:caret,old_line=cursor_line,old_anchor_line=selecting?anchor_line:cursor_line;begin();start_verse=1;start_word=0;memset(valid,0,sizeof(valid));eof_line=NO_LINE;reopen();suppress=1;render_row=MAX_ROWS;
 do{cache_line(line_no);if(line()<=0)break;if(measured.start<=old_caret&&old_caret<=measured.end)old_line=line_no;if(measured.start<=old_anchor&&old_anchor<=measured.end)old_anchor_line=line_no;last_end=measured.end;++line_no;}while(line_no<65534);
 suppress=0;eof_line=line_no;eof_offset=last_end;cursor_line=line_no?line_no-1:0;caret=eof_offset;
 if(all_select){anchor=anchor_line=0;selecting=1;}else if(shift){anchor=old_anchor;anchor_line=old_anchor_line;selecting=1;}else{anchor=caret;anchor_line=cursor_line;selecting=0;}
 top_line=cursor_line>=(unsigned)rows?cursor_line-rows+1:0;goal_x=65535;range();all();g_stream.seek_ms=GetUptimeMilliseconds();finish();(void)old_line;
}
static void start_chapter(unsigned shift){unsigned old=selecting?anchor:caret,n=0,old_line=0;begin();start_verse=1;start_word=0;memset(valid,0,sizeof(valid));eof_line=NO_LINE;reopen();
 if(shift){suppress=1;render_row=MAX_ROWS;for(;;){cache_line(n);if(line()<=0)break;if(measured.start<=old&&old<=measured.end){old_line=n;break;}++n;}suppress=0;}
 caret=cursor_line=top_line=0;anchor=shift?old:0;anchor_line=shift?old_line:0;selecting=shift;goal_x=65535;range();all();g_stream.seek_ms=GetUptimeMilliseconds();finish();
}

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


static void prompt(unsigned kind){begin();g_stream.mode=kind;entering=kind;command_length=command_cursor=0;command[0]=0;input_panel();observe();}
#if STREAM_SEARCH
static unsigned reading_word(void){BibleDecoder d=decoder;unsigned off=0,n=0,state=0;int c;
 if(!BibleOpenChapter(&d,chapter))return 0;
 while(off<caret&&(c=BibleReadByte(&d))>=0){++off;if(c=='\n'){n=state=0;continue;}
  if((c>='A'&&c<='Z')||(c>='a'&&c<='z')){if(!state)++n;state=1;}else if(c=='\''&&state==1)state=2;else state=0;
 }
 return n&&state?n-1:n;
}
static void search_direction(int direction,unsigned inclusive){if(!have_search){prompt(2);return;}
 SearchFrom(&search,chapter,cursor_verse,reading_word(),direction,inclusive);
 hide();searching=1;g_stream.searching=1;g_stream.mode=3;ui(direction<0?"Searching previous... Esc cancels":"Searching... Esc cancels");observe();
}
static void previous_match(void){search_direction(-1,0);}
static void next_match(void){search_direction(1,0);}
static void search_step(void){int r;uint32_t start=GetUptimeMilliseconds();g_stream.phase=11;do{r=SearchStep(&search,64);}while(!r&&!IsKeyReady()&&GetUptimeMilliseconds()-start<200);g_stream.phase=12;if(!r)return;searching=0;g_stream.searching=0;g_stream.mode=0;
 if(r==1){++g_stream.hits;reset_reference(search.chapter,search.verse,search.hit_word);}else{g_stream.mode=3;ui(r==-1?"No more matches":"Search error");observe();}}
#ifdef READER_PROFILE
static void scan_all(const char*q){int r;unsigned hits=0;g_stream.phase=13;if(!SearchStartMode(&search,BibleData,BibleDataEnd-BibleData,BibleSearchData,BibleSearchDataEnd-BibleSearchData,q,1)){g_stream.error=6;return;}do{r=SearchStep(&search,4096);if(r==1)++hits;}while(r>=0);if(r!=-1){g_stream.error=7;return;}g_stream.copied=hits;have_search=0;g_stream.phase=14;observe();}
#endif
#endif
static void accept(void){unsigned ch,v;unsigned kind=entering;entering=0;g_stream.mode=0;
 if(kind==1){if(parse_reference(command,&ch,&v))reset_reference(ch,v,0);else{g_stream.mode=3;ui("Invalid reference; Esc returns");observe();}}
#if STREAM_SEARCH
 else{g_stream.phase=9;have_search=SearchBegin(&search,BibleData,BibleDataEnd-BibleData,BibleSearchData,BibleSearchDataEnd-BibleSearchData,command,search_mode);g_stream.phase=10;if(have_search){search_direction(1,1);}else{g_stream.mode=3;ui("Use 1-8 words; Esc returns");observe();}}
#endif
}
static void character(unsigned c){
 if(entering==2&&c==9){search_mode=(search_mode+((GetKeyModifiers()&KEY_MOD_SHIFT)?2:1))%3;input_panel();observe();return;}
 if(!entering&&c<32)return;
 if(entering){if(c=='\r'||c=='\n'){accept();return;}if(c==8){if(command_cursor){memmove(command+command_cursor-1,command+command_cursor,command_length-command_cursor+1);--command_length;--command_cursor;}}else if(c>=32&&c<127&&command_length<63){memmove(command+command_cursor+1,command+command_cursor,command_length-command_cursor+1);command[command_cursor++]=c;++command_length;}input_panel();observe();return;}
 if(g_stream.mode){g_stream.mode=0;restore_overlay();caret_show();}
 if(c=='g'||c=='G')prompt(1);
#if STREAM_SEARCH
 else if(c=='f'||c=='F'||c=='/')prompt(2);
#ifdef READER_PROFILE
 else if(c=='y'||c=='Y')scan_all("Jesus Jesus");else if(c=='u'||c=='U')scan_all("Melchizedek");
#endif
#endif
 else if(c=='v'||c=='V'){numbered=!numbered;restore_offset=caret;reset_reference(chapter,start_verse,start_word);}
 else if(c==' ')page_move((GetKeyModifiers()&KEY_MOD_SHIFT)?-1:1);else if(c=='n'||c=='N')page_move(1);else if(c=='p'||c=='P')page_move(-1);
 else if(c=='['&&chapter)reset_reference(chapter-1,1,0);else if(c==']'&&chapter<1188)reset_reference(chapter+1,1,0);
 else if(c=='?'||c=='h'||c=='H'){g_stream.mode=3;reference(notice,cursor_verse,cursor_verse);ui(notice);observe();}
#ifdef READER_PROFILE
 else if(c=='a'||c=='A')reset_reference(books[39].first+1,1,0);else if(c=='b'||c=='B')reset_reference(books[39].first+1,12,0);else if(c=='c'||c=='C')reset_reference(books[42].first+2,1,0);
 else if(c=='t'||c=='T'){int q;unsigned n=0;g_stream.phase=7;if(!BibleOpenChapter(&decoder,chapter)){g_stream.error=8;return;}while((q=BibleReadByte(&decoder))>=0)++n;if(q!=-1||decoder.error){g_stream.error=9;return;}g_stream.copied=n;g_stream.phase=8;observe();}
 else if(c=='r'||c=='R'){begin();all();g_stream.seek_ms=GetUptimeMilliseconds();finish();}
 else if(c>='0'&&c<='9'){static const uint8_t bs[]={1,1,43,19,19,19,66,19,40,23},cs[]={1,1,3,119,119,119,22,117,5,53},vs[]={1,31,16,1,88,176,21,1,1,5};unsigned n=c-'0';reset_reference(books[bs[n]-1].first+cs[n]-1,vs[n],0);}
#endif
}
void ProcessMessage(Message_e message,uint32_t param,uint32_t*reply){unsigned key=param&127;*reply=0;
 if(message==MSG_SETFOCUS){if(!ready){g_stream.magic=0x42535452;CallSysInt(0,SYS_INT_GET_SYSTEM_FONT_PTR,&ui_font);ready=BibleInit(&decoder,BibleData,BibleDataEnd-BibleData);font();if(!ready||g_stream.error){g_stream.error=8;return;}reset_reference(0,1,0);}else{begin();all();g_stream.seek_ms=GetUptimeMilliseconds();finish();}}
 else if(message==MSG_KILLFOCUS){entering=searching=0;g_stream.mode=g_stream.searching=0;hide();set_roll(0);}
#if STREAM_SEARCH
 else if(message==MSG_IDLE&&searching)search_step();
#endif
 else if(message==MSG_CHAR&&ready)character(param);
 else if(message==MSG_KEY&&ready&&!(param&KEY_MOD_KEY_UP)){
  if(key==KEY_ESC){entering=0;
#if STREAM_SEARCH
 searching=0;g_stream.searching=0;
#endif
 begin();if(selecting){selecting=0;selection_refresh();}if(g_stream.mode)restore_overlay();g_stream.mode=0;g_stream.seek_ms=GetUptimeMilliseconds();finish();return;}
  if(entering){if(key==KEY_ENTER)accept();else{if(key==KEY_BACKSPACE&&command_cursor){memmove(command+command_cursor-1,command+command_cursor,command_length-command_cursor+1);--command_cursor;--command_length;}else if(key==KEY_LEFT&&command_cursor)--command_cursor;else if(key==KEY_RIGHT&&command_cursor<command_length)++command_cursor;else if(key==KEY_HOME)command_cursor=0;else if(key==KEY_END)command_cursor=command_length;else if(key==KEY_CLEAR_FILE)command[command_length=command_cursor=0]=0;input_panel();observe();}return;}
#if STREAM_SEARCH
  if(searching)return;
  if(key==KEY_FIND&&(param&KEY_MOD_CMD)){if(param&KEY_MOD_SHIFT)previous_match();else next_match();return;}
  if(key==KEY_FIND||(key==KEY_F&&(param&(KEY_MOD_CMD|KEY_MOD_CTRL)))){prompt(2);return;}
  if(key==KEY_G&&(param&KEY_MOD_CMD)){if(param&KEY_MOD_SHIFT)previous_match();else next_match();return;}
#endif
  if(key==KEY_G&&(param&KEY_MOD_CTRL)){prompt(1);return;}
  if(key==KEY_C&&(param&KEY_MOD_CTRL)){copy();return;}if(key==KEY_A&&(param&KEY_MOD_CTRL)){end_chapter(1,0);return;}
  if((param&(KEY_MOD_CTRL|KEY_MOD_CMD))&&key==KEY_HOME){start_chapter(!!(param&KEY_MOD_SHIFT));return;}
  if((param&(KEY_MOD_CTRL|KEY_MOD_CMD))&&key==KEY_END){end_chapter(0,!!(param&KEY_MOD_SHIFT));return;}
  if(key==KEY_LEFT||key==KEY_RIGHT||key==KEY_UP||key==KEY_DOWN||key==KEY_HOME||key==KEY_END){if(g_stream.mode){g_stream.mode=0;restore_overlay();}move(key,param);}
 }
 else if(message==MSG_REFRESH&&ready){if(param==MSG_REFRESH_FONTS){entering=0;g_stream.mode=0;font();restore_offset=caret;reset_reference(chapter,start_verse,start_word);}else{begin();all();g_stream.seek_ms=GetUptimeMilliseconds();finish();}}
}
