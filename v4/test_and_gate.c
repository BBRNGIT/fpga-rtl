/*
 * test_and_gate.c — Minimal test: AND gate using real components from components.h
 *
 * Goal: Prove that verilog.h macros instantiate real hardware primitives,
 * not just text copies.
 *
 * Test: AND(A, B) -> Y should give:
 *   A=0, B=0 -> Y=0
 *   A=0, B=1 -> Y=0
 *   A=1, B=0 -> Y=0
 *   A=1, B=1 -> Y=1
 */

#include "lib/components.h"
#include <stdio.h>
#include <assert.h>

/* Simple AND gate cell: instantiates real components, settles them, tests output */
void test_and_gate() {
    printf("\n=== AND Gate Test (Real Components) ===\n");

    /* Allocate internal wires */
    wire_t A_in, B_in, Y_out;

    /* Allocate AND gate component (from components.h) */
    and_t and_gate;

    /* Wire the AND gate: connect A, B inputs and Y output */
    wire_and(&and_gate, &A_in, &B_in, &Y_out);

    /* Test cases */
    struct { int a, b, expected; } tests[] = {
        { 0, 0, 0 },
        { 0, 1, 0 },
        { 1, 0, 0 },
        { 1, 1, 1 },
    };

    for (int i = 0; i < 4; i++) {
        int a = tests[i].a;
        int b = tests[i].b;
        int expected = tests[i].expected;

        /* Drive inputs */
        A_in.level = (a ? HI : LO);
        B_in.level = (b ? HI : LO);

        /* Settle the gate (propagate signals through NAND components) */
        and_settle(&and_gate);

        /* Check output */
        int result = (Y_out.level == HI) ? 1 : 0;
        printf("  AND(%d, %d) = %d (expected %d) %s\n",
               a, b, result, expected,
               result == expected ? "✓" : "✗");
        assert(result == expected && "AND gate test failed");
    }

    printf("✓ All AND gate tests passed (real components working)\n");
}

int main() {
    test_and_gate();
    return 0;
}
