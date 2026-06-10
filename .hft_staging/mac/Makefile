# mac — 125 MHz MAC sample clock. Real build, owned in this tree. NO poc/ ref.
# Flow: emitter --> netlist --validate--> (gate) --gennet--> device C --cc--> test.

CC      = cc
CFLAGS  = -std=c11 -Wall -Wextra -Werror -O2
PY      = python3

EMIT    = gen_mac_net.py
NET     = mac.net.json
GEN     = mac_gen.h

.PHONY: all emit validate gen test probe clean

all: test

emit: $(EMIT)
	$(PY) $(EMIT)

validate: $(NET)
	$(PY) validate.py $(NET)

gen: validate
	$(PY) gennet.py $(NET) > $(GEN)

test: gen
	$(CC) $(CFLAGS) -o test_synth test_synth.c mac.c display.c
	@echo "--- running mac thin test ---"
	./test_synth

probe: test
	@echo "--- probe: mac register snapshot ---"
	./test_synth

clean:
	rm -f $(GEN) test_synth probe

$(NET): $(EMIT)
	$(PY) $(EMIT)
