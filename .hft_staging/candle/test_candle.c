/* test_candle.c — THIN test: power-on + display only (no inject/step/replay).
 * Power the device on and run one self-oscillating edge, then display the live
 * OHLC lanes raw. The device logic itself is the generated cells; this testbench
 * only powers it and reads lanes (no compute, no conditionals on data). */
#include <stdio.h>
#include "candle_gen.h"

static word_t R[CANDLE_REG_COUNT];

int main(void) {
    candle_init(R);
    R[CANDLE_CANDLE_POWER] = 1ULL;        /* power on; clock self-runs one edge */
    R[CANDLE_CANDLE_POWER] = 0ULL;        /* (single edge for the thin test)    */
    candle_tick(R);                       /* one clock edge                     */
    printf("candle live OHLC bid: O=%llu H=%llu L=%llu C=%llu\n",
           (unsigned long long)R[CANDLE_CANDLE_BID_OPEN],
           (unsigned long long)R[CANDLE_CANDLE_BID_HIGH],
           (unsigned long long)R[CANDLE_CANDLE_BID_LOW],
           (unsigned long long)R[CANDLE_CANDLE_BID_CLOSE]);
    printf("candle bar_seq=%llu volume_bid=%llu delta=%llu\n",
           (unsigned long long)R[CANDLE_CANDLE_BAR_SEQ],
           (unsigned long long)R[CANDLE_CANDLE_VOLUME_BID],
           (unsigned long long)R[CANDLE_CANDLE_INTRABAR_QTY_DELTA]);
    return 0;
}
