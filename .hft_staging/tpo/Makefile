# tpo device — indicator component. Real build, owned in this tree.
# Flow: logic.yaml --emit--> netlist --validate--> --gennet--> device C --cc--> thin test.
#
# The emitter is the GENERIC meta-tool ../gen_module_net.py, invoked via the thin
# wrapper gen_tpo_net.py on tpo_logic.yaml. The netlist and *_gen.h are
# TOOL OUTPUTS (never hand-edited); both are committed as the validation spec.
#
# DOCTRINE: tpo is a price-indexed projection (Law #10) built to an ABSTRACT
# per-tick payload port (build/assignment separation) — no DOM/TF binding, no addresses.

CC      = cc
CFLAGS  = -std=c11 -Wall -Wextra -Werror -O2
PY      = python3

EMIT    = gen_tpo_net.py
LOGIC   = tpo_logic.yaml
NET     = tpo.net.json
GEN     = tpo_gen.h

.PHONY: all emit validate gen selfcheck test probe clean

all: test

emit: $(EMIT) $(LOGIC) ../gen_module_net.py
	$(PY) $(EMIT) > $(NET)

$(NET): $(EMIT) $(LOGIC) ../gen_module_net.py
	$(PY) $(EMIT) > $(NET)

validate: $(NET)
	$(PY) validate.py $(NET)

gen: validate
	$(PY) gennet.py $(NET) > $(GEN)

selfcheck: gen
	$(PY) simnet.py $(NET)

test: gen
	$(CC) $(CFLAGS) -o test_tpo test_tpo.c
	./test_tpo

probe: test
	@echo "--- probe: tpo register snapshot ---"

clean:
	rm -f test_tpo tpo_selfcheck probe
