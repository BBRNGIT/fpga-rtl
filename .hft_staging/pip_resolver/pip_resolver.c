/* pip_resolver.c — the STARTER. One job: load the static pip-config table, power
 * the PIP_RESOLVER lookup on, and step away. The generated netlist
 * (pip_resolver_gen.h) owns the data path; the canonical loop (pip_resolver_run)
 * self-runs on the MAC edge from the power bit until the configured tick budget.
 * Contains NO _tick and NO cell_*() (build-sequence law).
 *
 * The NIC seam (SEAM_SYMBOL/SEAM_VALID) is presented on the device's read port
 * (the NIC window it samples) — not test-time injection into the data path. At
 * integration the live NIC seam window is sampled directly each mac edge; the
 * standalone starter presents a fixed symbol to demonstrate the lookup. The
 * pip-config table is config-only: the starter writes it ONCE before power-on. */
#include "pip_resolver_gen.h"
#include "pip_resolver.h"

/* the PIP_RESOLVER device's register window (its address space). Single instance. */
static word_t g_pip_regs[PIP_REG_COUNT];

/* the NIC seam window the PIP_RESOLVER SAMPLES (the NIC's published output lanes).
 * Lane map = nic_gen.h (generated from ../nic/nic.net.json — single source). The
 * PIP_RESOLVER is a read-only consumer of this window; the NIC is the sole writer
 * in the real system. */
static word_t g_nic_window[NIC_REG_COUNT];

/* load the static pip-config table into the device's config slots (config-only;
 * written ONCE before power-on, never in the tick). Entry i -> PIP_CFG_TABLE_i.
 * The address arithmetic is symbol*8 bytes = the symbol-th 64-bit slot; in the
 * word-array model that is slot index = symbol. */
static void load_config_table(const pip_config_table_t *cfg) {
    uint64_t i = 0ULL;
    for (i = 0ULL; i < PIP_TABLE_DEPTH; i = i + 1ULL) {
        const uint64_t v = (i < cfg->count) ? cfg->pip[i] : 0ULL;
        g_pip_regs[PIP_PIP_CFG_TABLE_0 + i] = v;
    }
}

const uint64_t *pip_resolver_start(const pip_config_table_t *cfg,
                                   uint64_t seam_symbol,
                                   uint64_t seam_valid,
                                   uint64_t run_until) {
    pip_resolver_init(g_pip_regs);                 /* synchronous reset: all zero */
    nic_init(g_nic_window);                         /* zero the presented NIC seam */

    /* load the static pip-config table ONCE (config-only; read-only in the tick). */
    load_config_table(cfg);

    /* present the NIC seam lanes the PIP_RESOLVER reads (the NIC's published
     * output window — the legitimate cross-module surface). */
    g_nic_window[NIC_SEAM_SYMBOL] = seam_symbol;
    g_nic_window[NIC_SEAM_VALID]  = seam_valid & 1ULL;

    /* configure the self-run budget, power on once — the clock self-runs in its
     * own loop (canonical clock primitive). */
    g_pip_regs[PIP_PIP_RUN_UNTIL] = run_until;
    g_pip_regs[PIP_PIP_POWER]     = 1ULL;

    pip_resolver_run(g_pip_regs, g_nic_window);
    return g_pip_regs;
}

const uint64_t *pip_resolver_out(void) {
    /* the device output window (1-deep: the latest resolved pip value — the value
     * the spatial grid / DOM / footprint / tpo would read). Read-only to the
     * consumer (the PIP_RESOLVER is the sole writer). */
    return g_pip_regs;
}
