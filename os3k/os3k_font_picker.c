/* Uncached picker: at most 32 installed applets, searched through SDK names. */
#include "os3k.h"
#include <string.h>
#define NO_PROVIDER UINT16_MAX
/* Parsed names exist only on the stack for the duration of a search. */
typedef struct {
    uint16_t handle;
    char label[37];
    uint8_t family_length, variant, lines;
} Face;
FontPickerState g_font_picker;
static FontPickerReadName read_name;
static FontHeader_t* menu_font;
/* Previous paint coordinates only: no provider names or lists are retained. */
static FontPickerState painted;
static bool painted_valid;
_Static_assert(sizeof(FontPickerState) == 6, "picker state layout");

static bool ReadFace(unsigned handle, Face* face) {
    static const char sizes[][12] = {"Very Large", "Extra Large", "Medium", "Large", "Small", "Tiny", "Med"};
    unsigned n, cut, i;
    memset(face, 0, sizeof(*face));
    if(!handle || handle == FONT_PICKER_SYSTEM_SMALL) {
        strcpy(face->label, handle ? "System 7 lines" : "System 4 lines");
        face->handle = handle; face->family_length = 6;
        face->variant = 7; face->lines = handle ? 7 : 4;
        return true;
    }
    else if(!read_name || !read_name(handle, face->label)) return false;
    face->label[36] = 0;
    if(!strncmp(face->label,"BetaWise - ",11))
        memmove(face->label+9,face->label+11,strlen(face->label+11)+1);
    else if(!strncmp(face->label,"Neo Font - ",11))
        memmove(face->label,face->label+11,strlen(face->label+11)+1);
    n = strlen(face->label);
    if(!n) return false;
    face->handle = handle;
    face->variant = 255;
    face->family_length = n;
    for(cut = n; cut && face->label[cut-1] != '('; --cut) {}
    if(cut > 1 && face->label[cut-2] == ' ' && face->label[n-1] == ')') {
        unsigned value = 0, j = cut;
        while(j < n && face->label[j] >= '0' && face->label[j] <= '9') {
            value = value*10 + face->label[j++]-'0';
            if(value > 264) return true;
        }
        if(j < n && face->label[j] == 'x') {
            value = 0; ++j;
            while(j < n && face->label[j] >= '0' && face->label[j] <= '9') {
                value = value*10 + face->label[j++]-'0';
                if(value > 65) return true;
            }
            if(j != n-1) value = 0;
        } else if(strcmp(face->label+j, " lines)") && strcmp(face->label+j, " line)")) value = 0;
        if(value && value <= 65) {
            unsigned length = cut-2;
            face->lines = value;
            for(i = 0; i < sizeof(sizes)/sizeof(*sizes); ++i) {
                unsigned size_length = strlen(sizes[i]);
                if(length < size_length || memcmp(face->label+length-size_length, sizes[i], size_length)) continue;
                if(length != size_length && face->label[length-size_length-1] != ' ') continue;
                face->variant = length-size_length;
                face->family_length = face->variant ? face->variant-1 : 0;
                if(!face->family_length) {
                    /* Only these known vendor IDs form the size-only family.
                     * Community fonts share the prefix, not this identity. */
                    uint16_t id = AppletGetId(handle);
                    if(id != 0xAF00 && id != 0xAF75 && id != 0xAF02 &&
                       id != 0xAF73 && id != 0xAF03) {
                        face->family_length = length;
                        face->variant = cut-1;
                    }
                }
                break;
            }
            if(face->variant == 255) {
                face->family_length = length;
                face->variant = cut-1;
            }
        }
    }
    return true;
}
static const char* Family(const Face* face) {
    return face->variant != 255 && !face->family_length ? "Neo Font" : face->label;
}
static unsigned FamilyLength(const Face* face) {
    return face->variant != 255 && !face->family_length ? 8 : face->family_length;
}
static int CompareFamily(const Face* a, const Face* b) {
    unsigned al = FamilyLength(a), bl = FamilyLength(b);
    int result = strncmp(Family(a), Family(b), al < bl ? al : bl);
    return result ? result : (int)al-(int)bl;
}
static unsigned Distance(const Face* face, unsigned target) {
    return face->lines > target ? face->lines-target : target-face->lines;
}
static bool Closer(const Face* a, const Face* b, unsigned target) {
    unsigned ad = Distance(a,target), bd = Distance(b,target);
    return ad < bd || (ad == bd && (a->lines < b->lines ||
        (a->lines == b->lines && a->handle < b->handle)));
}
/* A single scan chooses both the neighboring family and its closest size.
 * Edge searches choose the alphabetically first/last family instead. */
