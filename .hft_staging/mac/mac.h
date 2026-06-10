/* mac.h — the 125 MHz MAC sample clock: starter interface.
 *
 * MAC is the NIC's sample RATE (a separate clock from TAI). The device logic
 * lives in the GENERATED mac_gen.h (netlist -> gennet); this header is only the
 * host starter glue — no _tick, no cell_*() here. (build-sequence law) */
#ifndef MAC_H
#define MAC_H

#include "mac_gen.h"

/* mac_start: power on the MAC clock, set the configured run bound, run the
 * self-oscillating clock to that bound, return the register window for display. */
const word_t *mac_start(word_t run_until);

#endif /* MAC_H */
