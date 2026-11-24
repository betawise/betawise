#include "os3k.h"
#include "Decoder.h"
#include "Navigation.h"
#include <string.h>

APPLET_HEADER_BEGIN
    APPLET_ID(0xA1F2)
    APPLET_NAME("Bible Reader")
    APPLET_INFO("KJV compressed-ROM feasibility prototype")
    APPLET_VERSION(0, 1, "p")
    APPLET_LANGUAGE_EN_US
APPLET_HEADER_END

extern const uint8_t BibleData[], BibleDataEnd[];
extern const uint8_t BibleSeekData[], BibleSeekDataEnd[];
static BibleDecoder decoder;
static char screen[8][44];
static uint16_t selected_book, selected_chapter=1, selected_verse=1;
static uint16_t current_verse=1, page_number;
#if !BIBLE_ASCII
static uint8_t pending[3];
#endif
static uint8_t pending_count, pending_pos;
static char command[24];
static uint16_t command_size;
static uint8_t entering, initialized;
#if BIBLE_FULL_CACHE
static uint8_t g_chapter_cache[16384];
#endif

/* Test observers read these markers; no addresses or test calls in the reader.
 * phase is committed last, after all associated data/timer fields. */
volatile struct {
    uint32_t magic, serial, phase, chapter, verse, kind;
    uint32_t start_ms, seek_ms, layout_ms, paint_ms, chapter_prefix_symbols, page_symbols;
    uint32_t error, workspace, screen_bytes, init_ms;
} g_bible_bench;