static unsigned SearchFamily(const Face* anchor, int direction, bool edge) {
    Face candidate, best;
    bool found = false;
    unsigned i;
    for(i = 0; i <= FONT_PICKER_SYSTEM_SMALL; ++i) {
        int comparison;
        if(!ReadFace(i, &candidate)) continue;
        if(!edge && CompareFamily(&candidate,anchor)*direction <= 0) continue;
        comparison = found ? CompareFamily(&candidate,&best)*direction : 0;
        if(!found || (edge ? comparison > 0 : comparison < 0) ||
           (!comparison && Closer(&candidate,&best,g_font_picker.target_lines))) {
            best = candidate; found = true;
        }
    }
    return found ? best.handle : NO_PROVIDER;
}
static unsigned SearchSize(const Face* anchor, int direction) {
    Face candidate, best;
    bool found = false;
    unsigned i, target = direction ? anchor->lines : g_font_picker.target_lines;
    for(i = 0; i <= FONT_PICKER_SYSTEM_SMALL; ++i) {
        if(!ReadFace(i,&candidate) || CompareFamily(&candidate,anchor)) continue;
        if(direction && ((int)candidate.lines-(int)anchor->lines)*direction <= 0) continue;
        if(!found || Closer(&candidate,&best,target)) { best=candidate; found=true; }
    }
    return found ? best.handle : NO_PROVIDER;
}
static unsigned Rows(void) { return 6; }
/* Fill the viewport backwards from the selection, without retaining names. */
static void PositionWindow(void) {
    Face face;
    unsigned previous;
    g_font_picker.top = g_font_picker.choice;
    g_font_picker.row = 0;
    while((unsigned)g_font_picker.row+1 < Rows()) {
        ReadFace(g_font_picker.top,&face);
        previous = SearchFamily(&face,-1,false);
        if(previous == NO_PROVIDER) break;
        g_font_picker.top = previous; ++g_font_picker.row;
    }
}
void FontPickerBegin(FontPickerReadName source, uint16_t current) {
    Face face;
    read_name = source;
    if(current > FONT_PICKER_SYSTEM_SMALL || !ReadFace(current,&face)) { current=0; ReadFace(0,&face); }
    g_font_picker.choice = current;
    g_font_picker.target_lines = face.lines ? face.lines : 4;
    PositionWindow();
}
void FontPickerMove(int family_direction, int size_direction) {
    Face current;
    unsigned next;
    if(!ReadFace(g_font_picker.choice,&current)) return;
    if(family_direction) {
        family_direction = family_direction < 0 ? -1 : 1;
        next = SearchFamily(&current,family_direction,false);
        if(next == NO_PROVIDER) return;
        g_font_picker.choice = next;
        if(family_direction < 0) {
            if(g_font_picker.row) --g_font_picker.row;
            else g_font_picker.top = next;
        } else if((unsigned)g_font_picker.row+1 < Rows()) ++g_font_picker.row;
        else {
            ReadFace(g_font_picker.top,&current);
            g_font_picker.top = SearchFamily(&current,1,false);
        }
    } else if(size_direction) {
        next = SearchSize(&current,size_direction < 0 ? -1 : 1);
        if(next == NO_PROVIDER) return;
        g_font_picker.choice = next;
        ReadFace(next,&current);
        g_font_picker.target_lines = current.lines;
    }
}
void FontPickerEdge(bool last) {
    Face current;
    if(!ReadFace(g_font_picker.choice,&current)) return;
    g_font_picker.choice = SearchFamily(&current,last ? 1 : -1,true);
    PositionWindow();
}
bool FontPickerCanResize(int direction) {
    Face current;
    return ReadFace(g_font_picker.choice,&current) && current.variant != 255 &&
        SearchSize(&current,direction < 0 ? -1 : 1) != NO_PROVIDER;
}
uint16_t FontPickerChoice(void) { return g_font_picker.choice; }

