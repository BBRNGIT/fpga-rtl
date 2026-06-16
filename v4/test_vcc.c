/*
 * test_vcc.c — Test VCC component (constant HI source)
 *
 * VCC is a source component that always drives its output to logic 1.
 * This test verifies the component works correctly.
 */

#include "lib/components.h"
#include <stdio.h>
#include <assert.h>

int main() {
    printf("\n=== VCC Component Test ===\n");

    wire P;
    P.level = Z;  /* Initialize P to high-impedance (undriven) */

    printf("Before VCC: P.level = %d (Z)\n", P.level);

    /* Create VCC component and wire it to P */
    vcc v;
    wire_vcc(&v, &P);
    vcc_settle(&v);

    printf("After VCC.settle(): P.level = %d (HI)\n", P.level);

    /* Verify P is driven to HI */
    assert(P.level == HI && "VCC failed to drive P to HI");

    printf("✓ VCC component works correctly\n");
    printf("✓ VCC is a real source that drives to logic 1\n");
    printf("===========================\n\n");

    return 0;
}
