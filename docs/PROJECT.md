# Project: Rt:Tailscale for muOS

## Purpose
Provide a self-contained Tailscale service manager and controller-friendly status panel for muOS handhelds. The service layer can run independently of the LÖVE UI and keeps the daemon, watchdog, web panel and Taildrop receiver under one application directory.

## Users and use cases
- muOS handheld owners connecting a device to an existing tailnet.
- Maintainers installing/updating the arm64 Tailscale binaries and migrating an existing node identity.
- Users checking status and managing a device from the handheld or a PIN-protected local web panel.

## Scope and boundaries
In scope: daemon lifecycle, userspace/kernel TUN fallback, watchdog, autostart, node-state migration, config, panel authentication, Taildrop and status/diagnostics.

Out of scope: operating as a general VPN manager for unrelated Linux systems, exposing the local panel without authentication, silently replacing a user's Tailscale identity, or writing outside the app directory except the documented muOS init hook and runtime paths.

## Target
- muOS on Anbernic RG35XX H/H700 and compatible ARM64 handhelds.
- POSIX shell service scripts, Tailscale arm64 binaries, Python 3 stdlib panel, LuaJIT/LÖVE 11.5 UI.
- Host checks via shellcheck, LuaJIT, Python and Xvfb; optional QEMU integration tests.

## Architecture
- rt: service manager, config, daemon, panel, Taildrop and autostart commands.
- watchdog: daemon liveness and recovery.
- panel/server.py: PIN-protected local HTTP API.
- LÖVE UI: status, QR login, peers and background jobs.
- tests/run_all.sh: shell, Lua, parser, QR, i18n and optional UI/device integration checks.

## Dependencies and integration
Tailscale upstream arm64 binaries, muOS user-init and MUX launcher contracts, LÖVE 11.5, Python 3 and LuaJIT. State and credentials are device-owned and must never be copied into source control.

## Security and accessibility
Node state is a credential. Panel PIN/key and config containing SOCKS5/HTTP proxy values must be owner-only. Keep TLS verification enabled, bind the panel to the documented local interface, redact secrets from logs, validate command arguments and preserve explicit stop semantics. UI must be controller-operable and readable at 640×480.

## Verified baseline
The repository includes service lifecycle scripts, migration, panel, UI and host tests. The quality workflow runs tests/run_all.sh; physical muOS/Tailscale network behavior remains a separate device test.
