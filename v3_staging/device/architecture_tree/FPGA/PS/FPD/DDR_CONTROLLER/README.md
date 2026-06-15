# DDR Memory Controller
DDR4 SDRAM controller with 6 slave ports
**Type:** `memory_controller`
- **data_width:** 512

## Sub-components
- [DDR_PORT_0](DDR_PORT_0/README.md)
- [DDR_PORT_1](DDR_PORT_1/README.md)
- [DDR_PORT_2](DDR_PORT_2/README.md)
- [DDR_PORT_3](DDR_PORT_3/README.md)
- [DDR_PORT_4](DDR_PORT_4/README.md)
- [DDR_PORT_5](DDR_PORT_5/README.md)

## Connections
- **FPD_MAIN_SWITCH**: AXI (N/A bits, slave)
- **CCI**: DDR_Slave (N/A bits, slave)

## References (UG1085)
- chapter: 17
- pages: 424-512
- tables: ['17-1', '17-2']
