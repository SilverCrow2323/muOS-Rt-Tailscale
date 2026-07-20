<p align="center">
  <img src="https://i.ibb.co/TBmdqNW3/muos-20260720-233921.png" width="640" alt="Rt:Tailscale Boot Animation">
</p>

<h1 align="center">🕸️ Rt:Tailscale</h1>
<p align="center">
  <b>The definitive mesh-VPN interface for muOS.</b><br>
  <i>Engineered for performance, built for the handheld.</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/muOS-Compatible-7B68EE?style=flat-square&logo=linux">
  <img src="https://img.shields.io/badge/Python-3-Python?style=flat-square&logo=python&color=3776AB">
  <img src="https://img.shields.io/badge/SDL2-ctypes-FF6F00?style=flat-square">
  <img src="https://img.shields.io/badge/Tailscale-Integrated-3955A3?style=flat-square&logo=tailscale">
  <img src="https://img.shields.io/badge/SPDW-Factory_Lab-00FFCC?style=flat-square">
</p>

---

## 📖 Overview

**Rt:Tailscale** is a lightweight, high-performance GUI application designed specifically for **Anbernic devices** running **muOS (MustardOS)**. This tool eliminates the friction of CLI-based Tailscale management, providing a native, controller-driven interface to control your tailnet, monitor connections, and manage exit nodes — directly from your console.

Built to run seamlessly within the muOS ecosystem, it leverages the `mux_launch.sh` wrapper for optimized process execution. Zero external dependencies. Zero pip packages. Pure Python + SDL2 via ctypes.

<p align="center">
  <img src="https://i.ibb.co/HpnKxWyb/mu-OS-20260720-2341-0.png" width="640" alt="Rt:Tailscale Main Menu">
</p>

---

## 🚀 Key Features

| Feature | Description |
|---------|-------------|
| 🎮 **Native muOS Experience** | Seamless integration with the muOS menu system via `mux_launch.sh` |
| 📡 **Tailnet Control** | Toggle the Tailscale daemon and manage SSH access with a single button press |
| 🌍 **Exit Node Management** | Dynamically list and select your preferred exit nodes |
| 📁 **Taildrop File Transfer** | Send and receive files across your tailnet mesh |
| 🔍 **Netcheck Diagnostics** | Integrated tools to analyze latency, NAT types, and UDP connectivity |
| 🔐 **QR Code Authentication** | Built-in QR code generator for instant device pairing |
| 🎨 **3 Visual Themes** | Tailscale Classic, SPDW Cyberpunk, and SPDW Hybrid |
| ⚡ **Zero-Dep Tech Stack** | Built with pure Python using ctypes to interface directly with SDL2 |
| 🛠️ **Operation Log System** | Persistent logging for troubleshooting and audit |

---

## 📂 Project Structure

```
Rt:Tailscale/
├── glyph/
│   └── icon.png              # Application launcher icon
├── config.ini                # User-defined configurations
├── error_log.txt             # Runtime crash logs & diagnostics
├── font.ttf                  # UI rendering font (local path)
├── lang.json                 # External multilingual support
├── mux_launch.sh             # Entry-point script for muOS
├── tailscale_gui.py          # Core application logic (Python 3 / SDL2)
├── tailscale.png             # Application primary logo
└── README.md                 # This file
```

---

## 📥 Installation

### 1. Deploy
Copy the entire `Rt:Tailscale/` directory to your muOS applications path:

```bash
/mnt/mmc/MUOS/application/Rt:Tailscale/
```

### 2. Verify Assets
Ensure all files from the structure above are present, especially:
- `font.ttf` — Required for UI text rendering
- `tailscale.png` — Application logo
- `glyph/icon.png` — Launcher icon for muOS menu

### 3. Execution
The app is designed to be launched via the `mux_launch.sh` script, which handles environment pathing for the muOS runtime.

### 4. Permissions
If the app fails to open, run the following via SSH:

```bash
chmod +x tailscale_gui.py
chmod +x mux_launch.sh
```

---

## 🎮 Controls

| Input | Action |
|-------|--------|
| **D-Pad ↑↓** | Navigate menus |
| **A Button** | Confirm / Select |
| **B Button** | Back / Cancel |
| **Y Button** | Show QR Code (auth) / Refresh peers |
| **L1 / R1** | Page Up / Page Down (file lists) |
| **START** | Preview audio (where applicable) |

---

## 🎨 Themes

Rt:Tailscale ships with three distinct visual themes:

| Theme | Style |
|-------|-------|
| **Tailscale Classic** | Clean, corporate dark — inspired by the official Tailscale brand |
| **SPDW Cyberpunk** | High-contrast neon with HUD corners and scanlines |
| **SPDW Hybrid** | Balanced fusion of both aesthetics |

Themes are switchable in-app and persist across sessions via `config.ini`.

---

## 💡 Troubleshooting

If the application fails to initialize, a crash report is generated automatically:

- **`error_log.txt`** — If the app closes unexpectedly, check this file in the root directory for specific library load errors or path misconfigurations.
- **Dependency Check** — Verify that the `libSDL2` stack (`libSDL2-2.0.so.0`, `libSDL2_ttf-2.0.so.0`, `libSDL2_image-2.0.so.0`) is accessible in your `/lib` path.
- **Logging** — If the GUI remains black, inspect the `mux_launch.sh` output by running it manually via shell.

---

## ⚖️ Credits & Philosophy

**Part of the Chou Henka Project ecosystem.**

> *The network is the computer. The Rintrompo guides the data. Sbrobs.*

Architected and maintained by **Kentani Kenji** *(Sir Pips du Wilson)* — SPDW Factory Lab.

<p align="center">
  <img src="https://img.shields.io/badge/SPDW-Factory_Lab-00FFCC?style=for-the-badge">
  <img src="https://img.shields.io/badge/Chou_Henka-Project-FF00FF?style=for-the-badge">
</p>
