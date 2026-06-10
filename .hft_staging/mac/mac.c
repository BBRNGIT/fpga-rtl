/* mac.c — the STARTER. One job: power on the MAC clock and step away. It owns
 * nothing of the data path — the generated netlist (mac_gen.h) owns that, and
 * the canonical clock (mac_run) self-oscillates from the power bit until the
 * configured run bound. Contains NO _tick and NO cell_*() (build-sequence law). */
#include "mac_gen.h"
#include "mac.h"

/* the MAC device's register window (its address space). Single instance. */
static word_t g_mac_regs[MAC_REG_COUNT];

const word_t *mac_start(word_t run_until) {
    mac_init(g_mac_regs);                       /* synchronous reset: all zero */
    g_mac_regs[MAC_MAC_RUN_UNTIL] = run_until;  /* configured self-run stop count */
    g_mac_regs[MAC_MAC_POWER]     = 1ULL;       /* power on — clock self-runs */
    mac_run(g_mac_regs);
    return g_mac_regs;
}
