#ifndef BIBLEWISE_PROBE_H
#define BIBLEWISE_PROBE_H

/* Test-only RAM observability. Never included in a production applet. The Lua
 * harness reads these records; it does not call into or drive the reader. */
#if BIBLEWISE_TEST
volatile struct {
    uint32_t magic, serial, phase, error, chapter, verse, bytes;
    uint32_t mode, searching, hits, copied, numbered, word, status;
    uint32_t sidebar_draws, chapter_decodes;
    uint32_t rebuild_bytes, rebuild_ok;
} g_reader;
volatile struct {
    uint32_t calls, status, position, chapter, numbered;
} g_saved;

#define ReaderProbeSet(field, value) (g_reader.field = (value))
#define ReaderProbeAdd(field, value) (g_reader.field += (value))

/* Observe actual allocator movement during clipboard operations. No mutation is
 * injected here: the test must make the normal firmware allocator move it. */
volatile struct {
    uint32_t writes, moves, initial, last, before, after, first_before, first_after;
} g_copy_probe;

static void ReaderProbeCopyBegin(void) {
    memset((void*)&g_copy_probe, 0, sizeof(g_copy_probe));
    g_copy_probe.initial = (uintptr_t)FileBindState(1, NULL, NULL, NULL, NULL);
}

static void ReaderProbeCopyWrite(bool after) {
    uint32_t address = (uintptr_t)FileBindState(1, NULL, NULL, NULL, NULL);
    if(!after) g_copy_probe.before = address;
    else {
        g_copy_probe.after = g_copy_probe.last = address;
        ++g_copy_probe.writes;
        if(address != g_copy_probe.before) {
            if(!g_copy_probe.moves) {
                g_copy_probe.first_before = g_copy_probe.before;
                g_copy_probe.first_after = address;
            }
            ++g_copy_probe.moves;
        }
    }
}

static void ReaderProbeSavedPosition(int32_t status, unsigned chapter, unsigned numbered) {
    g_saved.status = status;
    g_saved.position = FileTell(1);
    g_saved.chapter = chapter;
    g_saved.numbered = numbered;
    ++g_saved.calls;
}

static void ReaderProbeSelectSystemFont(void) {
#ifdef BIBLEWISE_TEST_SYSTEM_FONT_PICKER
    /* Pinned Neo 3.21's original picker. Confirmation uses normal firmware
     * preference/cache updates; the harness supplies ordinary End/Enter keys. */
    ((void (*)(void))(uintptr_t)0x42284e)();
#endif
}

static int ReaderProbeConfigureFonts(FontHeader_t** fonts) {
#ifdef BIBLEWISE_TEST_FONT_ID
    static unsigned applied;
    if(!applied) {
        uint8_t applet = AppletFindById(BIBLEWISE_TEST_FONT_ID);
        FontHeader_t* font = 0;
        uint32_t reply = 0;
        if(applet) {
            AppletSendMessage(applet, MSG_FONT_GET_NORMAL, (uint32_t)&font, &reply);
        }
        if(!font) {
            return 0;
        }
        fonts[0] = fonts[1] = fonts[2] = font;
        applied = 1;
    }
#else
    (void)fonts;
#endif
    return 1;
}
#else
#define ReaderProbeCopyBegin() ((void)0)
#define ReaderProbeCopyWrite(after) ((void)0)
#define ReaderProbeSet(field, value) ((void)0)
#define ReaderProbeAdd(field, value) ((void)0)
#define ReaderProbeSavedPosition(status, chapter, numbered) ((void)0)
#define ReaderProbeConfigureFonts(fonts) 1
#endif

#endif
