#include "os3k.h"
#include "FormatBench.h"
#include "BenchData.h"

APPLET_HEADER_BEGIN
    APPLET_ID(0xFF25)
    APPLET_NAME("Format Bench")
    APPLET_INFO("Disposable formatting CPU benchmark")
    APPLET_VERSION(0, 1, "b")
    APPLET_LANGUAGE_EN_US
APPLET_HEADER_END

typedef struct {
    uint32_t milliseconds, hash, bytes, atoms, headings, error;
} BenchCell;
volatile struct {
    uint32_t magic, started, done, error, current_case, current_variant, repetitions;
    BenchCell cells[BENCH_CASE_COUNT * BENCH_VARIANT_COUNT];
} g_bench;

void ProcessMessage(Message_e message, uint32_t parameter, uint32_t* reply) {
    unsigned c, i, repeat;
    BenchResult result;
    (void)parameter;
    *reply = 0;
    if(message == MSG_SETFOCUS) g_bench.magic = 0x464D5442;
    if(message != MSG_IDLE || g_bench.started) return;
    g_bench.started = 1;
    g_bench.repetitions = 4;
    for(c = 0; c < BENCH_CASE_COUNT; ++c) {
        for(i = 0; i < BENCH_VARIANT_COUNT; ++i) {
            const BenchVariant* v = BenchVariants + i;
            volatile BenchCell* cell = g_bench.cells + c * BENCH_VARIANT_COUNT + i;
            uint32_t start;
            g_bench.current_case = c;
            g_bench.current_variant = i;
            start = GetUptimeMilliseconds();
            for(repeat = 0; repeat < g_bench.repetitions; ++repeat) {
                if(!BenchFormatChapter(BenchResources + v->asset, BenchCases + c, v->mode, v->headings, &result)) {
                    g_bench.error = result.error;
                    g_bench.done = 1;
                    return;
                }
            }
            cell->milliseconds = GetUptimeMilliseconds() - start;
            cell->hash = result.hash;
            cell->bytes = result.bytes;
            cell->atoms = result.atoms;
            cell->headings = result.headings;
            cell->error = result.error;
        }
    }
    g_bench.done = 1;
}
