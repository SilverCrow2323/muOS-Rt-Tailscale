# Rt:Tailscale-M — field guide

Rt:Tailscale-M runs the official Tailscale client as a background service on muOS Andromeda and provides a controller-friendly interface for login, device status, exit nodes, settings and Taildrop.

## Start here

- [Install the app](Installation)
- [Learn the controls](Controls)
- [Connect your device](First-connection)
- [Manage the service from SSH](Service-and-CLI)
- [Use the web panel and Taildrop](Web-Panel-and-Taildrop)
- [Fix common problems](Troubleshooting)
- [Uninstall or reset safely](Uninstall-and-Recovery)

> [!IMPORTANT]
> **MUST KNOW!!** The `state/` directory contains the Tailscale node identity. Treat it like a password. Never post it, upload it to an issue or include it in a public backup.

## What the app provides

- Official ARM64 `tailscale` and `tailscaled` binaries.
- QR-based login, so you do not need to type an auth URL with the D-pad.
- A background service, boot integration and watchdog.
- Device/exit-node controls and a PIN-protected web panel.
- Taildrop into the app's `taildrop/` directory.

## Project links

- [Latest releases](https://github.com/SilverCrow2323/muOS-Rt-Tailscale/releases)
- [Source repository](https://github.com/SilverCrow2323/muOS-Rt-Tailscale)
- [Technical documentation](https://github.com/SilverCrow2323/muOS-Rt-Tailscale/tree/main/docs)
- [Report a problem](https://github.com/SilverCrow2323/muOS-Rt-Tailscale/issues)
