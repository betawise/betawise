"""Add test-only CPU timing boundaries without changing release images."""


def instrument(text):
    wrappers = '''
#if BIBLEWISE_TEST
static int32_t ProfileEditorMessage(TextEditor_t* editor, Message_e message,
    uint32_t parameter, uint32_t context, int32_t* status) {
    if(message!=MSG_KEY && message!=MSG_REFRESH)
        return TextEditorHandleMessage(editor,message,parameter,context,status);
    ReaderProbeSet(phase,message==MSG_KEY?800:802);
    int32_t result=TextEditorHandleMessage(editor,message,parameter,context,status);
    ReaderProbeSet(phase,message==MSG_KEY?801:803);
    return result;
}
static int32_t ProfileScanPosition(TextScan_t* scan, bool draw) {
    ReaderProbeSet(phase,804);
    int32_t result=TextEditorSetScanPosition(scan,draw);
    ReaderProbeSet(phase,805);
    return result;
}
static int32_t ProfileSavePosition(TextEditor_t* editor) {
    ReaderProbeSet(phase,806);
    int32_t result=TextEditorSavePosition(editor);
    ReaderProbeSet(phase,807);
    return result;
}
static int32_t ProfileEditorRefresh(TextEditor_t* editor) {
    ReaderProbeSet(phase,814);
    int32_t result=TextEditorRefresh(editor);
    ReaderProbeSet(phase,815);
    return result;
}
#define TextEditorHandleMessage ProfileEditorMessage
#define TextEditorSetScanPosition ProfileScanPosition
#define TextEditorSavePosition ProfileSavePosition
#define TextEditorRefresh ProfileEditorRefresh
#endif
'''
    text = text.replace('#include <string.h>', '#include <string.h>\n'+wrappers)
    marker = 'static int AppendChapterBytes('
    wrapper = '''#if BIBLEWISE_TEST
static int32_t ProfileReadingFonts(void) {
    ReaderProbeSet(phase,820);
    int32_t result=SetReadingFonts();
    ReaderProbeSet(phase,821);
    return result;
}
#define SetReadingFonts ProfileReadingFonts
#endif

'''
    text = text.replace(marker, wrapper+marker)
    text = text.replace('    /* Research: preserve the ROM', '    ReaderProbeSet(phase,808);\n    /* Research: preserve the ROM')
    text = text.replace('    g_editor.selection_state=old.selection_state;\n    RedrawChapterWithMode',
        '    g_editor.selection_state=old.selection_state;\n    ReaderProbeSet(phase,809);\n    RedrawChapterWithMode')
    text = text.replace('static void SaveReadingPosition(void) {',
        'static void SaveReadingPosition(void) {\n    ReaderProbeSet(phase,816);')
    text = text.replace('    ReaderProbeSet(phase, 16);', '    ReaderProbeSet(phase, 817);\n    ReaderProbeSet(phase, 16);')
    return text
