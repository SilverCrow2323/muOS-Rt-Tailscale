#!/bin/sh
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
mkdir -p "$TMP/app"
cp "$ROOT/app/RtTailscale/rt" "$TMP/app/rt"
chmod 755 "$TMP/app/rt"
RT_RUN="$TMP/run" RT_RUNDIR="$TMP/rundir" RT_INIT_DIR="$TMP/init" \
    "$TMP/app/rt" conf set HTTP_PROXY "http://user:secret@proxy.example:8080"
MODE="$(stat -c '%a' "$TMP/app/config/rt.conf")"
[ "$MODE" = "600" ] || {
    echo "expected config mode 600, got $MODE" >&2
    exit 1
}
grep -Fq 'HTTP_PROXY=http://user:secret@proxy.example:8080' "$TMP/app/config/rt.conf"
echo "config permissions test passed"
