/* tai_cdc.h — the TAI clock-domain crossing (gray-code 2-FF sync): starter
 * interface. Brings the TAI value into the MAC domain metastability-safe.
 *
 * The device logic lives in the GENERATED tai_cdc_gen.h (netlist -> gennet);
 * this header is only the host starter glue — no _tick, no cell_*() here.
 * (build-sequence law) */
#ifndef TAI_CDC_H
#define TAI_CDC_H

#include "tai_cdc_gen.h"

/* tai_cdc_start: power on the synchronizer, present a sampled TAI value on the
 * input lane, set the run budget, run the MAC-edge sync to the budget, and return
 * the register window for display. The thin test calls this and then displays. */
const word_t *tai_cdc_start(word_t tai_in, word_t run_until);

#endif /* TAI_CDC_H */
