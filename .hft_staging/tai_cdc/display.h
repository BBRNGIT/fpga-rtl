/* display.h — EXTERNAL display. Reads the tai_cdc register lanes RAW and prints
 * them. NO logic. Off-clock, non-blocking. (feedback_hft_display_rule) */
#ifndef TAI_CDC_DISPLAY_H
#define TAI_CDC_DISPLAY_H

#include "tai_cdc_gen.h"

/* display_show: print the tai_cdc lanes exactly as the addressed memory holds
 * them (POWER, TICKS, TAI_IN, SYNC1, SYNC2, TAI_MAC). Pure read + print. */
void display_show(const word_t *r);

#endif /* TAI_CDC_DISPLAY_H */