static void Text(unsigned x, unsigned y, unsigned limit, const char* text) {
    while(*text) {
        unsigned c = (uint8_t)*text++;
        unsigned w = menu_font->width_table ? menu_font->width_table[c] : menu_font->max_width;
        unsigned offset = menu_font->offset_table ? menu_font->offset_table[c] : c * menu_font->max_bytes;
        if(x+w > limit) break;
        DrawBitmap(x, y, w, menu_font->height, menu_font->bitmap_data+offset);
        x += w;
    }
}

static void PaintRow(const Face* face, unsigned row, bool erase) {
    static const uint8_t left_triangle[] = {0x08,0x1c,0x3e,0x7f};
    static const uint8_t right_triangle[] = {0x7f,0x3e,0x1c,0x08};
    unsigned pitch = menu_font->height;
    unsigned y = 10+row*pitch;
    if(erase) RasterOp(0,y,264,pitch,NULL,ROP_WHITENESS);
    if(face->variant == 255) Text(6,y,258,face->label);
    else {
        char family[37];
        unsigned length = FamilyLength(face);
        memcpy(family,Family(face),length); family[length]=0;
        Text(6,y,face->handle == g_font_picker.choice ? 108 : 258,family);
        if(face->handle == g_font_picker.choice) {
            Text(120,y,246,face->label+face->variant);
            if(FontPickerCanResize(-1)) DrawBitmap(112,y+(pitch-7)/2,4,7,left_triangle);
            if(FontPickerCanResize(1)) DrawBitmap(250,y+(pitch-7)/2,4,7,right_triangle);
        }
    }
    if(face->handle == g_font_picker.choice) RasterOp(0,y,264,pitch,NULL,ROP_DSTINVERT);
}
void FontPickerDraw(void) {
    Face face;
    unsigned handle, row;
    if(!menu_font) return;
    if(painted_valid && painted.top == g_font_picker.top &&
       painted.target_lines == g_font_picker.target_lines) {
        if(painted.choice != g_font_picker.choice) {
            if(ReadFace(painted.choice,&face)) PaintRow(&face,painted.row,true);
            if(ReadFace(g_font_picker.choice,&face)) PaintRow(&face,g_font_picker.row,true);
        }
    } else {
        if(!ReadFace(g_font_picker.top,&face)) return;
        handle = SearchSize(&face,0);
        ClearScreen();
        Text(6,0,258,"Select a font, then press Enter.");
        RasterOp(0,0,264,menu_font->height,NULL,ROP_DSTINVERT);
        for(row = 0; row < Rows() && handle != NO_PROVIDER; ++row) {
            if(!ReadFace(handle,&face)) break;
            PaintRow(&face,row,false);
            handle = SearchFamily(&face,1,false);
        }
    }
    painted=g_font_picker; painted_valid=true;
}
void FontPickerRedraw(void) { painted_valid=false; FontPickerDraw(); }
bool FontPickerOpen(void) {
    FontPickerClose();
    CallSysInt(0,SYS_INT_GET_SMALL_FONT_PTR,&menu_font);
    if(!menu_font || menu_font->height != 9) {
        menu_font=NULL; return false;
    }
    FontPickerDraw(); return true;
}
void FontPickerClose(void) { menu_font=NULL; painted_valid=false; }
