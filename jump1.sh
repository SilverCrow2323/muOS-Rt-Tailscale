#!/bin/bash
# jump1.sh v2 — GPG-signed tags + SBOM + reproducible build
# Safety: fails fast, no silent gh retries, no gpg pinentry loops.
set -euo pipefail
cd "$(dirname "$0")"

EMAIL="${GPG_EMAIL:-santatonicola93@gmail.com}"
NAME="${GPG_NAME:-SilverCrow2323}"

# ---------------------------------------------------------------------------
echo "=== 0/6. Pre-flight ==="

# 0a. gh must be authenticated
if ! gh auth status >/dev/null 2>&1; then
  echo "  ❌ gh not authenticated. Run: gh auth login"
  echo "     Then re-run this script."
  exit 1
fi
echo "  gh: authenticated"

# 0b. default repo must be set
if ! gh repo view --json nameWithOwner >/dev/null 2>&1; then
  echo "  ❌ no default repo for gh. Run:"
  echo "     gh repo set-default SilverCrow2323/rt-tailscale-m"
  exit 1
fi
echo "  gh: default repo = $(gh repo view --json nameWithOwner --jq .nameWithOwner)"

# 0c. git must be able to reach origin without prompting
if ! timeout 15 git ls-remote origin >/dev/null 2>&1; then
  echo "  ❌ git cannot reach origin (auth or network)."
  echo "     Try: git fetch origin"
  exit 1
fi
echo "  git: origin reachable"

# 0d. no stale gpg pinentry
pkill -9 -f pinentry 2>/dev/null || true
gpgconf --kill gpg-agent 2>/dev/null || true

# ---------------------------------------------------------------------------
echo "=== 1/6. GPG key ==="
# Use loopback pinentry: no GUI, no browser, ever.
mkdir -p ~/.gnupg && chmod 700 ~/.gnupg
grep -q 'allow-loopback-pinentry' ~/.gnupg/gpg-agent.conf 2>/dev/null || \
  echo 'allow-loopback-pinentry' >> ~/.gnupg/gpg-agent.conf
grep -q 'pinentry-program' ~/.gnupg/gpg-agent.conf 2>/dev/null || \
  echo 'pinentry-program /usr/bin/pinentry-curses' >> ~/.gnupg/gpg-agent.conf
gpgconf --launch gpg-agent

if gpg --list-secret-keys "$EMAIL" >/dev/null 2>&1; then
  echo "  already exists"
else
  echo "  generating RSA4096, 2y, no passphrase"
  gpg --batch --pinentry-mode loopback --passphrase '' \
      --quick-generate-key "$NAME <$EMAIL>" rsa4096 sign 2y
fi
KEYID="$(gpg --list-secret-keys --with-colons "$EMAIL" | awk -F: '/^sec/{print $5; exit}')"
echo "  key: $KEYID"

# ---------------------------------------------------------------------------
echo "=== 2/6. Configure git ==="
git config --global user.signingkey "$KEYID"
git config --global tag.gpgsign true
git config --global gpg.program gpg
echo "  user.signingkey = $KEYID"

# ---------------------------------------------------------------------------
echo "=== 3/6. Export public key ==="
PUB="/tmp/rttailscale-${KEYID}.pub.asc"
gpg --armor --export "$KEYID" > "$PUB"
echo
echo "  ┌──────────────────────────────────────────────────────────────┐"
echo "  │ ACTION REQUIRED (one time, ~30 seconds)                      │"
echo "  │                                                              │"
echo "  │ 1. Open https://github.com/settings/gpg/new in a browser     │"
echo "  │ 2. Copy the key printed below                                │"
echo "  │ 3. Paste it, give it any title, click 'Add GPG key'          │"
echo "  │ 4. Come back here and press ENTER                            │"
echo "  └──────────────────────────────────────────────────────────────┘"
echo
sed 's/^/  /' "$PUB"
echo
read -rp "  Press ENTER once the key is on GitHub... " _ || true

# Verify GitHub recognized the key before continuing
echo "  verifying GitHub sees the key..."
sleep 3
if gh api user/gpg_keys --jq '.[].key_id' 2>/dev/null | grep -q "$KEYID"; then
  echo "  ✅ GitHub has the key"
else
  echo "  ⚠ GitHub API does not show key $KEYID yet — continuing anyway."
  echo "    If verify-tag fails later, wait 30s and retry."
fi

# ---------------------------------------------------------------------------
echo "=== 4/6. Re-sign v0.1.0 ==="
git tag -d v0.1.0 2>/dev/null || true
git tag -s v0.1.0 -m "Rt:Tailscale-M 0.1.0 (audit-corrected, device-verified)"
git push --force origin v0.1.0
git verify-tag v0.1.0
echo "  ✅ v0.1.0 signed and pushed"

# ---------------------------------------------------------------------------
echo "=== 5/6. Patch build.sh for reproducibility ==="
if grep -q 'SOURCE_DATE_EPOCH' build.sh; then
  echo "  already patched"
else
  python3 - <<'PY'
from pathlib import Path
p = Path("build.sh")
s = p.read_text()
anchor = "set -euo pipefail"
inject = anchor + '\nexport SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git log -1 --format=%ct 2>/dev/null || date +%s)}"\nexport TZ=UTC'
if anchor in s and 'SOURCE_DATE_EPOCH' not in s:
    s = s.replace(anchor, inject, 1)
anchor2 = 'rm -f "$OUT"'
inject2 = 'find "$STAGE" -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} +\nrm -f "$OUT"'
if anchor2 in s and 'touch -h -d "@$SOURCE_DATE_EPOCH"' not in s:
    s = s.replace(anchor2, inject2, 1)
p.write_text(s)
print("  build.sh patched")
PY
fi

# ---------------------------------------------------------------------------
echo "=== 6/6. Reproducible build + SBOM ==="
if ! command -v syft >/dev/null 2>&1; then
  echo "  installing syft..."
  curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh \
    | sudo sh -s -- -b /usr/local/bin >/dev/null
fi

rm -rf dist
./build.sh
H1=$(sha256sum dist/*.muxapp | cut -d' ' -f1)

rm -rf dist
./build.sh
H2=$(sha256sum dist/*.muxapp | cut -d' ' -f1)

if [ "$H1" = "$H2" ]; then
  echo "  ✅ reproducible: $H1"
else
  echo "  ❌ NOT reproducible"
  echo "     build1: $H1"
  echo "     build2: $H2"
  exit 1
fi

syft dist/RtTailscale-M-0.1.0.muxapp -o cyclonedx-json > dist/RtTailscale-M-0.1.0.sbom.json
echo "  ✅ SBOM: $(wc -c < dist/RtTailscale-M-0.1.0.sbom.json) bytes"

gh release upload v0.1.0 dist/RtTailscale-M-0.1.0.muxapp --clobber
gh release upload v0.1.0 dist/RtTailscale-M-0.1.0.muxapp.sha256 --clobber
gh release upload v0.1.0 dist/RtTailscale-M-0.1.0.sbom.json --clobber

if ! git diff --quiet build.sh; then
  git add build.sh
  git commit -m "build: reproducible builds (SOURCE_DATE_EPOCH, normalized mtimes)"
  git push origin HEAD:main
  git tag -d v0.1.0
  git tag -s v0.1.0 -m "Rt:Tailscale-M 0.1.0 (reproducible)"
  git push --force origin v0.1.0
  echo "  ✅ build.sh committed, tag re-signed"
fi

echo
echo "============================================================"
echo "  Salto 1 complete."
echo "============================================================"
