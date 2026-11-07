#!/bin/bash
export LC_ALL=C
export LANG=C
# Build the muOS application archive.
#
#   ./build.sh                       download Tailscale (arm64) and the LOVE 11.5 runtime and bundle both
#   ./build.sh --bin-dir DIR         use the tailscale + tailscaled (arm64) found in DIR
#   ./build.sh --love-dir DIR        use DIR/bin/love + DIR/bin/libs.aarch64 instead of downloading the runtime
#   ./build.sh --full-love           ship EVERY library of the runtime (73 MB) instead of the 9 that love needs (6 MB)
#   ./build.sh --no-bin | --no-love  leave Tailscale / the LOVE runtime out (Tailscale is then downloaded on first start)
#
# Output: dist/RtTailscale-M-<version>.muxapp (a zip with one folder, RtTailscale/) + .sha256
# Install on the device: muOS > Archive Manager (put the file in an ARCHIVE folder), or unzip into MUOS/application/.
set -euo pipefail
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git log -1 --format=%ct 2>/dev/null || date +%s)}"
export TZ=UTC
cd "$(dirname "$0")"

BIN_DIR=""; LOVE_DIR=""; FULL_LOVE=0; NO_BIN=0; NO_LOVE=0
while [ $# -gt 0 ]; do
	case "$1" in
		--bin-dir) BIN_DIR="${2:?--bin-dir needs a path}"; shift 2 ;;
		--love-dir) LOVE_DIR="${2:?--love-dir needs a path}"; shift 2 ;;
		--full-love) FULL_LOVE=1; shift ;;
		--no-bin) NO_BIN=1; shift ;;
		--no-love) NO_LOVE=1; shift ;;
		-h | --help) sed -n '2,11p' "$0"; exit 0 ;;
		*) echo "unknown option: $1" >&2; exit 1 ;;
	esac
done
command -v zip >/dev/null || { echo "zip is required (apt install zip)" >&2; exit 1; }

# The aarch64 LOVE 11.5 runtime used by working muOS apps (MIT-licensed 2048 Plus repo), pinned:
LOVE_REPO="https://github.com/saitamasahil/2048plus.git"
LOVE_TAG="v7.0.1"
LOVE_COMMIT="abdec7092178881f0f5e271503c78f69c89b9d8e"
LOVE_SHA256="c6c64453ed6163c8aeb14d303bad1e4d9ecc4d628097b3c6420ada2fa6a8690f"            # bin/love
LIBLOVE_SHA256="a50c83729cb0e1c4d8389eaaa827f0a6e7f3362814d0504ca84074dd0e47c379"         # bin/libs.aarch64/liblove-11.5.so

VERSION=$(cat app/RtTailscale/VERSION)
STAGE=$(mktemp -d); trap 'rm -rf "$STAGE"' EXIT
APP="$STAGE/RtTailscale"
mkdir -p "$APP" dist

# --- the app itself (game/ becomes the hidden .game/ folder muOS apps use)
(cd app/RtTailscale && tar --exclude='./bin/*' --exclude='./state' --exclude='./taildrop' --exclude='./config/rt.conf' \
	--exclude='./config/panel.*' --exclude='./.game' --exclude='./game' -cf - .) | tar -xf - -C "$APP"
mkdir -p "$APP/bin" "$APP/.game/bin"
cp -r app/RtTailscale/game/. "$APP/.game/"
cp LICENSE THIRD-PARTY.md "$APP/"

# --- Tailscale binaries
fetch_tailscale() {
	local tmp ver url want
	tmp=$(mktemp -d)
	ver=$(curl -fsSL 'https://pkgs.tailscale.com/stable/?mode=json' | python3 -c 'import sys,json; print(json.load(sys.stdin)["TarballsVersion"])')
	url="https://pkgs.tailscale.com/stable/tailscale_${ver}_arm64.tgz"
	echo "downloading Tailscale $ver (arm64)..."
	curl -fsSL "$url" -o "$tmp/ts.tgz"
	want=$(curl -fsSL "$url.sha256" | awk '{print $1}')
	echo "$want  $tmp/ts.tgz" | sha256sum -c - >/dev/null || { echo "sha256 mismatch" >&2; exit 1; }
	tar -xzf "$tmp/ts.tgz" -C "$tmp" --strip-components=1
	cp "$tmp/tailscale" "$tmp/tailscaled" "$APP/bin/"
	rm -rf "$tmp"
}
if [ "$NO_BIN" = 0 ]; then
	if [ -n "$BIN_DIR" ]; then cp "$BIN_DIR/tailscale" "$BIN_DIR/tailscaled" "$APP/bin/"; [ -f "$BIN_DIR/LICENSE.tailscale" ] && cp "$BIN_DIR/LICENSE.tailscale" "$APP/bin/"; else fetch_tailscale; fi
