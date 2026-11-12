# Manage the service

The UI manages the same local service stack exposed by the `rt` and `ts` command-line tools. Use the app for normal operation; SSH is useful for diagnostics and recovery.

## Open an SSH session

Go to the installed application directory, normally:

```sh
cd /mnt/mmc/MUOS/application/RtTailscale
```

The exact mount point may differ between SD layouts. Use the actual path of the installed folder.

## Common commands

| Command | Purpose |
|---|---|
| `./rt install` | Create/check the service folders and permissions |
| `./rt start` | Start the daemon, watchdog and web panel |
| `./rt autostart on` | Enable boot start |
| `./rt doctor` | Run the health checks |
| `./rt pin` | Display the current web-panel PIN |
| `./rt pin new` | Rotate the PIN and invalidate active panel sessions |
| `./ts up` | Start Tailscale login from the CLI |
| `./ts status` | Query the local Tailscale daemon |

## Useful log locations

- App log: `.game/rttailscale.log`
- Daemon log: `/tmp/tailscaled.log`
- Diagnostics: run **System → Run diagnostics** or `./rt doctor`.

> **Optional** — Run the CLI directly when the UI cannot be opened. The `./ts` wrapper talks to the daemon managed by this app; do not start an unrelated second daemon.
