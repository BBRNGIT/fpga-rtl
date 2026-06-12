/* test_dom_bus.c — thin test: power-on (zero) + deposit a couple lanes + display.
 * dom_bus is a passive barrier bus; the testbench acts as the producer depositing. */
#include <stdio.h>
#include "dom_bus_gen.h"

int main(void) {
    dom_bus_word_t b[DOM_BUS_REG_COUNT];
    dom_bus_init(b);
    b[DOM_BUS_DOMBUS_BID_ACT_2] = 5u;
    b[DOM_BUS_DOMBUS_BEST_BID]  = 47068000u;
    b[DOM_BUS_DOMBUS_VALID]     = 1u;
    printf("dom_bus lanes=%u | bid_act[2]=%llu best_bid=%llu valid=%llu\n",
           DOM_BUS_REG_COUNT,
           (unsigned long long)b[DOM_BUS_DOMBUS_BID_ACT_2],
           (unsigned long long)b[DOM_BUS_DOMBUS_BEST_BID],
           (unsigned long long)b[DOM_BUS_DOMBUS_VALID]);
    return 0;
}
