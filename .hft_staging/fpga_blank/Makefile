# fpga_blank — THE identical FPGA blank (cast from device_profiles/vu9p.yaml).
# EMITTED BY gen_fpga_blank.py — DO NOT EDIT BY HAND (regenerate via the tool).
# Pure device reference: NO module allocation, NO logic, NO addresses (blank law).
# Boards = identical instances of this blank, named at addressing (phase 3).
# Flow: part profile --emit--> netlist --validate--> --gennet--> fabric C --cc--> thin test.
CC=cc
CFLAGS=-std=c11 -Wall -Wextra -Werror -O2
PY=python3
PROFILE=../device_profiles/vu9p.yaml
NET=fpga_blank.net.json
GEN=fpga_blank_gen.h
.PHONY: all emit validate gen test clean
all: test
emit: ../gen_fpga_blank.py $(PROFILE)
	$(PY) ../gen_fpga_blank.py $(PROFILE) > $(NET)
$(NET): ../gen_fpga_blank.py $(PROFILE)
	$(PY) ../gen_fpga_blank.py $(PROFILE) > $(NET)
validate: $(NET)
	$(PY) validate.py $(NET)
gen: validate
	$(PY) gennet.py $(NET) > $(GEN)
test: gen
	$(CC) $(CFLAGS) -o test_fpga_blank test_fpga_blank.c
	./test_fpga_blank
clean:
	rm -f test_fpga_blank
