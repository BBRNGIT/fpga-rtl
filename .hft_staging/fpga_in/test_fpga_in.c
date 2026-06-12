/* test_fpga_in.c — thin test: power-on (zero fabric) + display geometry.
 * A blank owns no logic and runs no clock; the test proves the fabric exists,
 * inits, and its real-part constants are present. Static storage — no heap. */
#include <stdio.h>
#include "fpga_in_gen.h"

static fpga_in_word_t f[FPGA_IN_FABRIC_REGS];

int main(void) {
    fpga_in_init(f);
    printf("fpga-in blank: fabric=%u regs x %u bits | mac=%uHz internal=%uHz\n",
           FPGA_IN_FABRIC_REGS, FPGA_IN_WORD_BITS,
           FPGA_IN_CLK_MAC_HZ, FPGA_IN_CLK_INTERNAL_HZ);
    printf("geometry: addr_space=%#x align=%#x cdc=%#x | gty=%u clb=%u\n",
           FPGA_IN_ADDR_SPACE_SIZE, FPGA_IN_SLOT_ALIGNMENT, FPGA_IN_CDC_REGION_SIZE,
           FPGA_IN_IO_GTY_LANES, FPGA_IN_RES_CLB_CAPACITY);
    return 0;
}
