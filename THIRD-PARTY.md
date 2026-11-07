# Third-party components

| Component | Where | License |
|---|---|---|
| Tailscale `tailscale`, `tailscaled` (arm64) | `bin/` | BSD-3-Clause (`bin/LICENSE.tailscale`) — © Tailscale Inc. |
| Inter typeface | `.game/fonts/` | SIL OFL 1.1 (`.game/fonts/Inter-LICENSE.txt`) |
| Colour palette (`theme.lua`) | `.game/lib/theme.lua` | derived from tailscale/tailscale (BSD-3-Clause) |
| Tailscale nine-dot mark | `glyph/`, `.game/lib/icons.lua` | geometry from tailscale/tailscale (BSD-3-Clause); trademark of Tailscale Inc. |
| LOVE 11.5 (`love`, `liblove`) | `.game/bin/` | zlib |
| LuaJIT | `.game/bin/libs.aarch64/` | MIT |

## Bundled aarch64 libraries (default build)

The default build ships **only** the libraries `love` needs, resolved at
build time with `tools/needed_libs.py` (via `readelf`):

- `liblove-11.5.so`
- `libluajit-5.1.so.2`
- `libfreetype.so.6`
- `libz.so.1`
- `libpng16.so.16`
- `libogg.so.0`
- `libmodplug.so.1`
- `libbrotlicommon.so.1`
- `libbrotlidec.so.1`

SDL2, OpenAL, libc, libstdc++ and other system libraries come from muOS
itself, not from this package.

A `--full-love` build ships the full 73 MB `libs.aarch64` tree (Qt6, ICU,
Kerberos, …). **Use it only as a fallback** if the trimmed build fails to
start on a specific device; report it with `System → Run diagnostics`.
