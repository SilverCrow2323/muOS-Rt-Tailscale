# Install Rt:Tailscale-M

This guide installs the published muOS application package. The app includes its own LÖVE 11.5 runtime; you do not need to install LÖVE separately.

## Before you begin

- Use a release package intended for muOS Andromeda.
- Keep a backup of the SD card and existing Tailscale state.
- Make sure the handheld can reach the network for the first login.

> [!IMPORTANT]
> **MUST KNOW!!** Download the `.muxapp` from [GitHub Releases](https://github.com/SilverCrow2323/muOS-Rt-Tailscale/releases). Do not install the repository source ZIP as an application package.

## Install from Archive Manager

1. Download `RtTailscale-M-<version>.muxapp`.
2. Copy it to the SD card's `ARCHIVE/` folder.
3. Open **Applications → Archive Manager**.
4. Install the package.
5. Launch **Applications → Tailscale**.

## Install by extracting the package

- Extract the archive so the application directory is `MUOS/application/RtTailscale/`.
- Confirm that `mux_launch.sh` is directly inside that directory.
- Keep the directory and launcher names intact.

## Existing installations

- Installing over **Shin RtTailscale** keeps the existing login and settings.
- To import another Tailscale app's identity, use **System → Take over another Tailscale install** and follow the on-screen status.

## Next step

Open [First connection](First-connection) to log in and enable startup.
