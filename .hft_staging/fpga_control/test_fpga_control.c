/* test_fpga_control.c — thin test: power-on (zero fabric) + display geometry.
 * A blank owns no logic and runs no clock; the test proves the fabric exists,
 * inits, and its real-part constants are present. Static storage — no heap. */
#include <stdio.h>
#include "fpga_control_gen.h"

static fpga_control_word_t f[FPGA_CONTROL_FABRIC_REGS];

int main(void) {
    fpga_control_init(f);
    printf("fpga-control blank: fabric=%u regs x %u bits | taiosc=%uHz internal=%uHz\n",
           FPGA_CONTROL_FABRIC_REGS, FPGA_CONTROL_WORD_BITS,
           FPGA_CONTROL_CLK_TAIOSC_HZ, FPGA_CONTROL_CLK_INTERNAL_HZ);
    printf("geometry: addr_space=%#x align=%#x cdc=%#x | gty=%u clb=%u\n",
           FPGA_CONTROL_ADDR_SPACE_SIZE, FPGA_CONTROL_SLOT_ALIGNMENT, FPGA_CONTROL_CDC_REGION_SIZE,
           FPGA_CONTROL_IO_GTY_LANES, FPGA_CONTROL_RES_CLB_CAPACITY);
    return 0;
}
