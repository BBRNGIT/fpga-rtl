/* test_synth.c — THIN test: power on the adapter, display its output. Nothing
 * else. No clock, no stepping, no orchestration loop, no data injection, no
 * wire read. The device's own clock self-runs from the power bit; the buffer
 * reads the data file; the display reads the lanes raw. (test_harness_law) */
#include "adapter.h"
#include "display.h"

/* per-source static config — gold (XAU): symbol id, pip value, commission. */
#define SYM_XAU      1ULL
#define PIP_XAU      100ULL          /* 0.0100 in ×10000 fixed-point */
#define COMMISSION   0ULL

/* SPEED config (real-world-clock rate scale). Default 1 = unscaled real-world
 * pacing (now == source timestamp). Override at build with -DSPEED_CFG=<n>. */
#ifndef SPEED_CFG
#define SPEED_CFG    1ULL
#endif

/* RECORD_FILE: which binary record file the buffer loads. Default = synthetic.
 * Override at build with -DRECORD_FILE='"data_xau.bin"' to run the live file. */
#ifndef RECORD_FILE
#define RECORD_FILE  "data_synth.bin"
#endif

int main(void) {
    const uint64_t *regs =
        adapter_start(RECORD_FILE, SYM_XAU, PIP_XAU, COMMISSION, SPEED_CFG);
    display_show(regs);
    display_wire_bus(adapter_wire_bus());
    return 0;
}
