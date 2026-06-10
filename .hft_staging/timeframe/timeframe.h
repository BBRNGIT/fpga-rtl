/* timeframe.h — the bar-boundary clock authority: starter interface.
 *
 * timeframe is a pure-combinational rollover detector (SPEC_REGISTERS.md §2): when
 * (TAI - BAR_START) >= PERIOD it advances BAR_SEQ, pulses BAR_CLOSED, and re-anchors
 * BAR_START. The device logic lives in the GENERATED timeframe_gen.h (netlist ->
 * gennet); this header is only the host starter glue — no _tick, no cell_*() here.
 * (build-sequence law) */
#ifndef TIMEFRAME_H
#define TIMEFRAME_H

#include "timeframe_gen.h"

/* timeframe_start: power on the rollover detector, present the sampled TAI value and
 * configure the bar period + self-run tick budget, run the self-clocking loop to that
 * budget, return the register window for display. */
const word_t *timeframe_start(word_t period_ns, word_t tai_sample, word_t run_until);

#endif /* TIMEFRAME_H */
