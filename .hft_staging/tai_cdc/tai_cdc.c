/* tai_cdc.c — the STARTER. One job: power on the CDC synchronizer and step away.
 * The generated netlist (tai_cdc_gen.h) owns the data path; the canonical loop
 * (tai_cdc_run) self-runs on the MAC edge from the power bit until the configured
 * tick budget. Contains NO _tick and NO cell_*() (build-sequence law).
 *
 * TAI_IN is presented as starter config (the source-domain sample the
 * synchronizer carries across) — not test-time injection into the data path. */
#include "tai_cdc_gen.h"
#include "tai_cdc.h"

/* the tai_cdc device's register window (its address space). Single instance. */
static word_t g_tai_cdc_regs[TAI_CDC_REG_COUNT];

const word_t *tai_cdc_start(word_t tai_in, word_t run_until) {
    tai_cdc_init(g_tai_cdc_regs);                          /* reset: all zero */
    g_tai_cdc_regs[TAI_CDC_TAI_IN]            = tai_in;    /* sampled source value */
    g_tai_cdc_regs[TAI_CDC_TAI_CDC_RUN_UNTIL] = run_until; /* configured tick budget */
    g_tai_cdc_regs[TAI_CDC_TAI_CDC_POWER]     = 1ULL;      /* power on — sync self-runs */
    tai_cdc_run(g_tai_cdc_regs);
    return g_tai_cdc_regs;
}
