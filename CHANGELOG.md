# Changelog

## 0.1.0

### Audit fixes (2026-11-01)

- `VERSION` normalized to `0.1.0` and tagged `v0.1.0`
- All Italian UI strings translated to English
- PIN: 8 digits for new installs
- New `PANEL_BIND` option (default `0.0.0.0`; set `127.0.0.1` for LAN-only)
- `serve` and `funnel` blocked in the CLI console
- `THIRD-PARTY.md` rewritten with the real library list
- `CREDITS.md` added; derivation notice added to `LICENSE`
- README: removed "not yet verified" warning (verified on real hardware),
  added Security section
- Documented the build environment


First release of Rt:Tailscale-M: the muOS Andromeda port of Rt:Tailscale-K, successor of *Shin RtTailscale*.

- Graphical app (LÖVE 11.5, bundled runtime) styled after the Tailscale web client; icon-only button legend; Nintendo layout by default;
  quit with SELECT+START; light and dark theme; login by QR code.
- Service stack: daemon + watchdog + web panel + Taildrop receiver; TUN with automatic userspace fallback.
- Start at boot through a muOS user init script (also switches on *User Init Scripts*).
- `rt adopt`: take over another Tailscale app's identity and disable its init script.
- Packaging: `.muxapp` with a pinned LÖVE runtime trimmed to the 9 libraries `love` needs (`--full-love` ships all).
- Test suite: 21 integration checks with the real arm64 Tailscale under qemu-user, Lua unit tests, QR verification, UI render.
