/* adapter.c — the STARTER. It does exactly one job: power on the adapter device
 * and step away. It owns nothing of the data path — the generated netlist owns
 * that, and the canonical clock (adapter_run) self-oscillates from the power bit
 * until the buffer is exhausted. No main() the modules slave to.
 *
 * adapter_start(): load records (buffer), set per-source static config, set the
 * power bit, run the free-running clock, return the register window for display.
 * The thin test calls this and then displays — nothing else. */
#include "adapter_gen.h"
#include "adapter.h"

/* the adapter device's register window (its address space). Single instance. */
static word_t g_adp_regs[ADP_REG_COUNT];

/* the WIRE BUS the adapter drives — the passive addressed-memory window the
 * adapter deposits into and the NIC samples. The adapter is its sole writer.
 * Lane map comes from the wire's canonical seam header (wire_gen.h, generated
 * from ../wire/wire.net.json — single source); the wire tree owns the canonical
 * passive bus. A lane needs an address — this storage IS the wire window. */
static wire_word_t g_wire_bus[WIRE_REG_COUNT];

const uint64_t *adapter_start(const char *record_path,
                              uint64_t symbol, uint64_t pip, uint64_t commission,
                              uint64_t speed) {
    adapter_init(g_adp_regs);                 /* synchronous reset: all zero */
    buffer_load(record_path);                 /* buffer holds the records */

    /* per-source static config (set by the connector/starter, not data path). */
    g_adp_regs[ADP_WIRE_SYMBOL]     = symbol;
    g_adp_regs[ADP_WIRE_PIP]        = pip;
    g_adp_regs[ADP_WIRE_COMMISSION] = commission;
    g_adp_regs[ADP_SPEED]           = speed;   /* real-world-clock rate scale */

    /* power on — the clock self-runs in its own loop, depositing each emitted
     * packet into the wire bus; then we step away. */
    g_adp_regs[ADP_ADP_POWER] = 1ULL;
    adapter_run(g_adp_regs, g_wire_bus);

    return g_adp_regs;
}

const uint64_t *adapter_wire_bus(void) {
    /* the wire bus the adapter drove (1-deep: the latest deposited packet — the
     * value the NIC would sample). Read-only to the consumer (the adapter is the
     * sole writer). */
    return g_wire_bus;
}
