/* taisoc.c — the STARTER. One job: power on the taisoc oscillator and step away.
 * It owns nothing of the data path — the generated netlist (taisoc_gen.h) owns
 * that, and the canonical clock (taisoc_run) self-oscillates from the power bit
 * until the configured run bound is reached. No main() the modules slave to.
 *
 * Contains NO _tick and NO cell_*() — only host glue (build-sequence law). */
#include "taisoc_gen.h"
#include "taisoc.h"

/* the taisoc device's register window (its address space). Single instance. */
static word_t g_taisoc_regs[TAISOC_REG_COUNT];

const word_t *taisoc_start(word_t run_until) {
    taisoc_init(g_taisoc_regs);                       /* synchronous reset: all zero */

    /* configured run bound: the self-run stop count (set once by the starter).
     * The clock self-oscillates while CYCLE < this — config, not external steps. */
    g_taisoc_regs[TAISOC_TAISOC_RUN_UNTIL] = run_until;

    /* power on — the clock self-runs in its own loop, then we step away. */
    g_taisoc_regs[TAISOC_TAISOC_POWER] = 1ULL;
    taisoc_run(g_taisoc_regs);

    return g_taisoc_regs;
}
