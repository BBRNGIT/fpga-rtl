/* display.h — EXTERNAL display. Reads the MAC register lanes RAW and prints them.
 * NO logic: no compute, no reformat. Off-clock, non-blocking. Not a device, not
 * a netlist. (feedback_hft_display_rule) */
#ifndef MAC_DISPLAY_H
#define MAC_DISPLAY_H

#include "mac_gen.h"

/* display_show: print the MAC lanes exactly as the addressed memory holds them
 * (POWER, CYCLE, EDGE, RUN_UNTIL). Pure read + print. */
void display_show(const word_t *r);

#endif /* MAC_DISPLAY_H */
