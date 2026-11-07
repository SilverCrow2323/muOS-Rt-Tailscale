#!/bin/sh
# Fails CI if Italian strings reappear in the user-facing UI or backend.
set -eu
REPO="$(cd "$(dirname "$0")/.." && pwd)"
FILES="$REPO/app/RtTailscale/panel/server.py $REPO/app/RtTailscale/panel/index.html"
if grep -nE '"(PIN errato|file vuoto|upload interrotto|log sconosciuto|index\.html mancante|niente da impostare)"' $FILES 2>/dev/null; then
  echo "FAIL: Italian strings found"; exit 1
fi
echo "OK: no Italian strings"
