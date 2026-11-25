#include "os3k.h"
#include <string.h>

APPLET_HEADER_BEGIN
    APPLET_ID(0xFF26)
    APPLET_NAME("SoftHyphen probe")
    APPLET_INFO("Native cached hyphen experiment")
    .fileCount = 1,
    APPLET_VERSION(0, 1, "a")
    APPLET_LANGUAGE_EN_US
APPLET_HEADER_END

static TextEditor_t g_editor;
volatile struct {
    uint32_t magic, serial, phase, error, chapter, verse, bytes;
    uint32_t mode, searching, hits, copied, numbered, word, status;
} g_reader;
static uint8_t g_file_bytes[64];
static unsigned g_case;

static void OpenCase(void) {
    const uint8_t* text = (const uint8_t*)(g_case < 2 ? "abcdefghij\xad" "klmnop" :
        g_case < 4 ? "abcdefghij-klmnop" : "abcdefghijklmnop");
    unsigned length = strlen((const char*)text);
    int32_t status;
    g_reader.phase = 1;
    FileClose();
    FileOpen(1, FILE_OPEN_REWIND);
    FileEraseCurrent();
    FileWriteBuffer(1, text, length, FILE_WRITE_APPEND);
    ClearScreen();
    status = TextEditorInit(&g_editor, 1, TEXT_EDITOR_EDITABLE, 4096, 0, 0,
        g_case & 1 ? 72 : 254, 64);
    if(!status) {
        TextScan_t scan;
        status = TextScanInit(&g_editor, &scan, TEXT_POSITION_START);
        if(!status) status = TextEditorSetScanPosition(&scan, true);
    }
    memset(g_file_bytes, 0, sizeof(g_file_bytes));
    FileSeek(1, g_editor.gap_end, FILE_SEEK_START);
    FileReadBuffer(1, g_file_bytes, sizeof(g_file_bytes));
    g_reader.magic = 0x42524452;
    g_reader.error = status;
    g_reader.chapter = g_case;
    g_reader.verse = 1;
    g_reader.bytes = length;
    g_reader.phase = 4;
    ++g_reader.serial;
}

void ProcessMessage(Message_e message, uint32_t parameter, uint32_t* reply) {
    *reply = 0;
    if(message == MSG_SETFOCUS) OpenCase();
    else if(message == MSG_KEY && !(parameter & KEY_MOD_KEY_UP) && (parameter & 0x7f) == KEY_DOWN) {
        g_case = (g_case + 1) % 6;
        OpenCase();
    }
}
