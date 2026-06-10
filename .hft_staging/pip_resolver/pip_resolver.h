/* pip_resolver.h — the PIP_RESOLVER lookup device: starter interface.
 *
 * The device logic lives in the GENERATED pip_resolver_gen.h (netlist -> gennet);
 * this header is only the host starter glue — NO _tick, NO cell_*() here
 * (build-sequence law).
 *
 * The PIP_RESOLVER samples the NIC seam's SEAM_SYMBOL/SEAM_VALID lanes, indexes a
 * static per-symbol pip-config table by the symbol address (symbol*8 bytes = the
 * symbol-th 64-bit slot), and publishes the resolved pip value on
 * PIP_RESOLUTION_REG. (SPEC_REGISTERS.md s3/s4 — the unified Y-axis resolution
 * authority.) */
#ifndef PIP_RESOLVER_H
#define PIP_RESOLVER_H

#include "pip_resolver_gen.h"

/* The static per-symbol pip-config table the starter loads ONCE before power-on
 * (config-only; the device only reads it). Entry i = the pip resolution for
 * symbol i. Up to PIP_TABLE_DEPTH entries are loaded; the rest stay 0. */
typedef struct {
    uint64_t pip[PIP_TABLE_DEPTH];   /* pip[i] = resolution for symbol i */
    uint64_t count;                  /* number of valid entries (<= PIP_TABLE_DEPTH) */
} pip_config_table_t;

/* pip_resolver_start: load the static pip-config table, power the device on,
 * present a NIC-seam symbol (the value the NIC seam would expose), let the device
 * self-run for a window, and return the device register window for an external
 * display. The presented symbol + valid are the NIC's published seam lanes the
 * PIP_RESOLVER samples — NOT data-path injection (it sets the sampled input lanes
 * the device reads, exactly as the NIC samples the wire bus).
 *
 * Returns the device register window (output + status lanes) for display. */
const uint64_t *pip_resolver_start(const pip_config_table_t *cfg,
                                   uint64_t seam_symbol,
                                   uint64_t seam_valid,
                                   uint64_t run_until);

/* pip_resolver_out: the device output window (the PIP_* lanes). The latest
 * resolved pip value (PIP_RESOLUTION_REG) — the value the spatial grid / DOM /
 * footprint / tpo would read. The PIP_RESOLVER is the sole writer; this is the
 * consumer's read-only view. */
const uint64_t *pip_resolver_out(void);

#endif /* PIP_RESOLVER_H */
