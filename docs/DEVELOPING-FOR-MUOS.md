# Developing apps for muOS (MustardOS) Andromeda

Written while building Rt:Tailscale-M. Statements are tagged:

- **[verified]** - taken from working muOS apps' source (the launchers of *rgTrek* and *muSudoku*, both LÖVE 11.5 apps) or
  from this repository's tests.
- **[inherited]** - used by the earlier muOS Tailscale apps by the same author on real devices; not re-checked here.
- **[assumed]** - convention/guess; check it on your device (commands given).

---

## 1. What an app is

An application is a **folder** in `MUOS/application/` (on either SD card). muOS lists every folder that contains a
`mux_launch.sh`. It is distributed as a **`.muxapp`**: a zip with exactly one top-level folder, installed through
*Applications → Archive Manager*. [verified]

```
RtTailscale/
├── mux_launch.sh        executable; the first lines are comment headers read by muOS:
│                          # HELP: text shown in the app's help      # ICON: glyph name      # GRID: label in the grid
├── mux_lang.ini         [full] [grid] [help] sections, one line per language (English=...)
├── glyph/<name>.png|svg the icon, 64x64 PNG (+ SVG)
├── .game/               hidden folder with the LÖVE game (main.lua ...) and its runtime in .game/bin
└── your own files
```

## 2. The launcher

```sh
#!/bin/sh
# HELP: ...   # ICON: rttailscale   # GRID: Tailscale
. /opt/muos/script/var/func.sh          # SETUP_APP, GET_VAR, SET_VAR, CAFFEINE ...   [verified]
SETUP_STAGE_OVERLAY
SETUP_APP "love" ""                     # CPU governor + SDL environment for the app    [verified]
SCREEN_WIDTH="$(GET_VAR device mux/width)"; SCREEN_HEIGHT="$(GET_VAR device mux/height)"   [verified]
export SDL_GAMECONTROLLERCONFIG_FILE="/usr/lib/gamecontrollerdb.txt"                         [verified]
SET_VAR "system" "foreground_process" "love"
"$APP/.game/bin/love" . "${SCREEN_WIDTH}x${SCREEN_HEIGHT}"
```
See [`app/RtTailscale/mux_launch.sh`](../app/RtTailscale/mux_launch.sh), which also handles older releases that lack
`SETUP_APP`. Habits worth copying:

- Derive the app folder from `$0`, keep muOS paths (`/run/muos/storage/application/...`) only as fallbacks. [verified]
- `LD_LIBRARY_PATH`: system library directories **first**, your bundled libraries last, so your copies are only
  fallbacks. [verified]
- Log the game's output to a file in the app folder - it is the only way to see errors on a device without a terminal.
- Opening the app can start background work (here: `rt ensure`); do it before `love` and never block.

## 3. LÖVE on muOS

muOS ships **no LÖVE**. Every LÖVE app bundles an aarch64 LÖVE 11.5: `bin/love` plus `bin/libs.aarch64/`. [verified]
Rt:Tailscale-M takes the runtime from the MIT-licensed `saitamasahil/2048plus` repository (tag `v7.0.1`), **pinned by
commit and SHA-256** in `build.sh`.

That repository's `libs.aarch64` is 73 MB because it also holds Qt6, ICU, Kerberos... that have nothing to do with LÖVE.
`tools/needed_libs.py` follows the `NEEDED` entries of `love` with `readelf` and finds the real set: **9 libraries, 6 MB**
(`liblove-11.5`, `luajit`, `freetype`, `zlib`, `libpng`, `libogg`, `libmodplug`, `brotli` x2). SDL2, OpenAL, mpg123,
vorbisfile, theoradec, libc and libstdc++ are expected from muOS itself. If an app fails to start with a "cannot open shared
object file" line in its log, that is the first thing to suspect: build with `--full-love`, or copy the whole
`libs.aarch64` from a LÖVE app that works on your device.

Game code tips (same as for any handheld):

- Draw on a fixed canvas and scale it to `love.graphics.getDimensions()` (screens differ: 640x480, 720x480, 720x720...).
- Use the gamepad API (`love.gamepadpressed`); names are SDL's, by position: `a` = bottom, `b` = right, `x` = left, `y` = top.
  Anbernic handhelds print A on the right and B at the bottom, so offer a layout switch (see `game/lib/input.lua`).
