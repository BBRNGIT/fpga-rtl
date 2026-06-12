# harness — THE POWER HARNESS (programmatic on/off + sequenced power-up for the
# 3 boards). Tool-built: system.harness.yaml --gen_harness--> netlist
# --validate--> --gennet--> device C --cc--> thin test. NOTHING by hand.
CC=cc
CFLAGS=-std=c11 -Wall -Wextra -Werror -O2
PY=python3
SPEC=system.harness.yaml
NET=harness.net.json
GEN=harness_gen.h
.PHONY: all emit validate gen test clean
all: test
emit: $(SPEC) ../gen_harness.py ../gen_module_net.py
	$(PY) ../gen_harness.py $(SPEC) > $(NET)
$(NET): $(SPEC) ../gen_harness.py ../gen_module_net.py
	$(PY) ../gen_harness.py $(SPEC) > $(NET)
validate: $(NET)
	$(PY) validate.py $(NET)
gen: validate
	$(PY) gennet.py $(NET) > $(GEN)
test: gen
	$(CC) $(CFLAGS) -o test_harness test_harness.c
	./test_harness
clean:
	rm -f test_harness
