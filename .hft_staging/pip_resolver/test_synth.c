/* test_synth.c — THIN test: power on the PIP_RESOLVER, display its output. Nothing
 * else. No clock loop, no stepping, no orchestration, no data-path injection. The
 * device's own clock self-runs on the MAC edge from the power bit (inside the
 * starter); the display reads the output lanes raw. (test_harness_law)
 *
 * Two scenarios prove the lookup:
 *   sym 1 -> table[1]  : a valid symbol resolves to its configured pip value.
 *   sym 2 -> table[2]  : a different symbol resolves to a different pip value.
 * Both latch only because SEAM_VALID is presented high (a sampled symbol). */
#include <stdio.h>
#include "pip_resolver.h"
#include "display.h"

#define RUN_WINDOW  4ULL    /* mac-edge self-run budget */

int main(void) {
    /* static per-symbol pip-config table: symbol i -> pip[i] (config-only). */
    const pip_config_table_t cfg = {
        .pip = { 0ULL, 100000ULL, 10ULL, 5ULL }, .count = 4ULL };

    printf("=== PIP_RESOLVER lookup: symbol 1 (expect PIP_RESOLUTION_REG = table[1] = 100000) ===\n");
    display_show(pip_resolver_start(&cfg, 1ULL, 1ULL, RUN_WINDOW));

    printf("\n=== PIP_RESOLVER lookup: symbol 2 (expect PIP_RESOLUTION_REG = table[2] = 10) ===\n");
    display_show(pip_resolver_start(&cfg, 2ULL, 1ULL, RUN_WINDOW));
    return 0;
}
