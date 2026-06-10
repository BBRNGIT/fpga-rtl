/* display.c — external display: scan the tai_cdc lanes RAW and print them. NO
 * logic. (feedback_hft_display_rule) */
#include <stdio.h>
#include "tai_cdc_gen.h"
#include "display.h"

void display_show(const word_t *r) {
    printf("tai_cdc  (gray-code 2-FF synchronizer — TAI value into the MAC domain)\n");
    printf("  POWER    TICKS      TAI_IN        SYNC1        SYNC2      TAI_MAC\n");
    printf("  %5llu  %7llu  %10llu  %11llu  %11llu  %11llu\n",
           (unsigned long long)r[TAI_CDC_TAI_CDC_POWER],
           (unsigned long long)r[TAI_CDC_TAI_CDC_TICKS],
           (unsigned long long)r[TAI_CDC_TAI_IN],
           (unsigned long long)r[TAI_CDC_TAI_SYNC1_GRAY],
           (unsigned long long)r[TAI_CDC_TAI_SYNC2_GRAY],
           (unsigned long long)r[TAI_CDC_TAI_MAC]);
}
