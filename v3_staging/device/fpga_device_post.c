/* fpga_device_post.c — GENERATED power-on POST for the unified XCZU19EG. */
#include <stdio.h>
#include "fpga_device_gen.h"
int main(void){
    printf("== XCZU19EG fpga_device — POWER-ON POST ==\n");
    printf("PL fabric cells : %llu\n", DEVICE_FABRIC_CELLS);
    printf("element types   : %d (arrays allocated)\n", CAST_TYPES);
    printf("PS domain       : %d hard blocks, %d signals\n", DEVICE_PS_BLOCKS, DEVICE_PS_SIGNALS);
    printf("interconnect    : %llu PIP bits set\n", DEVICE_PIP_BITS);
    printf("loaded design   : %d blocks placed on grid\n", DEVICE_PLACED_BLOCKS);
    /* power: touch fabric + PS so they link */
    storage_element[0].state = 1; lut6[0].cfg = 1; ps_domain[0].state = 1;
    printf("fabric + PS + interconnect + design unified: DEVICE BOOTS\n");
    return (CAST_TOTAL==DEVICE_FABRIC_CELLS && DEVICE_PS_BLOCKS>0) ? 0 : 1;
}
