# fpga_in — FPGA BLANK (board fabric, cast from device_profiles/fpga-in.yaml).
# Pure device reference: NO module allocation, NO logic, NO addresses (blank law).
# Flow: profile --emit--> netlist --validate--> --gennet--> fabric C --cc--> thin test.
CC=cc
CFLAGS=-std=c11 -Wall -Wextra -Werror -O2
PY=python3
EMIT=gen_fpga_in_net.py
NET=fpga_in.net.json
GEN=fpga_in_gen.h
.PHONY: all emit validate gen test clean
all: test
emit: $(EMIT) ../gen_fpga_blank.py ../device_profiles/fpga-in.yaml
	$(PY) $(EMIT) > $(NET)
$(NET): $(EMIT) ../gen_fpga_blank.py ../device_profiles/fpga-in.yaml
	$(PY) $(EMIT) > $(NET)
validate: $(NET)
	$(PY) validate.py $(NET)
gen: validate
	$(PY) gennet.py $(NET) > $(GEN)
test: gen
	$(CC) $(CFLAGS) -o test_fpga_in test_fpga_in.c
	./test_fpga_in
clean:
	rm -f test_fpga_in
