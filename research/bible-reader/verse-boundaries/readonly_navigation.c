/* Original-ROM state probe, appended to the typed SDK probe. */
static unsigned LogicalOffset(TextEditor_t* editor, unsigned raw) {
    if(raw >= editor->gap_end) return raw - (editor->gap_end - editor->gap_start);
    return raw > editor->gap_start ? editor->gap_start : raw;
}
static void NavigationProbe(unsigned mode) {
    const unsigned keys[]={KEY_RIGHT,KEY_DOWN,KEY_LEFT,KEY_UP,
        KEY_MOD_CMD|KEY_DOWN,KEY_MOD_CMD|KEY_UP,
        KEY_MOD_LEFTSHIFT|KEY_RIGHT,KEY_MOD_LEFTSHIFT|KEY_RIGHT,
        KEY_MOD_LEFTSHIFT|KEY_LEFT,KEY_RIGHT,
        KEY_MOD_LEFTSHIFT|KEY_DOWN,KEY_MOD_LEFTSHIFT|KEY_DOWN,
        KEY_MOD_LEFTSHIFT|KEY_UP,KEY_LEFT,
        KEY_HOME,KEY_END,KEY_MOD_CMD|KEY_LEFT,KEY_MOD_CMD|KEY_RIGHT,
        KEY_MOD_LEFTSHIFT|KEY_HOME,KEY_MOD_LEFTSHIFT|KEY_END,
        KEY_MOD_LEFTSHIFT|KEY_MOD_CMD|KEY_DOWN,KEY_MOD_LEFTSHIFT|KEY_MOD_CMD|KEY_UP};
    unsigned index;
    OUT[0]=0;
    {
        TextEditor_t editor;
        int32_t status=0;
        CHECK(201,FileOpen(1,FILE_OPEN_REWIND)>=0);
        CHECK(205,TextEditorInit(&editor,1,mode?TEXT_EDITOR_EDITABLE:TEXT_EDITOR_READ_ONLY,
            1000,0,0,40,4)==0);
        CHECK(208,FileOpen(1,FILE_OPEN_KEEP_POSITION)>=0);
        for(index=0;index<sizeof(keys)/sizeof(keys[0]);++index) {
            /* Test extended shortcuts independently from the same location,
             * so one unsupported key cannot contaminate later results. */
            if(index>=14) {
                CHECK(206,FileOpen(1,FILE_OPEN_REWIND)>=0);
                CHECK(207,TextEditorInit(&editor,1,mode?TEXT_EDITOR_EDITABLE:TEXT_EDITOR_READ_ONLY,
                    1000,0,0,40,4)==0);
                CHECK(209,FileOpen(1,FILE_OPEN_KEEP_POSITION)>=0);
                TextEditorHandleMessage(&editor,MSG_KEY,KEY_RIGHT,0,&status);
                TextEditorHandleMessage(&editor,MSG_KEY,KEY_DOWN,0,&status);
            }
            unsigned consumed=TextEditorHandleMessage(&editor,MSG_KEY,keys[index],0,&status);
            volatile uint32_t* row=OUT+1+index*9;
            row[0]=LogicalOffset(&editor,editor.caret_offset);
            row[1]=LogicalOffset(&editor,editor.selection_anchor);
            row[2]=editor.selection_state;
            row[3]=LogicalOffset(&editor,editor.viewport_offset);
            row[4]=editor.caret_x;row[5]=editor.caret_y;
            row[6]=editor.gap_end-editor.gap_start;
            row[7]=status;row[8]=consumed;
        }
    }
    OUT[0]=0x70617373;
}

void typed_readonly_nav(void) { NavigationProbe(0); }
void typed_editable_nav(void) { NavigationProbe(1); }
