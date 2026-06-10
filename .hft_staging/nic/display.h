/* display.h — external display for the NIC: scan the seam/status lanes RAW and
 * print them. NO logic, NO compute (feedback_hft_display_rule). */
#ifndef NIC_DISPLAY_H
#define NIC_DISPLAY_H

#include <stdint.h>

/* display_show: print the NIC seam + dedup status lanes (the re-stamped packet on
 * the nic->fifo seam, the strobe, and the dedup marker). Reads the register window
 * raw — no compute. */
void display_show(const uint64_t *r);

#endif /* NIC_DISPLAY_H */
