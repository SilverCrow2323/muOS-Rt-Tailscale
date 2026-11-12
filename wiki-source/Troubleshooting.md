# Troubleshooting

Start with **System → Run diagnostics** in the app or `./rt doctor` over SSH. Include the output in a bug report after removing secrets and personal identifiers.

## Common problems

| Symptom | First check |
|---|---|
| App missing from Applications | Verify the installed folder contains `mux_launch.sh` and that the package was installed from Archive Manager |
| App exits immediately | Read `.game/rttailscale.log`; check that the bundled LÖVE runtime and libraries are present |
| A/B buttons feel swapped | Change **Settings → Nintendo button layout** |
| Login waits for a link | Check Wi-Fi, DNS and system time; run `./ts netcheck` |
| Login is lost after reboot | Check that `state/tailscaled.state` persists and is writable |
| Start at boot does nothing | Run `./rt doctor`; check **Advanced settings → User Init Scripts** |
| Panel cannot be reached | Check the address/PIN in the Panel tab, Python availability and port 8077 |
| Tailscale restarts repeatedly | Check for another Tailscale daemon or init script; inspect `/tmp/tailscaled.log` |
| Binaries are missing | Run `./rt update` or install a release package containing the ARM64 binaries |

## Logs to collect

- `./rt doctor`
- `./rt log 50`
- `tail -n 50 /tmp/tailscaled.log`
- `.game/rttailscale.log`

## Report a bug

Include the handheld model, muOS version, app release, reproduction steps and redacted diagnostic output.

> [!IMPORTANT]
> **MUST KNOW!!** Never attach `state/tailscaled.state`, auth keys, the web-panel PIN, `panel.key`, private IP inventories or unredacted network logs to a public issue.
