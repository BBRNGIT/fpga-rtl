/* tai.h — the authoritative TAI timestamp counter: starter interface.
 *
 * tai is a PLAIN counter clocked by taisoc (no discipline). The device logic
 * lives in the GENERATED tai_gen.h (netlist -> gennet); this header is only the
 * host starter glue — no _tick, no cell_*() here. (build-sequence law) */
#ifndef TAI_H
#define TAI_H

#include "tai_gen.h"

/* tai_start: power on the counter, set the configured run bound, run the
 * self-oscillating clock to that bound, return the register window for display. */
const word_t *tai_start(word_t run_until);

#endif /* TAI_H */
