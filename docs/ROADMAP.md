# Roadmap — Rt:Tailscale

## M0 — Reliable service lifecycle
- [x] Start/stop/restart/ensure/status for tailscaled.
- [x] Watchdog, explicit stopped/stopped_all state and userspace-networking fallback.
- [x] Migrate node state from supported muOS/community app locations.
- [x] Add PIN-protected panel, QR login and Taildrop receiver.

## M1 — Credential and configuration hardening
- [x] Keep panel PIN/key owner-only.
- [x] Keep proxy credentials and service configuration owner-only.
- [ ] Add regression tests for invalid config keys, malformed URLs and redaction of secrets in diagnostics.
- [ ] Verify state migration never overwrites an existing node identity.

## M2 — Device integration
- [ ] Test kernel TUN and userspace fallback on physical H700 firmware.
- [ ] Test Wi-Fi loss/recovery, boot ordering, explicit stop and repeated daemon restart.
- [ ] Test Taildrop path, conflict rename, storage exhaustion and cancellation.
- [ ] Test panel authentication, session invalidation and LAN/tailnet reachability.

## M3 — Maintenance release
- [ ] Pin upstream binary version and SHA-256 per architecture.
- [ ] Rebuild and verify the muOS .muxapp package.
- [ ] Publish notes with tested muOS version/device matrix and known limitations.

## Acceptance
Config/state files containing credentials are owner-only; no secrets appear in logs; daemon stop cannot be undone by watchdog races; host tests pass; physical network and boot tests are recorded separately.

## Release target
Maintain the current 2.6.x line until config security, binary provenance and physical H700 tests are documented. No release is created by this change.
