/* test_harness.c — thin test: master power on + run + display power lanes.
 * Proves the sequenced power-up: control@0, in@4, main@8, bounded by RUN_UNTIL. */
#include <stdio.h>
#include "harness_gen.h"

int main(void) {
    word_t r[HARNESS_REG_COUNT] = {0};
    harness_init(r);
    r[HARNESS_HARNESS_POWER] = 1u;          /* master ON — the only external act */
    for (int t = 0; t < 6; t++) harness_tick(r);
    printf("t=6 : control=%llu in=%llu main=%llu (seq=%llu)\n",
           (unsigned long long)r[HARNESS_HARNESS_PWR_FPGA_CONTROL],
           (unsigned long long)r[HARNESS_HARNESS_PWR_FPGA_IN],
           (unsigned long long)r[HARNESS_HARNESS_PWR_FPGA_MAIN],
           (unsigned long long)r[HARNESS_HARNESS_SEQ]);
    for (int t = 0; t < 6; t++) harness_tick(r);
    printf("t=12: control=%llu in=%llu main=%llu\n",
           (unsigned long long)r[HARNESS_HARNESS_PWR_FPGA_CONTROL],
           (unsigned long long)r[HARNESS_HARNESS_PWR_FPGA_IN],
           (unsigned long long)r[HARNESS_HARNESS_PWR_FPGA_MAIN]);
    r[HARNESS_HARNESS_POWER] = 0u;          /* master OFF — everything drops */
    harness_tick(r);
    printf("off : control=%llu in=%llu main=%llu\n",
           (unsigned long long)r[HARNESS_HARNESS_PWR_FPGA_CONTROL],
           (unsigned long long)r[HARNESS_HARNESS_PWR_FPGA_IN],
           (unsigned long long)r[HARNESS_HARNESS_PWR_FPGA_MAIN]);
    return 0;
}
