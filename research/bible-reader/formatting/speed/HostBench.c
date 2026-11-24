#define _POSIX_C_SOURCE 200809L
#include "FormatBench.h"
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <string.h>
#include "BenchData.h"

static double Now(void) {
    struct timespec ts;
    clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

int main(int argc, char** argv) {
    unsigned i, c, repeat, repetitions = argc > 1 ? atoi(argv[1]) : 100;
    BenchResult result;
    for(c = 0; c < BENCH_CASE_COUNT; ++c) {
        for(i = 0; i < BENCH_VARIANT_COUNT; ++i) {
            const BenchVariant* v = BenchVariants + i;
            double start = Now();
            for(repeat = 0; repeat < repetitions; ++repeat) {
                if(!BenchFormatChapter(BenchResources + v->asset, BenchCases + c, v->mode, v->headings, &result)) {
                    fprintf(stderr, "FAIL c=%u mode=%u line=%u\n", c, i, result.error);
                    return 1;
                }
            }
            printf("%u %u %.9f %u %u %u %u\n", c, i, (Now() - start) / repetitions,
                result.hash, result.bytes, result.atoms, result.headings);
        }
    }
    return 0;
}
