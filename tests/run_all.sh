#!/bin/bash
# Run every check that does not need a device. Optional integration test: set RT_BIN_DIR.
cd "$(dirname "$0")/.." || exit 1
rc=0
step() { echo; echo "### $1"; shift; "$@" || { echo ">>> FAILED: $*"; rc=1; }; }

step "shellcheck (POSIX sh)"  shellcheck -s sh app/RtTailscale/rt app/RtTailscale/watchdog app/RtTailscale/ts
step "shellcheck (launcher)"  shellcheck -s sh app/RtTailscale/mux_launch.sh
step "python (panel) lint"    python3 -m pyflakes app/RtTailscale/panel/server.py
step "Lua syntax"             bash -c 'for f in $(find app tests -name "*.lua"); do luajit -bl "$f" /dev/null || exit 1; done'
step "Lua model tests"        luajit tests/test_model.lua
step "Lua input mapping tests" luajit tests/test_input.lua
step "Fuzz JSON parser" luajit tests/fuzz_json.lua
step "i18n guard" sh tests/i18n_guard.sh
step "QR encoder vs python-qrcode + OpenCV" python3 tests/test_qr.py
if command -v love >/dev/null && command -v xvfb-run >/dev/null; then
  step "UI renders all 12 screens" bash -c 'rm -rf /tmp/rtk-ui-test && mkdir -p /tmp/rtk-ui-test && HOME=/tmp/rtk-ui-test timeout 120 xvfb-run -a env RTTS_FAKE_DIR="$PWD/tests/fixtures" RTTS_DEMO=/tmp/rtk-ui-test/s RT_RUN=/tmp/rtk-ui-test/run LIBGL_ALWAYS_SOFTWARE=1 love app/RtTailscale/game >/dev/null 2>&1; [ "$(ls /tmp/rtk-ui-test/s-*.png 2>/dev/null | wc -l)" = 12 ]'
else echo; echo "(UI render test skipped: needs love + xvfb-run)"; fi
if [ -n "${RT_BIN_DIR:-}" ]; then step "integration (qemu)" tests/run_integration.sh
else echo; echo "(integration test skipped: set RT_BIN_DIR to run it)"; fi

echo; [ "$rc" -eq 0 ] && echo "ALL CHECKS PASSED" || echo "SOME CHECKS FAILED"
exit $rc
