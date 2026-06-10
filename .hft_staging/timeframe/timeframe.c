/* timeframe.c — the STARTER. One job: configure the bar period + present the sampled
 * TAI value, power on the rollover detector, and step away. The generated netlist
 * (timeframe_gen.h) owns the data path; the canonical clock (timeframe_run)
 * self-runs from the power bit, bounded by the configured tick budget. Contains NO
 * _tick and NO cell_*() (build-sequence law).
 *
 * Module barrier: TAI and PERIOD are PRESENTED on this device's own input lanes
 * (TF_TAI_IN, TF_PERIOD_NS); the starter wires the upstream published values onto
 * them at integration time — the device never reaches into another module. */
#include "timeframe_gen.h"
#include "timeframe.h"

/* the timeframe device's register window (its address space). Single instance. */
static word_t g_tf_regs[TIMEFRAME_REG_COUNT];

const word_t *timeframe_start(word_t period_ns, word_t tai_sample, word_t run_until) {
    timeframe_init(g_tf_regs);                           /* synchronous reset: all zero */
    g_tf_regs[TIMEFRAME_TF_PERIOD_NS] = period_ns;       /* operator config: bar period */
    g_tf_regs[TIMEFRAME_TF_TAI_IN]    = tai_sample;      /* presented sampled TAI value */
    g_tf_regs[TIMEFRAME_TF_RUN_UNTIL] = run_until;       /* configured self-run budget */
    g_tf_regs[TIMEFRAME_TF_POWER]     = 1ULL;            /* power on — rollover detect runs */
    timeframe_run(g_tf_regs);
    return g_tf_regs;
}
