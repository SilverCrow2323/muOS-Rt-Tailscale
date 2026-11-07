# Architecture

```
 muOS > Applications > Tailscale > mux_launch.sh -- rt ensure --------------+
                                  |                                          |
                                  +--> LOVE (.game/main.lua)  background jobs|
                                            |  ts status --json              v
 muOS boot > init/rttailscale.sh --> rt boot --> tailscaled <--socket-- ts (tailscale CLI)
                                           |-- watchdog   (every 10 s: rt ensure)
                                           |-- panel/server.py  (HTTP :8077, PIN)  <-- phone / PC browser
                                           `-- tailscale file get --loop  (Taildrop)
```

The **service layer** (`rt`, `watchdog`, `panel/`) is independent of the **UI** (`.game/`): use either alone.

## Components

| Component | Language | Role |
|---|---|---|
| `mux_launch.sh` | sh | muOS entry point: SETUP_APP, LÖVE environment, `rt install` + `rt ensure`, runs `love` |
| `rt` | POSIX sh | start/stop everything, config, PIN, init script, install, update, adopt, doctor, `summary` for the UI |
| `watchdog` | POSIX sh | `rt ensure` every 10 s; restarts a daemon stuck in *Starting* |
| `ts` | POSIX sh | the real `tailscale` CLI bound to our socket |
| `panel/server.py` | Python 3 (stdlib) | PIN-protected HTTP API + single-page UI over the CLI |
| `.game/main.lua` | Lua (LÖVE 11.5) | gamepad UI, QR login, background jobs |
| `.game/lib/*.lua` | Lua | `model` (parsing), `json`, `qr`, `input` (button mapping), `theme`, `icons` - the first four are unit-tested without LÖVE |

## Process model and flags

- Long-lived processes start with `SPAWN`: `setsid sh -c 'echo $$ >pidfile; exec cmd'`, so the PID file holds the real PID.
- Liveness (`PF_ALIVE`) = PID exists **and** `/proc/PID/cmdline` matches: no false positives from recycled PIDs, no double start.
- Runtime files live in `$RT_RUN` (default `/tmp/rttailscale`); the daemon socket in `/var/run/tailscale/`.
- Two flags there: `stopped` (daemon stopped on purpose; panel and watchdog stay up so you can restart it) and
  `stopped_all` (`rt stop`: nothing may be restarted until `rt start` / next boot). `ensure` re-checks `stopped_all`
  after the slow daemon start so an in-flight watchdog pass cannot resurrect things after a stop (found by the integration test).

## Boot

1. muOS runs `init/rttailscale.sh` (if *User Init Scripts* is on): `setsid "<app>/rt" boot &`, and returns at once.
2. `rt boot` waits (up to `WIFI_WAIT` s, default 120) for a default route, then runs `ensure`.
3. `ensure` -> `DAEMON_START`: prepares `/dev/net/tun`, starts `tailscaled --tun=tailscale0`; if the socket does not appear
   and `TS_MODE=auto`, restarts with `--tun=userspace-networking`. Then panel, Taildrop receiver and watchdog.

## State and secrets

`state/tailscaled.state` is the node identity (treat it like a password). `config/panel.pin` + `panel.key`: `rt pin new`
regenerates both, which also invalidates every open session. `config/rt.conf` holds the settings. `MIGRATE_STATE` imports an
identity from the muOS 2601 built-in Tailscale, the community app, or an older Rt:Tailscale.

## On-device UI

Fixed 640x480 canvas scaled with letterboxing; every command is a background job polled in `love.update`; `rt summary`,
`ts status --json`, `ts debug prefs` and `rt urls` are polled every 4 s (1.5 s during login). Login runs `ts up --timeout=0`
in the background (PID saved so *Cancel* can kill it), reads `AuthURL` from `status --json` and draws it as a QR code.
`RTTS_FAKE_DIR` swaps every command for canned files and `RTTS_DEMO` renders screenshots: used by the docs and the tests.

## Web panel

Python standard library only. HMAC-SHA256 signed session cookie (`HttpOnly`, `SameSite=Strict`), five wrong PINs lock the
client out (1 min, growing to 15), requests need the `X-Rt` header (CSRF guard). Updates download the official
`tailscale_<ver>_arm64.tgz`, verify its sha256 and swap the binaries keeping `.bak` copies (`rt update` runs the same code).
