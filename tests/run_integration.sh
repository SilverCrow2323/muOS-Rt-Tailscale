#!/bin/bash
# Integration test of the service stack (rt + watchdog + web panel) using the REAL arm64
# Tailscale binaries under qemu-user, so it runs on any x86-64 Linux box (and in CI).
#
#   RT_BIN_DIR=/path/with/tailscale+tailscaled ./tests/run_integration.sh
#
# Needs: qemu-user-static (qemu-aarch64-static), python3, curl, root (tailscaled needs it).
# The tests force userspace-networking so no /dev/net/tun is required.
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
BIN="${RT_BIN_DIR:?set RT_BIN_DIR to a folder containing the arm64 tailscale and tailscaled binaries}"
QEMU=$(command -v qemu-aarch64-static) || { echo "qemu-aarch64-static not found (apt install qemu-user-static)"; exit 2; }

W=$(mktemp -d /tmp/rtk-it.XXXXXX)
export RT_RUN="$W/run" RT_INIT_DIR="$W/init" RT_RUNDIR="$W/tsrun" RT_SOCK="$W/tsrun/tailscaled.sock"
PASS=0; FAIL=0
ok()   { echo "  PASS  $1"; PASS=$((PASS + 1)); }
bad()  { echo "  FAIL  $1"; FAIL=$((FAIL + 1)); }
check() { if eval "$2"; then ok "$1"; else bad "$1"; fi; }

APP="$W/app"
mkdir -p "$APP" "$W/fakebin" "$W/tsrun"
cp -r "$ROOT/app/RtTailscale/." "$APP/"
# The process must look like "<dir>/bin/tailscaled" (rt matches on that), so the real binaries live in xbin/
mkdir -p "$APP/xbin" "$APP/bin"
cp "$BIN/tailscale" "$BIN/tailscaled" "$APP/xbin/"
for b in tailscale tailscaled; do
	printf '#!/bin/sh\nexec "%s" "%s/xbin/%s" "$@"\n' "$QEMU" "$APP" "$b" >"$APP/bin/$b"
done
chmod +x "$APP"/bin/* "$APP"/xbin/* "$APP"/rt "$APP"/ts


cleanup() { "$APP/rt" stop >/dev/null 2>&1; rm -rf "$W"; }
trap cleanup EXIT
RT="$APP/rt"
$RT conf set TS_MODE userspace
$RT conf set PANEL_PORT 18077

echo "== install"
check "install reports the Tailscale version" '$RT install | grep -q "Install OK (1\."'

echo "== start"
$RT start
for _ in $(seq 1 40); do [ "$($RT backend)" = NeedsLogin ] && break; sleep 0.5; done
check "backend reaches NeedsLogin (fresh node)" '[ "$($RT backend)" = NeedsLogin ]'
S=$($RT summary)
check "summary: daemon=1"   'echo "$S" | grep -q "^daemon=1$"'
check "summary: panel=1"    'echo "$S" | grep -q "^panel=1$"'
check "summary: watchdog=1" 'echo "$S" | grep -q "^watchdog=1$"'
check "summary: userspace mode (tun=0)" 'echo "$S" | grep -q "^tun=0$"'
check "summary: pin is 6 digits" 'echo "$S" | grep -Eq "^pin=[0-9]{6}$"'

echo "== web panel"
PIN=$($RT pin)
URL=http://127.0.0.1:18077
curl -s -c "$W/cj" -H 'X-Rt: 1' -H 'Content-Type: application/json' -d "{\"pin\":\"$PIN\"}" $URL/api/login >/dev/null
ST=$(curl -s -b "$W/cj" -H 'X-Rt: 1' $URL/api/status)
check "panel login with the PIN works and sees the daemon" 'echo "$ST" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d[\"daemon\"] and d[\"state\"]==\"NeedsLogin\" else 1)"'
check "panel rejects a wrong PIN" '! curl -s -H "X-Rt: 1" -H "Content-Type: application/json" -d "{\"pin\":\"000000\"}" $URL/api/login | grep -q "\"ok\": *true"'
check "panel UI is English" 'curl -s $URL/ | grep -q "<html lang=\"en\">"'

echo "== boot (muOS init script)"
$RT conf set WIFI_WAIT 1
$RT autostart on >/dev/null
check "init script is installed and executable" '[ -x "$RT_INIT_DIR/rttailscale.sh" ]'
check "init script launches 'rt boot' detached with the real path" 'grep -q "setsid \"$APP/rt\" boot" "$RT_INIT_DIR/rttailscale.sh"'
check "autostart status is on"  '[ "$($RT autostart status)" = on ]'
check "'summary' reports autostart=on (what the app shows in Settings)" '$RT summary | grep -q "^autostart=on$"'
$RT stop; sleep 2
sh "$RT_INIT_DIR/rttailscale.sh"       # what muOS does at boot
for _ in $(seq 1 60); do [ "$($RT backend)" = NeedsLogin ] && break; sleep 0.5; done
check "the init script brings the whole stack up" '[ "$($RT backend)" = NeedsLogin ] && $RT summary | grep -q "^panel=1$"'
$RT autostart off >/dev/null
check "autostart status is off" '[ "$($RT autostart status)" = off ] && [ ! -e "$RT_INIT_DIR/rttailscale.sh" ]'

echo "== adopt (another Tailscale app)"
mkdir -p "$W/Tailscale/state"; echo STATE >"$W/Tailscale/state/tailscaled.state"
printf '#!/bin/sh\n' >"$RT_INIT_DIR/tailscale.sh"
$RT stop; sleep 1; rm -f "$APP/state/tailscaled.state"
$RT adopt >/dev/null
check "the other app's init script is disabled" '[ ! -e "$RT_INIT_DIR/tailscale.sh" ] && [ -e "$RT_INIT_DIR/tailscale.sh.disabled-by-rt" ]'
check "its node identity is migrated" 'grep -q STATE "$APP/state/tailscaled.state"'
rm -f "$APP/state/tailscaled.state"
$RT start; for _ in $(seq 1 40); do [ "$($RT backend)" = NeedsLogin ] && break; sleep 0.5; done

echo "== watchdog"
OLD=$(cat "$RT_RUN/daemon.pid"); kill "$OLD"
for _ in $(seq 1 40); do sleep 1; N=$(cat "$RT_RUN/daemon.pid" 2>/dev/null); [ -n "$N" ] && [ "$N" != "$OLD" ] && kill -0 "$N" 2>/dev/null && break; done
check "watchdog restarts a killed daemon" '[ -n "$N" ] && [ "$N" != "$OLD" ] && kill -0 "$N" 2>/dev/null'

echo "== doctor / stop"
check "doctor reports no FAIL" '! $RT doctor | grep -q "^\[FAIL\]"'
$RT stop
sleep 12
S=$($RT summary)
check "after stop the daemon stays down (watchdog honours it)" 'echo "$S" | grep -q "^daemon=0$" && echo "$S" | grep -q "^watchdog=0$"'

echo
echo "passed: $PASS   failed: $FAIL"
[ "$FAIL" -eq 0 ]
