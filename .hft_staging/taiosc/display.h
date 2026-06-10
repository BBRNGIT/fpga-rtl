/* display.h — EXTERNAL display. Reads the taisoc register lanes RAW and prints
 * them. NO logic: no compute, no reformat, no reshape — it shows what the
 * addressed memory holds. Off-clock, non-blocking. Not a device, not a netlist.
 * (feedback_hft_display_rule) */
#ifndef TAISOC_DISPLAY_H
#define TAISOC_DISPLAY_H

#include "taisoc_gen.h"

/* display_show: scan the taisoc lanes and print them exactly as the addressed
 * memory holds them (POWER, CYCLE, EDGE, RUN_UNTIL). Pure read + print. */
void display_show(const word_t *r);

#endif /* TAISOC_DISPLAY_H */
