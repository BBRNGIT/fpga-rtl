/* internal.c — the STARTER. One job: power on the pipeline metronome and step
 * away. The generated netlist (internal_gen.h) owns the data path; the canonical
 * clock (internal_run) self-oscillates from the power bit until the configured
 * run bound. Contains NO _tick and NO cell_*() (build-sequence law). */
#include "internal_gen.h"
#include "internal.h"

/* the internal device's register window (its address space). Single instance. */
static word_t g_internal_regs[INTERNAL_REG_COUNT];

const word_t *internal_start(word_t run_until) {
    internal_init(g_internal_regs);                          /* reset: all zero */
    g_internal_regs[INTERNAL_INTERNAL_RUN_UNTIL] = run_until;
    g_internal_regs[INTERNAL_INTERNAL_POWER]     = 1ULL;     /* power on — self-runs */
    internal_run(g_internal_regs);
    return g_internal_regs;
}
