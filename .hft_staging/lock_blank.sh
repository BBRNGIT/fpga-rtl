#!/usr/bin/env bash
# lock_blank.sh — certify the BLANK FPGA device so it can be locked into the vault.
#
# The blank (slices/RAM/lanes) is fixed-by-design — the immutable foundation. This is
# its graduation: prove it (1) regenerates byte-identically from committed inputs
# (determinism), (2) builds -Werror and runs, (3) rebuilds clean-room from committed
# HEAD (reproducibility). On PASS, the blank is safe to vault. Does NOT vault by
# itself — vaulting is a separate, explicit step.
set -euo pipefail
cd "$(dirname "$0")"            # operate from .hft_staging (assembly paths are fpga/*)
say(){ echo "==> [lock-blank] $*"; }
FP=fpga

say "1/3 reproducibility — device header regenerates byte-identically from committed inputs"
python3 gen_fpga_device.py "$FP/vu9p_device.yaml" spec/vu9p_device_model.json > /tmp/lb_dev.h
if diff -q /tmp/lb_dev.h "$FP/fpga_device_gen.h" >/dev/null; then
  echo "    PASS  fpga_device_gen.h reproduces exactly from assembly + device model"
else
  echo "    FAIL  device header drift (committed artifact != regenerated)"; exit 1
fi

say "2/3 build -Werror + run"
cc -O2 -std=c11 -Wall -Wextra -Werror "$FP/test_device.c" -I"$FP" -o /tmp/lb_test
/tmp/lb_test | head -1
echo "    PASS  builds clean and runs"

say "3/3 clean-room — rebuild the blank from committed HEAD in a fresh tree"
TMP="$(mktemp -d)"
git -C .. archive HEAD .hft_staging/fpga .hft_staging/spec .hft_staging/gen_fpga_device.py | tar -x -C "$TMP"
(
  cd "$TMP/.hft_staging"
  python3 gen_fpga_device.py fpga/vu9p_device.yaml spec/vu9p_device_model.json > fpga/fpga_device_gen.h
  cc -O2 -std=c11 -Wall -Wextra -Werror fpga/test_device.c -Ifpga -o /tmp/lb_clean
  /tmp/lb_clean | head -1
)
rm -rf "$TMP"
echo "    PASS  clean-room build from committed HEAD reproduces the device"

say "BLANK CERTIFIED — reproducible, builds, clean-room OK. Safe to vault."
