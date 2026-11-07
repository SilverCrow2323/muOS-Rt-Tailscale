#!/bin/bash
# master.sh — Salto 1 (GPG + SBOM + reproducible) + Salto 2 (CI + fuzz + i18n)
# Safe: no browser loops, no GUI pinentry, fail-fast preflight.
set -euo pipefail
cd "$(dirname "$0")"

EMAIL="${GPG_EMAIL:-santatonicola93@gmail.com}"
NAME="${GPG_NAME:-SilverCrow2323}"
REPO_DEFAULT="SilverCrow2323/rt-tailscale-m"

# ===========================================================================
echo "=== 0/10. Cleanup stale processes ==="
pkill -9 -f jump1.sh 2>/dev/null || true
pkill -9 -f 'gh auth' 2>/dev/null || true
pkill -9 -f pinentry 2>/dev/null || true
gpgconf --kill gpg-agent 2>/dev/null || true
echo "  done"

# ===========================================================================
echo "=== 1/10. Preflight ==="

if ! gh auth status >/dev/null 2>&1; then
  echo "  ❌ gh not authenticated."
  echo "     Run once:  gh auth login"
  echo "     Then re-run this script."
  exit 1
fi
echo "  gh: authenticated"

# Ensure default repo
if ! gh repo view --json nameWithOwner >/dev/null 2>&1; then
  echo "  setting default repo..."
  gh repo set-default "$REPO_DEFAULT"
fi
echo "  gh: repo = $(gh repo view --json nameWithOwner --jq .nameWithOwner)"

if ! timeout 15 git ls-remote origin >/dev/null 2>&1; then
  echo "  ❌ git cannot reach origin"
  echo "     Try: git fetch origin"
  exit 1
fi
echo "  git: origin reachable"

# ===========================================================================
echo "=== 2/10. GPG setup (no GUI, no browser) ==="
mkdir -p ~/.gnupg && chmod 700 ~/.gnupg
grep -q 'allow-loopback-pinentry' ~/.gnupg/gpg-agent.conf 2>/dev/null || \
  echo 'allow-loopback-pinentry' >> ~/.gnupg/gpg-agent.conf
grep -q 'pinentry-program' ~/.gnupg/gpg-agent.conf 2>/dev/null || \
  echo 'pinentry-program /usr/bin/pinentry-curses' >> ~/.gnupg/gpg-agent.conf
gpgconf --launch gpg-agent

if gpg --list-secret-keys "$EMAIL" >/dev/null 2>&1; then
  echo "  key already exists"
else
  echo "  generating RSA4096 2y (loopback, no prompt)"
  gpg --batch --pinentry-mode loopback --passphrase '' \
      --quick-generate-key "$NAME <$EMAIL>" rsa4096 sign 2y
fi
KEYID="$(gpg --list-secret-keys --with-colons "$EMAIL" | awk -F: '/^sec/{print $5; exit}')"
git config --global user.signingkey "$KEYID"
git config --global tag.gpgsign true
git config --global gpg.program gpg
echo "  key = $KEYID"

# ===========================================================================
echo "=== 3/10. Export public key (manual upload needed) ==="
PUB="/tmp/rttailscale-$KEYID.pub.asc"
gpg --armor --export "$KEYID" > "$PUB"
echo
echo "  ┌────────────────────────────────────────────────────────────┐"
echo "  │  ONE-TIME MANUAL STEP (no browser auto-opens)              │"
echo "  │                                                            │"
echo "  │  1. Open in your browser:                                  │"
echo "  │     https://github.com/settings/gpg/new                    │"
echo "  │  2. Paste the PUBLIC KEY below                             │"
echo "  │  3. Title: RtTailscale-M release key                       │"
echo "  │  4. Click 'Add GPG key'                                    │"
echo "  │  5. Come back and press ENTER                              │"
echo "  └────────────────────────────────────────────────────────────┘"
echo
sed 's/^/  /' "$PUB"
echo
read -rp "  Press ENTER after uploading (or ENTER to skip for now)... " _ || true

HAVE_GPG=0
if gh api user/gpg_keys --jq '.[].key_id' 2>/dev/null | grep -q "$KEYID"; then
  echo "  ✅ GitHub sees key $KEYID"
  HAVE_GPG=1
else
  echo "  ⚠ GitHub does not see key yet (may be propagation lag)"
  echo "    Continuing without signing — you can sign the tag later."
fi

# ===========================================================================
echo "=== 4/10. Patch build.sh for reproducibility ==="
if grep -q 'SOURCE_DATE_EPOCH' build.sh; then
  echo "  already patched"
