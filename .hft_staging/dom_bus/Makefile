# dom_bus — DOM's passive lock-free BARRIER bus (dom -> indicators). Tool-built:
# logic.yaml --emit--> netlist --validate--> --gennet--> address map --cc--> thin test.
CC=cc
CFLAGS=-std=c11 -Wall -Wextra -Werror -O2
PY=python3
EMIT=gen_dom_bus_net.py
LOGIC=dom_bus_logic.yaml
NET=dom_bus.net.json
GEN=dom_bus_gen.h
.PHONY: all emit validate gen test clean
all: test
emit: $(EMIT) $(LOGIC) ../gen_module_net.py
	$(PY) $(EMIT) > $(NET)
$(NET): $(EMIT) $(LOGIC) ../gen_module_net.py
	$(PY) $(EMIT) > $(NET)
validate: $(NET)
	$(PY) validate.py $(NET)
gen: validate
	$(PY) gennet.py $(NET) > $(GEN)
test: gen
	$(CC) $(CFLAGS) -o test_dom_bus test_dom_bus.c
	./test_dom_bus
clean:
	rm -f test_dom_bus