- Run shell commands as **background jobs** and poll them; `io.popen():read()` freezes the frame loop.
- Quit with SELECT+START held together; START alone should not close an app that uses it.
- Disable the LÖVE modules you do not use in `conf.lua`.

## 4. Starting something at boot

muOS runs every executable in the **user init folder**, `/run/muos/storage/init/` [inherited], when
*Advanced settings → User Init Scripts* is on - stored as `settings/advanced/user_init` in the muOS config, readable and
settable with `GET_VAR`/`SET_VAR "config" ...` after `. /opt/muos/script/var/config.sh` [inherited].

Rules for an init script: it must return immediately (start your work with `setsid ... &`), must not assume Wi-Fi is up
(wait for a default route inside the detached part), and should be removable by the app that installed it. `rt autostart on`
does exactly this and `rt doctor` checks that the setting is really on.

## 5. Testing without a device

Everything below is automated in `tests/`:

1. **UI headless**: `xvfb-run -a env LIBGL_ALWAYS_SOFTWARE=1 RTTS_FAKE_DIR=tests/fixtures RTTS_DEMO=/tmp/shot love app/RtTailscale/game`
   renders each screen to a PNG. Inject your data through an environment variable and you can test every state.
2. **aarch64 binaries on x86**: `qemu-aarch64-static` runs static binaries (Tailscale is one). `tests/run_integration.sh`
   wraps the real arm64 `tailscaled` so the real service scripts run unmodified.
3. **Make paths overridable** (`RT_RUN`, `RT_SOCK`, `RT_INIT_DIR`, `RTTS_DIR`) so scripts can run outside `/mnt/mmc`.
4. **Verify generated data against a reference** (the QR encoder is compared bit-for-bit with python-qrcode).
5. `shellcheck -s sh` for scripts; `luajit -bl file.lua /dev/null` for Lua syntax.

What this cannot tell you: real controller mapping, real screen size, the real boot sequence, kernel features such as TUN.

## 6. Pitfalls

| Pitfall | Fix |
|---|---|
| Archive extracted without exec bits | `chmod +x` at start (`rt install` does), build with `zip -X` |
| Init script blocks the boot | detach with `setsid ... &` |
| *User Init Scripts* is off | the init script silently never runs: check/set it from the app |
| Two Tailscale apps/daemons | `rt adopt`: disable the other init script, import its identity, stop its daemon |
| Missing shared library | read the game's log; see §3 |
| Wrong clock after boot (no battery-backed clock) | do not treat the first TLS/auth failure as fatal [assumed] |
| Assuming a keyboard | gamepad API, plus QR/web panel for anything that needs typing |

## Sources

- muOS community: *Application Runner* FAQ <https://community.muos.dev/t/application-runner/1282>;
  *Tailscale for MustardOS (Andromeda)* <https://community.muos.dev/t/tailscale-for-mustardos-andromeda/1730> (another, text-menu, Tailscale app)
- Working LÖVE apps for muOS: <https://github.com/ctanas/rgtrek>, <https://github.com/ctanas/musudoku>
- LÖVE runtime source: <https://github.com/saitamasahil/2048plus> (tag v7.0.1)
- LÖVE: <https://love2d.org>

## Build environment

The release `.muxapp` is produced by `./build.sh`. It has been built and
exercised in two environments:

1. **Local Linux (x86_64)** with `zip`, `curl`, `git`, `python3` and
   `readelf` (binutils). `build.sh` downloads the arm64 Tailscale tarball
   from `pkgs.tailscale.com` (sha256-verified) and the pinned LÖVE 11.5
   arm64 runtime from `saitamasahil/2048plus` (commit + sha256 in-script).
2. **GitHub Actions CI** on `ubuntu-24.04` — see `.github/workflows/ci.yml`.

The build needs **network access** to `pkgs.tailscale.com` and to GitHub.
Earlier notes referred to a "build sandbox" without network access; that
was a temporary local restriction, not the default environment, and is not
required for a reproducible build.
