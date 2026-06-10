/* internal.h — the 250 MHz pipeline metronome: starter interface.
 *
 * The device logic lives in the GENERATED internal_gen.h (netlist -> gennet);
 * this header is only the host starter glue — no _tick, no cell_*() here.
 * (build-sequence law) */
#ifndef INTERNAL_H
#define INTERNAL_H

#include "internal_gen.h"

/* internal_start: power on the metronome, set the run bound, run the
 * self-oscillating clock to the bound, return the register window. */
const word_t *internal_start(word_t run_until);

#endif /* INTERNAL_H */
