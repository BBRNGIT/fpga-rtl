#include "fpga_device_gen.h"
int main(void){ fpga_device_init(); fpga_device_power_on(); fpga_device_tick(); fpga_device_display(); return 0; }
