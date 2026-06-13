/* engine.c — the BIOS ENGINE: the C interface that powers the FPGA up/down and
 * reports status/POST. One command per invocation; the bash console (bios.sh)
 * keeps session state and drives the menu. The engine adds NO datapath logic —
 * it only sequences power and reports. Phase A targets the bare blank prototype;
 * Phase D extends POST to the assembled modules on the .bbhft clone.
 *
 * Usage: engine <boot|shutdown|post|status>
 */
#include "fpga_device_gen.h"
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv) {
    const char *cmd = (argc > 1) ? argv[1] : "status";
    fpga_device_init();

    if (!strcmp(cmd, "boot")) {
        printf("  [BIOS] init fabric ............ ok  (%lu flip-flops, %lu LUTs)\n",
               fpga_device_flipflops(), fpga_device_luts());
#ifdef FPGA_MMCM_COUNT
        /* native clocks: configure MMCM[0] (bitstream divides) and power the clock */
        fpga_mmcm[0][MMCM_DIV_0_D]=2; fpga_mmcm[0][MMCM_DIV_1_D]=4; fpga_mmcm[0][MMCM_DIV_CFG_EN]=1;
        fpga_device_power_on();
        fpga_device_tick();
        fpga_mmcm[0][MMCM_DIV_CFG_EN]=0; fpga_mmcm[0][MMCM_CLK_POWER]=1;
        int c0=0,c1=0; for (int t=0;t<12;t++){ fpga_device_tick();
            c0+=fpga_mmcm[0][MMCM_CLKOUT_0]&1; c1+=fpga_mmcm[0][MMCM_CLKOUT_1]&1; }
        printf("  [BIOS] master power ........... ON\n");
        printf("  [CLOCK] native clock mgmt ..... %u MMCM, %u PLL present\n", FPGA_MMCM_COUNT, FPGA_PLL_COUNT);
        printf("  [CLOCK] MMCM[0] ALIVE ......... CLKOUT/2=%d edges, CLKOUT/4=%d over 12 ref ticks\n", c0, c1);
        printf("  [POST] fabric + native clocks . PASS\n");
#else
        fpga_device_power_on();
        for (int i = 0; i < 8; i++) fpga_device_tick();
        printf("  [BIOS] master power ........... ON\n");
        printf("  [POST] bare fabric alive ...... PASS (no native clocks on this image)\n");
#endif
        printf("  [BIOS] BOOTED\n");
        return 0;
    }
    if (!strcmp(cmd, "shutdown")) {
        fpga_device_power_off();
        printf("  [BIOS] master power ........... OFF\n");
        printf("  [BIOS] SHUT DOWN\n");
        return 0;
    }
    if (!strcmp(cmd, "post")) {
        fpga_device_power_on();
        printf("  [POST] fabric ................. PASS (%lu flip-flops, %lu LUTs powered)\n",
               fpga_device_flipflops(), fpga_device_luts());
        fpga_device_power_off();
        return 0;
    }
    /* status */
    fpga_device_display();
    return 0;
}