else
  python3 - <<'PY'
from pathlib import Path
p = Path("build.sh")
s = p.read_text()
if "SOURCE_DATE_EPOCH" not in s:
    s = s.replace(
        "set -euo pipefail",
        'set -euo pipefail\nexport SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git log -1 --format=%ct 2>/dev/null || date +%s)}"\nexport TZ=UTC',
        1)
if 'touch -h -d "@$SOURCE_DATE_EPOCH"' not in s:
    s = s.replace(
        'rm -f "$OUT"',
        'find "$STAGE" -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} +\nrm -f "$OUT"',
        1)
p.write_text(s)
print("  build.sh patched")
PY
fi

# ===========================================================================
echo "=== 5/10. Add fuzz + i18n guard tests ==="
cat > tests/fuzz_json.lua <<'LUA'
-- tests/fuzz_json.lua — 10 000 random inputs, must never crash
package.path = "app/RtTailscale/game/?.lua;" .. package.path
local json = require("lib.json")
math.randomseed(42)
local alphabet = "{}[]\",:0123456789truefalsnul\\uABCDEFghij \t\r\n"
local crashes = 0
for i = 1, 10000 do
  local len = math.random(0, 200)
  local s = {}
  for j = 1, len do
    local k = math.random(#alphabet)
    s[j] = alphabet:sub(k, k)
  end
  local ok = pcall(json.decode, table.concat(s))
  if not ok then crashes = crashes + 1 end
end
if crashes > 0 then
  io.stderr:write(("FAIL: %d crashes out of 10000\n"):format(crashes))
  os.exit(1)
end
print("fuzz_json: 10000 inputs, no crashes")
LUA

cat > tests/i18n_guard.sh <<'SH'
#!/bin/sh
# Fails CI if Italian strings reappear in the user-facing UI or backend.
set -eu
REPO="$(cd "$(dirname "$0")/.." && pwd)"
FILES="$REPO/app/RtTailscale/panel/server.py $REPO/app/RtTailscale/panel/index.html"
if grep -nE '"(PIN errato|file vuoto|upload interrotto|log sconosciuto|index\.html mancante|niente da impostare)"' $FILES 2>/dev/null; then
  echo "FAIL: Italian strings found"; exit 1
fi
echo "OK: no Italian strings"
SH
chmod +x tests/i18n_guard.sh

# Wire into run_all.sh
if ! grep -q 'Fuzz JSON parser' tests/run_all.sh; then
  python3 - <<'PY'
from pathlib import Path
p = Path("tests/run_all.sh")
s = p.read_text()
needle = 'step "Lua input mapping tests" luajit tests/test_input.lua'
add = needle + '\nstep "Fuzz JSON parser" luajit tests/fuzz_json.lua\nstep "i18n guard" sh tests/i18n_guard.sh'
if needle in s and "Fuzz JSON parser" not in s:
    p.write_text(s.replace(needle, add, 1))
    print("  run_all.sh wired")
PY
fi

# ===========================================================================
echo "=== 6/10. Harden CI workflow ==="
mkdir -p .github/workflows
cat > .github/workflows/ci.yml <<'YAML'
name: ci
on:
  push: { branches: [main] }
  pull_request: { branches: [main] }
permissions:
  contents: read
  id-token: write
  attestations: write
jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - name: Install tools
        run: |
          sudo apt-get update
          sudo apt-get install -y shellcheck luajit qemu-user-static zip curl python3-pip
          pip install --break-system-packages pyflakes qrcode pillow opencv-python-headless numpy
      - name: shellcheck (strict)
        run: shellcheck -s sh -S warning app/RtTailscale/rt app/RtTailscale/watchdog app/RtTailscale/ts app/RtTailscale/mux_launch.sh
      - name: pyflakes
        run: python3 -m pyflakes app/RtTailscale/panel/server.py
      - name: Lua syntax
        run: for f in $(find app tests -name "*.lua"); do luajit -bl "$f" /dev/null || exit 1; done
      - name: Unit + fuzz
        run: |
          luajit tests/test_model.lua
          luajit tests/test_input.lua
          luajit tests/fuzz_json.lua
      - name: i18n guard
        run: sh tests/i18n_guard.sh
      - name: QR encoder
        run: python3 tests/test_qr.py
      - name: Download arm64 Tailscale
        run: |
          ver=$(curl -fsSL 'https://pkgs.tailscale.com/stable/?mode=json' | python3 -c 'import sys,json; print(json.load(sys.stdin)["TarballsVersion"])')
          mkdir -p /tmp/tsbin && cd /tmp/tsbin
          curl -fsSL "https://pkgs.tailscale.com/stable/tailscale_${ver}_arm64.tgz" | tar -xz --strip-components=1
      - name: Integration (qemu)
        run: sudo env "PATH=$PATH" RT_BIN_DIR=/tmp/tsbin tests/run_integration.sh
      - name: Build (reproducible)
        run: |
          export SOURCE_DATE_EPOCH=$(git log -1 --format=%ct)
          ./build.sh --bin-dir /tmp/tsbin
          sha256sum dist/*.muxapp
      - name: SBOM
        uses: anchore/sbom-action@v0
        with:
          path: dist/
          format: cyclonedx-json
          output-file: dist/sbom.json
      - name: Attest provenance
        uses: actions/attest-build-provenance@v1
        with:
          subject-path: 'dist/RtTailscale-M-*.muxapp'
      - uses: actions/upload-artifact@v4
        with:
          name: RtTailscale-M
          path: dist/*
YAML
echo "  ci.yml written"

# ===========================================================================
echo "=== 7/10. Run all tests locally ==="
tests/run_all.sh
echo "  ✅ all tests passed"

# ===========================================================================
echo "=== 8/10. Reproducible build + SBOM ==="
if ! command -v syft >/dev/null 2>&1; then
  echo "  installing syft..."
  curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sudo sh -s -- -b /usr/local/bin >/dev/null
fi

rm -rf dist
./build.sh >/dev/null
H1=$(sha256sum dist/*.muxapp | cut -d' ' -f1)
rm -rf dist
./build.sh >/dev/null
H2=$(sha256sum dist/*.muxapp | cut -d' ' -f1)

if [ "$H1" != "$H2" ]; then
  echo "  ❌ NOT reproducible"
  echo "     build1: $H1"
  echo "     build2: $H2"
  exit 1
fi
echo "  ✅ reproducible: $H1"

syft dist/RtTailscale-M-0.1.0.muxapp -o cyclonedx-json > dist/RtTailscale-M-0.1.0.sbom.json
echo "  ✅ SBOM: $(wc -c < dist/RtTailscale-M-0.1.0.sbom.json) bytes"

# ===========================================================================
echo "=== 9/10. Commit + tag + push ==="
git add -A
if ! git diff --cached --quiet; then
  git commit -m "ci: harden pipeline + fuzz + i18n guard + reproducible build + SBOM

- shellcheck -S warning (strict) in CI
- fuzz JSON parser: 10000 random inputs, no crashes
- i18n guard: fails on Italian strings
- reproducible build: SOURCE_DATE_EPOCH in build.sh
- SBOM: anchore/sbom-action (CycloneDX)
- SLSA provenance: actions/attest-build-provenance"
  git push origin HEAD:main
  echo "  ✅ committed and pushed"
else
  echo "  (nothing new to commit)"
fi

if [ "$HAVE_GPG" = 1 ]; then
  git tag -d v0.1.0 2>/dev/null || true
  git tag -s v0.1.0 -m "Rt:Tailscale-M 0.1.0 (audit-corrected, device-verified, reproducible)"
  git push --force origin v0.1.0
  git verify-tag v0.1.0
  echo "  ✅ signed tag v0.1.0 pushed"
else
  echo "  ⚠ skipped tag signing (key not on GitHub yet)"
  echo "    Later, run:"
  echo "      git tag -d v0.1.0"
  echo "      git tag -s v0.1.0 -m 'Rt:Tailscale-M 0.1.0 (reproducible)'"
  echo "      git push --force origin v0.1.0"
fi

# ===========================================================================
echo "=== 10/10. Upload release assets ==="
gh release upload v0.1.0 dist/RtTailscale-M-0.1.0.muxapp --clobber
gh release upload v0.1.0 dist/RtTailscale-M-0.1.0.muxapp.sha256 --clobber
gh release upload v0.1.0 dist/RtTailscale-M-0.1.0.sbom.json --clobber
echo "  ✅ assets uploaded"

echo
echo "============================================================"
echo "  ✅ ALL DONE"
echo "============================================================"
echo "  Assets on release v0.1.0:"
gh release view v0.1.0 --json assets --jq '.assets[] | "    " + .name + "  " + (.size|tostring) + " bytes"'
echo
echo "  Next: push CI and watch it"
echo "    git push origin HEAD:main   # already done above"
echo "    gh run watch"
