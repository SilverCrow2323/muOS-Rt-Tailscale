# Troubleshooting

First step, always: **System → Run diagnostics** in the app, or `./rt doctor` over SSH. Attach its output when you report a
problem, with `./rt log 50` and `tail -n 50 /tmp/tailscaled.log`; the app's own log is `.game/rttailscale.log`.

| Symptom | Likely cause | Fix |
|---|---|---|
| Not in the Applications list | archive not installed, or extracted with a different structure | the `.muxapp` must contain one folder (`RtTailscale/`) with `mux_launch.sh`; install via *Archive Manager* or unzip into `MUOS/application/` |
| App opens and returns to the menu at once | the LÖVE runtime cannot start (missing library) or `mux_launch.sh` lost its exec bit | read `.game/rttailscale.log`; rebuild with `--full-love` or copy `libs.aarch64` from a LÖVE app that works; `chmod +x mux_launch.sh .game/bin/love` |
| Buttons A/B (or X/Y) feel swapped | layout differs from the Nintendo default | *Settings → Nintendo button layout* |
| Stays on "Waiting for the login link..." | no internet/DNS yet, or clock far off | check Wi-Fi; `./ts netcheck`; look for "failed to resolve" in `/tmp/tailscaled.log`; make sure the device time is right |
| Asks to log in again after every reboot | `state/` not persistent or not writable | check `state/tailscaled.state` exists after login; do not run the app from a read-only location |
| "Start at boot" on, nothing starts | *User Init Scripts* is off, or the boot wait is too short | `./rt doctor` tells you; enable *Advanced settings → User Init Scripts*; raise `WIFI_WAIT` in `config/rt.conf` |
| Connected, but other apps cannot reach tailnet IPs | userspace mode (no TUN) | `rt doctor` says "no TUN device"; use `tailscale ssh`, `./ts ping`, or the SOCKS5/HTTP proxy settings in the web panel (System) |
| Web panel unreachable | `python3` missing, wrong URL, port busy | `rt doctor`; the URL is on the *Panel* tab; change `PANEL_PORT` in `config/rt.conf` |
| Forgot the PIN | - | `./rt pin` shows it, `./rt pin new` makes a new one |
| `tailscaled` restarts in a loop | corrupt state, or two Tailscale daemons | `rt doctor` warns about another init script: `./rt adopt`; read `/tmp/tailscaled.log` |
| "binaries missing in bin/" | archive built with `--no-bin`, or update failed | `./rt update` (internet + python3), or copy arm64 `tailscale` and `tailscaled` into `bin/` |
| Slow right after boot | Wi-Fi still connecting | normal; the watchdog restarts a daemon stuck in *Starting* |

## Resetting

- Log out only: *Status → Log out of this tailnet*.
- Forget this device completely: `./rt stop`, delete `state/`, remove the device in your Tailscale admin console, start again.
- Default settings: delete `config/rt.conf`.

## Reporting a bug

Open an issue with: device model, muOS version, what you did and expected, the diagnostics output and the log excerpts above.
Remove auth keys and the PIN from anything you paste.
