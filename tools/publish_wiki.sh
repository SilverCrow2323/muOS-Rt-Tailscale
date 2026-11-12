#!/bin/sh
set -eu

REPO_URL="https://github.com/SilverCrow2323/muOS-Rt-Tailscale.wiki.git"
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
SOURCE="$ROOT/wiki-source"
TMP="$(mktemp -d)"
WIKI="$TMP/wiki"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT HUP INT TERM

if ! git clone "$REPO_URL" "$WIKI"; then
    echo "Create and save the GitHub Wiki Home page once, then rerun this script." >&2
    exit 2
fi

for page in "$SOURCE"/*.md; do
    [ -f "$page" ] || continue
    [ "$(basename "$page")" = "README.md" ] && continue
    cp "$page" "$WIKI/"
done

cd "$WIKI"
git add -- *.md
if git diff --cached --quiet; then
    echo "Wiki is already up to date."
    exit 0
fi

git -c user.name="Rt:Tailscale-M Wiki Publisher" \
    -c user.email="rttailscale-wiki@users.noreply.github.com" \
    commit -m "docs: publish Rt:Tailscale-M field guide"
git push origin HEAD
