/* test_fpga_main.c — thin test: power-on (zero fabric) + display geometry.
 * A blank owns no logic and runs no clock; the test proves the fabric exists,
 * inits, and its real-part constants are present. Static storage — no heap. */
#include <stdio.h>
#include "fpga_main_gen.h"

static fpga_main_word_t f[FPGA_MAIN_FABRIC_REGS];

int main(void) {
    fpga_main_init(f);
    printf("fpga-main blank: fabric=%u regs x %u bits | taiosc=%uHz internal=%uHz\n",
           FPGA_MAIN_FABRIC_REGS, FPGA_MAIN_WORD_BITS,
           FPGA_MAIN_CLK_TAIOSC_HZ, FPGA_MAIN_CLK_INTERNAL_HZ);
    printf("geometry: addr_space=%#x align=%#x cdc=%#x | gty=%u clb=%u\n",
           FPGA_MAIN_ADDR_SPACE_SIZE, FPGA_MAIN_SLOT_ALIGNMENT, FPGA_MAIN_CDC_REGION_SIZE,
           FPGA_MAIN_IO_GTY_LANES, FPGA_MAIN_RES_CLB_CAPACITY);
    return 0;
}
