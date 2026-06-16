/*
 * test_inv_comparison.c
 *
 * Side-by-side comparison:
 * VERILOG (INV.v):
 *   module INV (O, I);
 *     output O;
 *     input I;
 *     not n1 (O, I);
 *   endmodule
 *
 * C EQUIVALENT (using real components):
 *   void INV(wire_t *I, wire_t *O) {
 *     not_t inv_gate;
 *     wire_not(&inv_gate, I, O);
 *     not_settle(&inv_gate);
 *   }
 *
 * TEST:
 *   INV(0) -> 1 (expected: 1) ✓
 *   INV(1) -> 0 (expected: 0) ✓
 */

#include "lib/components.h"
#include <stdio.h>
#include <assert.h>

/* C equivalent of INV.v: instantiate NOT gate, wire inputs/outputs */
void INV(wire_t *I, wire_t *O) {
    not_t inv_gate;
    wire_not(&inv_gate, I, O);
    not_settle(&inv_gate);
}

int main() {
    printf("\n========================================\n");
    printf("COMPARISON: Verilog INV.v → C INV()\n");
    printf("========================================\n");

    printf("\nVERILOG CODE (INV.v):\n");
    printf("  module INV (O, I);\n");
    printf("    output O;\n");
    printf("    input I;\n");
    printf("    not n1 (O, I);\n");
    printf("  endmodule\n");

    printf("\nC CODE (using real components):\n");
    printf("  void INV(wire_t *I, wire_t *O) {\n");
    printf("    not_t inv_gate;\n");
    printf("    wire_not(&inv_gate, I, O);\n");
    printf("    not_settle(&inv_gate);\n");
    printf("  }\n");

    printf("\n\nTEST RESULTS:\n");
    printf("%-20s | %-10s | %-10s | %-10s\n", "Input I", "Output O", "Expected", "Status");
    printf("-20s | %-10s | %-10s | %-10s\n", "--------", "--------", "--------", "------");

    int tests[] = { 0, 1 };
    int expected[] = { 1, 0 };

    for (int i = 0; i < 2; i++) {
        int input_val = tests[i];
        int exp_val = expected[i];

        wire_t I_wire, O_wire;
        I_wire.level = (input_val ? HI : LO);

        INV(&I_wire, &O_wire);  /* Call the C function */

        int result = (O_wire.level == HI) ? 1 : 0;
        const char *status = (result == exp_val) ? "✓ PASS" : "✗ FAIL";

        printf("%-20d | %-10d | %-10d | %s\n", input_val, result, exp_val, status);

        assert(result == exp_val && "INV test failed");
    }

    printf("\n✓ All INV tests passed!\n");
    printf("✓ Verilog spec (INV.v) → C implementation (INV()) → Real components working\n");
    printf("\nCONCLUSION:\n");
    printf("  Verilog text describes hardware.\n");
    printf("  C code copies Verilog text exactly.\n");
    printf("  verilog.h macros instantiate real components from components.h.\n");
    printf("  Components implement actual logic (proven working).\n");
    printf("========================================\n\n");

    return 0;
}