fi

# --- LOVE runtime
if [ "$NO_LOVE" = 0 ]; then
	if [ -z "$LOVE_DIR" ]; then
		LOVE_DIR=".cache/love-$LOVE_TAG"
		if [ ! -f "$LOVE_DIR/bin/love" ]; then
			echo "downloading the LOVE 11.5 aarch64 runtime ($LOVE_REPO $LOVE_TAG)..."
			rm -rf "$LOVE_DIR"; mkdir -p .cache
			git -c advice.detachedHead=false clone --quiet --depth 1 --branch "$LOVE_TAG" --filter=blob:none --sparse "$LOVE_REPO" "$LOVE_DIR"
			git -C "$LOVE_DIR" sparse-checkout set bin >/dev/null
			[ "$(git -C "$LOVE_DIR" rev-parse HEAD)" = "$LOVE_COMMIT" ] || { echo "unexpected commit in $LOVE_REPO $LOVE_TAG" >&2; exit 1; }
		fi
		echo "$LOVE_SHA256  $LOVE_DIR/bin/love" | sha256sum -c - >/dev/null || { echo "love: sha256 mismatch" >&2; exit 1; }
		echo "$LIBLOVE_SHA256  $LOVE_DIR/bin/libs.aarch64/liblove-11.5.so" | sha256sum -c - >/dev/null || { echo "liblove: sha256 mismatch" >&2; exit 1; }
	fi
	cp "$LOVE_DIR/bin/love" "$APP/.game/bin/love"
	mkdir -p "$APP/.game/bin/libs.aarch64"
	if [ "$FULL_LOVE" = 1 ]; then
		cp -r "$LOVE_DIR/bin/libs.aarch64/." "$APP/.game/bin/libs.aarch64/"
	else
		# only what `love` needs (resolved with readelf); SDL2, OpenAL, libc... come from muOS
		LIBS=$(python3 tools/needed_libs.py "$LOVE_DIR/bin" | grep -v "^$" || true)
		if [ -z "$LIBS" ]; then echo "ERROR: no libraries resolved by tools/needed_libs.py." >&2
			echo "  Try: readelf -d \"$LOVE_DIR/bin/love\" | head   (must show \"Shared library:\")" >&2
			echo "  Or rebuild with --full-love (73 MB) as a fallback." >&2; exit 1; fi
		while read -r lib; do cp "$LOVE_DIR/bin/libs.aarch64/$lib" "$APP/.game/bin/libs.aarch64/"; done <<< "$LIBS"
	fi
fi

chmod +x "$APP/mux_launch.sh" "$APP/rt" "$APP/watchdog" "$APP/ts" 2>/dev/null || true
[ -f "$APP/bin/tailscale" ] && chmod +x "$APP/bin/tailscale" "$APP/bin/tailscaled"
[ -f "$APP/.game/bin/love" ] && chmod +x "$APP/.game/bin/love"

SUFFIX=""; [ "$NO_BIN" = 1 ] && SUFFIX="-nobin"; [ "$NO_LOVE" = 1 ] && SUFFIX="$SUFFIX-nolove"; [ "$FULL_LOVE" = 1 ] && SUFFIX="$SUFFIX-fulllove"
OUT="dist/RtTailscale-M-${VERSION}${SUFFIX}.muxapp"
find "$STAGE" -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} +
rm -f "$OUT"
(cd "$STAGE" && zip -X -q -r "$OLDPWD/$OUT" RtTailscale)
(cd dist && sha256sum "$(basename "$OUT")" >"$(basename "$OUT").sha256")
echo "built $OUT ($(du -h "$OUT" | cut -f1))"
