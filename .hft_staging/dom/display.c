/* display.c — external display: scan the DOM best/derived/relay/counter lanes RAW
 * and print them. NO logic, NO compute (feedback_hft_display_rule). The lane
 * addresses are the generated DOM_* register names from dom_gen.h. */
#include <stdio.h>
#include "dom_gen.h"
#include "display.h"

void display_show(const uint64_t *r) {
    printf("dom  (order book — price-indexed tables depth %u, 10-level relay ladders)\n",
           DOM_TABLE_DEPTH);
    printf("  --- best of book ---\n");
    printf("  BEST_BID px=%llu qty=%llu | BEST_ASK px=%llu qty=%llu\n",
           (unsigned long long)r[DOM_DOM_BEST_BID_PRICE_REG],
           (unsigned long long)r[DOM_DOM_BEST_BID_QTY_REG],
           (unsigned long long)r[DOM_DOM_BEST_ASK_PRICE_REG],
           (unsigned long long)r[DOM_DOM_BEST_ASK_QTY_REG]);
    printf("  --- derived ---\n");
    printf("  SPREAD=%llu MID=%llu | TOTAL_BID_QTY=%llu TOTAL_ASK_QTY=%llu\n",
           (unsigned long long)r[DOM_DOM_SPREAD_REG],
           (unsigned long long)r[DOM_DOM_MID_PRICE_REG],
           (unsigned long long)r[DOM_DOM_TOTAL_BID_QTY_REG],
           (unsigned long long)r[DOM_DOM_TOTAL_ASK_QTY_REG]);
    printf("  --- counters ---\n");
    printf("  PKT=%llu ADD=%llu CANCEL=%llu TRADE=%llu  LAST_FEED_TIME=%llu  TICKS=%llu\n",
           (unsigned long long)r[DOM_DOM_PKT_COUNT_REG],
           (unsigned long long)r[DOM_DOM_ADD_COUNT_REG],
           (unsigned long long)r[DOM_DOM_CANCEL_COUNT_REG],
           (unsigned long long)r[DOM_DOM_TRADE_COUNT_REG],
           (unsigned long long)r[DOM_DOM_LAST_FEED_TIME_REG],
           (unsigned long long)r[DOM_DOM_TICKS]);
    printf("  --- relay ladder (level 0 = best) ---\n");
    printf("  BID[0] px=%llu qty=%llu | ASK[0] px=%llu qty=%llu\n",
           (unsigned long long)r[DOM_DOM_REL_BID_PRICE_0],
           (unsigned long long)r[DOM_DOM_REL_BID_QTY_0],
           (unsigned long long)r[DOM_DOM_REL_ASK_PRICE_0],
           (unsigned long long)r[DOM_DOM_REL_ASK_QTY_0]);
    printf("  BID[1] px=%llu qty=%llu | ASK[1] px=%llu qty=%llu\n",
           (unsigned long long)r[DOM_DOM_REL_BID_PRICE_1],
           (unsigned long long)r[DOM_DOM_REL_BID_QTY_1],
           (unsigned long long)r[DOM_DOM_REL_ASK_PRICE_1],
           (unsigned long long)r[DOM_DOM_REL_ASK_QTY_1]);
}
