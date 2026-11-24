/* Interactive Neo 3.21 research applet; all drawing/editing is original ROM UI. */
#include "os3k.h"

APPLET_HEADER_BEGIN
    APPLET_ID(0xA1F2)
    APPLET_NAME("Font Dialog Demo")
    APPLET_INFO("Betawise Neo 3.21 dialog research")
    APPLET_VERSION(0, 1, 'a')
    APPLET_LANGUAGE_EN_US
APPLET_HEADER_END

typedef struct { uint8_t id, count, body_mask, kinds[5]; } Layout;
static const Layout layouts[] = {
    {5,5,24,{4,3,2,3,3}}, {6,3,0,{4,3,2}},
    {7,1,1,{5}}, {8,1,1,{5}}, {9,1,1,{5}},
    {11,3,6,{5,4,4}}, {12,1,1,{4}}, {13,1,1,{3}},
    {14,1,1,{3}}, {15,1,1,{2}}, {16,3,6,{2,4,4}},
    {17,3,6,{4,4,4}}, {18,1,1,{5}}, {19,3,6,{5,4,4}},
    {20,3,6,{5,4,4}}, {21,3,6,{5,4,3}}
};
static char selector_body[] =
    "5  Five regions / two inputs\r6  Three regions / two inputs\r"
    "7  Title / special input / body\r8  Line selection\r9  Variant of 8\r"
    "11  Title / 40:60 columns\r12  Letter choices\r13  Title and body\r"
    "14  Underlined text input\r15  Editable text input\r"
    "16  Main / two lower regions\r17  Main letter choice\r18  Variant of 8\r"
    "19  Equal columns\r20  Titled columns\r21  Choice / text columns";
/* Exported only for deterministic local message/ROM-contract testing. */
FontDialog_t* demo_dialog;
uint8_t demo_index, demo_in_layout, demo_menu;
static char title[48];
static char bodies[5][64];
static bool supported;

static void release_dialog(void) {
    if(demo_dialog) FontDialogDestroy(demo_dialog);
    demo_dialog = 0;
}

static void selector(void) {
    release_dialog();
    demo_in_layout = 0;
    ClearScreen();
    SetCursorMode(CURSOR_MODE_HIDE);
    demo_dialog = FontDialogCreate(FONT_DIALOG_LAYOUT_13);
    if(!demo_dialog) return;
    FontDialogActivate(demo_dialog, 0);
    FontDialogActivate(0, 0); /* Reused pool addresses do not reselect automatically. */
    FontDialogSetProperty(demo_dialog, 0, FONT_DIALOG_SELECT_ITEMS, true);
    FontDialogUpdate(demo_dialog, 0, "Font dialogs: Up/Down, Enter", "", selector_body, 0, 0);
    FontDialogSetSelection(demo_index);
    FontDialogDrawRegion(demo_dialog, 0);
}

static void set_menu(void) {
    const Layout* l = &layouts[demo_index];
    for(uint8_t r=0; r<l->count; ++r) {
        if(!(l->body_mask & (1<<r))) continue;
        FontDialogActivate(0, r);
        FontDialogSetProperty(demo_dialog, r, FONT_DIALOG_SELECT_ITEMS, demo_menu);
        FontDialogSetSelection(demo_menu ? 1 : 0);
        FontDialogDrawRegion(demo_dialog, r);
    }
    FontDialogActivate(0, 0);
}

static void open_layout(void) {
    const Layout* l = &layouts[demo_index];
    release_dialog();
    ClearScreen();
    SetCursorMode(CURSOR_MODE_HIDE);
    demo_dialog = FontDialogCreate((FontDialogLayout_e)l->id);
    if(!demo_dialog) { selector(); return; }
    demo_in_layout = 1;
    FontDialogActivate(demo_dialog, 0);
    FontDialogActivate(0, 0); /* Reused pool addresses do not reselect automatically. */
    sprintf(title, "Layout %u: Esc=back Ctrl+M=menu", (unsigned)l->id);
    for(uint8_t r=0; r<l->count; ++r) {
        /* Borrowed text needs distinct persistent storage for each region. */
        strcpy(bodies[r], (l->body_mask & (1<<r)) ? "Alpha\rBeta\rGamma" : "");
        const char* input = l->kinds[r]==5 ? 0 :
            l->kinds[r]==4 ? "Pick: @A  #B  @C" :
            l->id==5 || l->id==6 ? (r==1 ? "First:" : "Last:") : "Name:";
        FontDialogUpdate(demo_dialog, r, r==0 ? title : "Options", "", bodies[r], input, 0);
        /* The numeric/multiple-answer state format is not a public text prompt.
           Keep its empty editor inactive rather than pass a NULL editor to keys. */
        if(l->kinds[r]==5)
            FontDialogSetProperty(demo_dialog, r, FONT_DIALOG_ENABLE_INPUT, false);
    }
    demo_menu = 1;
    set_menu();
}

void ProcessMessage(Message_e message, uint32_t param, uint32_t* status) {
    *status = 0;
    if(message == MSG_INIT) {
        uint32_t hw=0;
        FirmwareVersion_t version={0};
        CallSysInt(0, SYS_INT_GET_HW_LEVEL, &hw);
        supported = hw>=2 && CallSysInt(0, SYS_INT_GET_FIRMWARE_VERSION, &version)
            && version.major==3 && version.minor==21;
        demo_dialog=0; demo_index=0; demo_in_layout=0; demo_menu=0;
    } else if(message == MSG_SETFOCUS) {
        if(supported) selector();
        else { ClearScreen(); PutString("Requires Neo System 3.21"); }
    } else if(message == MSG_KILLFOCUS) {
        release_dialog();
    } else if(supported && demo_dialog && message == MSG_CHAR) {
        if(GetKeyModifiers() & (KEY_MOD_CTRL|KEY_MOD_CMD|KEY_MOD_ALT)) return;
        if(!demo_in_layout) {
            if(param=='\r') open_layout();
        } else if(param!='\r') FontDialogHandleKey((uint16_t)param);
    } else if(supported && demo_dialog && message == MSG_KEY && !(param & KEY_MOD_KEY_UP)) {
        uint8_t key = param & 0x7f;
        if(!demo_in_layout) {
            if(key==KEY_UP && demo_index) --demo_index;
            else if(key==KEY_DOWN && demo_index<15) ++demo_index;
            else return;
            FontDialogSetSelection(demo_index);
            FontDialogDrawRegion(demo_dialog, 0);
        } else if(key==KEY_ESC) selector();
        else if((param & KEY_MOD_CTRL) && key==KEY_M) {
            demo_menu = !demo_menu; set_menu();
        } else if(key==KEY_UP || key==KEY_DOWN || key==KEY_LEFT || key==KEY_RIGHT)
            FontDialogHandleKey(KEY_MOD_CTRL | key);
        else if(key==KEY_BACKSPACE) FontDialogHandleKey(KEY_MOD_CTRL | KEY_BACKSPACE);
    } else if(supported && demo_dialog && message==MSG_IDLE) {
        FontDialogUpdateAnimations(0);
    }
}
