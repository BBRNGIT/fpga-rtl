/* taisoc.h — the taisoc oscillator-reference clock: starter interface.
 *
 * taisoc is the TAI rate reference: a free-running counter that emits one edge
 * strobe per powered tick (tai counts the strobe). The device logic lives in
 * the GENERATED taisoc_gen.h (netlist -> gennet); this header is only the host
 * starter glue — no _tick, no cell_*() here. (build-sequence law)
 *
 *   - single writer = taisoc_tick() (generated): CYCLE + EDGE.
 *   - readers = tai (counts TAISOC_EDGE); external probe/display (read-only).
 *   - the clock self-runs from the power bit, bounded by a configured stop count
 *     (run_until) — nothing external steps it. */
#ifndef TAISOC_H
#define TAISOC_H

#include "taisoc_gen.h"

/* taisoc_start: power on the oscillator, set the configured run bound, run the
 * self-oscillating clock to that bound, and return the register window for the
 * external display. The thin test calls this and then displays — nothing else. */
const word_t *taisoc_start(word_t run_until);

#endif /* TAISOC_H */
