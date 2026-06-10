# tai_cdc — TAI clock-domain crossing (gray-code 2-FF sync). Real build, owned in
# this tree. NO poc/ ref. Flow: emitter --> netlist --validate--> (gate) --gennet-->
# device C --cc--> thin test.

CC      = cc
CFLAGS  = -std=c11 -Wall -Wextra -Werror -O2
PY      = python3

EMIT    = gen_tai_cdc_net.py
NET     = tai_cdc.net.json
GEN     = tai_cdc_gen.h

.PHONY: all emit validate gen test probe clean

all: test

emit: $(EMIT)
	$(PY) $(EMIT)

validate: $(NET)
	$(PY) validate.py $(NET)

gen: validate
	$(PY) gennet.py $(NET) > $(GEN)

test: gen
	$(CC) $(CFLAGS) -o test_synth test_synth.c tai_cdc.c display.c
	@echo "--- running tai_cdc thin test ---"
	./test_synth

probe: test
	@echo "--- probe: tai_cdc register snapshot ---"
	./test_synth

clean:
	rm -f $(GEN) test_synth probe

$(NET): $(EMIT)
	$(PY) $(EMIT)
