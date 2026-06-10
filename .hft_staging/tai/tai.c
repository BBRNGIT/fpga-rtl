/* tai.c — the STARTER. One job: power on the TAI counter and step away. The
 * generated netlist (tai_gen.h) owns the data path; the canonical clock (tai_run)
 * self-oscillates from the power bit (one tick per taisoc edge) until the
 * configured run bound. Contains NO _tick and NO cell_*() (build-sequence law). */
#include "tai_gen.h"
#include "tai.h"

/* the tai device's register window (its address space). Single instance. */
static word_t g_tai_regs[TAI_REG_COUNT];

const word_t *tai_start(word_t run_until) {
    tai_init(g_tai_regs);                     /* synchronous reset: all zero */
    g_tai_regs[TAI_TAI_RUN_UNTIL] = run_until;
    g_tai_regs[TAI_TAI_POWER]     = 1ULL;     /* power on — counts on taisoc edges */
    tai_run(g_tai_regs);
    return g_tai_regs;
}