static unsigned number(char *out,unsigned value) {
    char tmp[6];unsigned n=0,i;
    do {tmp[n++]='0'+value%10;value/=10;}while(value);
    for(i=0;i<n;++i) out[i]=tmp[n-i-1];
    return n;
}
static void title(void) {
    unsigned p=0,n=0;const char *name=books[selected_book].name;
    screen[0][p++]='K';screen[0][p++]='J';screen[0][p++]='V';screen[0][p++]=' ';
    while(name[n] && p<28) screen[0][p++]=name[n++];
    screen[0][p++]=' ';p+=number(screen[0]+p,selected_chapter);
    screen[0][p++]=':';p+=number(screen[0]+p,selected_verse);
    if(page_number) {screen[0][p++]=' ';screen[0][p++]='+';number(screen[0]+p,page_number);}
}
static int display_byte(void) {
#if BIBLE_ASCII
    int c=BibleReadByte(&decoder);
    if(c>127){decoder.error=1;return -2;}
    return c;
#else
    int c,a,b;
    if(pending_pos<pending_count) return pending[pending_pos++];
    pending_pos=pending_count=0;c=BibleReadByte(&decoder);
    if(c<0 || c<128) return c;
    if(c==0xc3) {
        a=BibleReadByte(&decoder);
        if(a==0xa6 || a==0x86) {pending[0]=a==0xa6?'e':'E';pending_count=1;return a==0xa6?'a':'A';}
    } else if(c==0xe2) {
        a=BibleReadByte(&decoder);b=BibleReadByte(&decoder);
        if(a==0x80 && b==0x99) return '\'';
        if(a==0x80 && b==0x94) return '-';
        if(a==0x80 && b==0xa6) {pending[0]=pending[1]='.';pending_count=2;return '.';}
    }
    decoder.error=1;return -2;
#endif
}
static void paint(void) {
    uint16_t r,c;
    ClearScreen();SetCursorMode(CURSOR_MODE_HIDE);
    for(r=0;r<8;++r) {
        SetCursor(r+1,1,CURSOR_MODE_HIDE);
        for(c=0;c<44;++c) putchar(screen[r][c]);
    }
    SetCursor(8,1,CURSOR_MODE_HIDE);
}
static void show_page(uint8_t reopen) {
    unsigned row=1,col=0;int c;uint32_t before;
    uint16_t absolute=books[selected_book].first+selected_chapter-1;
    ++g_bible_bench.serial;g_bible_bench.chapter=absolute;g_bible_bench.verse=selected_verse;
    g_bible_bench.kind=reopen?0:1;g_bible_bench.error=0;
    g_bible_bench.start_ms=GetUptimeMilliseconds();g_bible_bench.phase=1;
    if(reopen) {
        page_number=0;current_verse=1;pending_count=pending_pos=0;
#if BIBLE_USE_SEEK
        if(!BibleSeekVerse(&decoder,absolute,selected_verse,BibleSeekData,
           (uint32_t)(BibleSeekDataEnd-BibleSeekData),&current_verse)) goto fail;
#else
        if(!BibleOpenChapter(&decoder,absolute)) goto fail;
#endif
        while(current_verse<selected_verse) {
            c=BibleReadByte(&decoder);if(c<0) goto fail;
            if(c=='\n') ++current_verse;
        }
    } else ++page_number;
    g_bible_bench.chapter_prefix_symbols=decoder.decoded_symbols;
    g_bible_bench.seek_ms=GetUptimeMilliseconds();g_bible_bench.phase=2;
    memset(screen,' ',sizeof(screen));title();before=decoder.decoded_symbols;
    while(row<8) {
        c=display_byte();
        if(c==-1) break;
        if(c<0) goto fail;
        if(c=='\n') {++row;col=0;++current_verse;continue;}
        if(c<32 || c>126) goto fail;
        screen[row][col++]=c;
        if(col==44) {col=0;++row;}
    }
    g_bible_bench.page_symbols=decoder.decoded_symbols-before;
    g_bible_bench.layout_ms=GetUptimeMilliseconds();g_bible_bench.phase=3;
    paint();g_bible_bench.paint_ms=GetUptimeMilliseconds();g_bible_bench.phase=4;
    return;
fail:
    g_bible_bench.error=decoder.error?decoder.error:2;
    memset(screen,' ',sizeof(screen));memcpy(screen[0],"Bible decode/verse error",23);paint();
    g_bible_bench.phase=5;
}
static void select_reference(unsigned book,unsigned chapter,unsigned verse) {
    if(book<1 || book>66 || chapter<1 || chapter>books[book-1].chapters || verse<1 || verse>176) return;
    selected_book=book-1;selected_chapter=chapter;selected_verse=verse;show_page(1);
}
#if BIBLE_FULL_CACHE
static void cache_chapter(void) {
    uint32_t count=0,hash=2166136261u,i;int c;unsigned p;
    uint16_t chapter=books[selected_book].first+selected_chapter-1;
    ++g_bible_bench.serial;g_bible_bench.chapter=chapter;g_bible_bench.verse=1;
    g_bible_bench.kind=2;g_bible_bench.error=0;
    g_bible_bench.start_ms=GetUptimeMilliseconds();g_bible_bench.phase=1;
    if(!BibleOpenChapter(&decoder,chapter)){g_bible_bench.error=1;g_bible_bench.phase=5;return;}
    g_bible_bench.seek_ms=GetUptimeMilliseconds();g_bible_bench.phase=2;
    while((c=BibleReadByte(&decoder))>=0){
        if(count>=sizeof(g_chapter_cache)){decoder.error=1;break;}
        g_chapter_cache[count++]=c;
    }
    g_bible_bench.layout_ms=GetUptimeMilliseconds();g_bible_bench.phase=3;
    if(c!=-1||decoder.error){g_bible_bench.error=2;g_bible_bench.phase=5;return;}
    g_bible_bench.chapter_prefix_symbols=count;g_bible_bench.page_symbols=decoder.decoded_symbols;
    for(i=0;i<count;++i)hash=(hash^g_chapter_cache[i])*16777619u;
    selected_verse=1;page_number=0;memset(screen,' ',sizeof(screen));title();
    memcpy(screen[1],"Full chapter decoded",20);memcpy(screen[2],"Bytes: ",7);number(screen[2]+7,count);
    memcpy(screen[3],"Hash: ",6);
    for(p=0;p<8;++p)screen[3][6+p]="0123456789ABCDEF"[(hash>>(28-4*p))&15];
    paint();g_bible_bench.paint_ms=GetUptimeMilliseconds();g_bible_bench.phase=4;
}
#endif
static void shortcut(unsigned key) {
    static const uint16_t references[10][3] = {
        {1,1,1},{1,1,31},{43,3,16},{19,119,1},{19,119,88},
        {19,119,176},{66,22,21},{19,117,1},{40,5,1},{23,53,5}
    };
    select_reference(references[key][0],references[key][1],references[key][2]);
}
static void typed(unsigned c) {
    if(entering) {
        if(c=='\r' || c=='\n') {
            unsigned values[3]={0,0,0},field=0,i;
            for(i=0;i<command_size;++i) {
                if(command[i]==' ') {if(++field>2) break;}
                else values[field]=values[field]*10+command[i]-'0';
            }
            entering=0;
            if(field==2) select_reference(values[0],values[1],values[2]);
        } else if(c==8 && command_size) --command_size;
        else if(command_size<sizeof(command)-1 && ((c>='0' && c<='9') || c==' ')) command[command_size++]=c;
        if(entering) {
            unsigned i;SetCursor(8,1,CURSOR_MODE_HIDE);
            for(i=0;i<44;++i) putchar(i<command_size?command[i]:' ');
            SetCursor(8,1,CURSOR_MODE_HIDE);
        }
    }
#if BIBLE_FULL_CACHE
    else if(c=='t'||c=='T')cache_chapter();
#endif
    else if(c>='0' && c<='9') shortcut(c-'0');
    else if(c=='g' || c=='G') {
        entering=1;command_size=0;SetCursor(8,1,CURSOR_MODE_HIDE);printf("Goto: book chapter verse (e.g. 43 3 16)     ");
        SetCursor(8,1,CURSOR_MODE_HIDE);
    }
}
void ProcessMessage(Message_e message,uint32_t param,uint32_t *status) {
    *status=0;
    if(message==MSG_SETFOCUS) {
        uint32_t start=GetUptimeMilliseconds();
        initialized=BibleInit(&decoder,BibleData,(uint32_t)(BibleDataEnd-BibleData));
        g_bible_bench.magic=0x4249424c;g_bible_bench.workspace=sizeof(decoder);
        g_bible_bench.screen_bytes=sizeof(screen);g_bible_bench.init_ms=GetUptimeMilliseconds()-start;
        if(initialized) show_page(1);
        else {ClearScreen();printf("Bible container invalid");g_bible_bench.error=1;g_bible_bench.phase=5;}
    } else if(initialized && message==MSG_CHAR) typed(param);
    else if(initialized && message==MSG_KEY && !(param&KEY_MOD_KEY_UP)) {
        if(param==KEY_DOWN && !entering) show_page(0);
        else if(param==KEY_ENTER && entering) typed('\r');
        else if(param==KEY_BACKSPACE && entering) typed(8);
    }
}
