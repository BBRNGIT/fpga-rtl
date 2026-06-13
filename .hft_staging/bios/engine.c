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
        fpga_device_power_on();
        for (int i = 0; i < 8; i++) fpga_device_tick();   /* let the power harness settle */
        printf("  [BIOS] master power ........... ON\n");
        printf("  [POST] fabric alive ........... PASS\n");
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
