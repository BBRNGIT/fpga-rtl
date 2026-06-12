/* test_fpga_blank.c — thin test: power-on (zero fabric) + display geometry.
 * EMITTED BY gen_fpga_blank.py — DO NOT EDIT BY HAND (regenerate via the tool).
 * A blank owns no logic and runs no clock; the test proves the fabric exists,
 * inits, and the full-part constants are present. Static storage — no heap. */
#include <stdio.h>
#include "fpga_blank_gen.h"

static fpga_blank_word_t f[FPGA_BLANK_FABRIC_REGS];

int main(void) {
    fpga_blank_init(f);
    printf("fpga blank: fabric=%u regs x %u bits | mac=%uHz internal=%uHz taiosc=%uHz\n",
           FPGA_BLANK_FABRIC_REGS, FPGA_BLANK_WORD_BITS,
           FPGA_BLANK_CLK_MAC_HZ, FPGA_BLANK_CLK_INTERNAL_HZ, FPGA_BLANK_CLK_TAIOSC_HZ);
    printf("full part: gty=%u banks=%u clb=%u bram=%u dsp=%u | geom addr=%#x align=%#x cdc=%#x\n",
           FPGA_BLANK_IO_GTY_LANES, FPGA_BLANK_IO_IO_BANKS,
           FPGA_BLANK_RES_CLB_CAPACITY, FPGA_BLANK_RES_BRAM_CAPACITY, FPGA_BLANK_RES_DSP_CAPACITY,
           FPGA_BLANK_ADDR_SPACE_SIZE, FPGA_BLANK_SLOT_ALIGNMENT, FPGA_BLANK_CDC_REGION_SIZE);
    return 0;
}
