🕸️ Rt:Tailscale

The definitive mesh-VPN interface for muOS. Engineered for performance, built for the handheld.

📖 Overview

Rt:Tailscale is a lightweight, high-performance GUI application designed specifically for Anbernic devices running muOS (MustardOS). This tool eliminates the friction of CLI-based Tailscale management, providing a native, controller-driven interface to control your tailnet, monitor connections, and manage exit nodes directly from your console.

Built to run seamlessly within the muOS ecosystem, it leverages the mux_launch.sh wrapper for optimized process execution.

👁️ Visuals

Boot Animation

Main Menu





📂 Project Structure

The project follows a clean, modular structure optimized for muOS application management:

Rt:Tailscale/
├── glyph/              # Graphical assets & icons
│   └── icon.png        # Application launcher icon
├── config.ini          # User-defined configurations
├── font.ttf            # UI rendering font
├── mux_launch.sh       # Entry-point script for muOS
├── tailscale_gui.py    # Core application logic (Python/SDL2)
├── tailscale.png       # Application primary logo
└── README.md           # Documentation


🚀 Key Features

🎮 Native muOS Experience: Seamless integration with the muOS menu system via mux_launch.sh.

📡 Tailnet Control: Toggle the Tailscale daemon and manage SSH access with a single button press.

🌍 Exit Node Management: Dynamically list and select your preferred exit nodes.

⚡ Zero-Dep Tech Stack: Built with pure Python using ctypes to interface directly with SDL2.

🛠️ Diagnostic Engine: Integrated netcheck tools to analyze latency, NAT types, and UDP connectivity.

📥 Installation

Deploy: Copy the entire Rt:Tailscale directory to your applications path (e.g., /mnt/mmc/MUOS/application/).

Verify Assets: Ensure all files from the structure above are present, especially font.ttf and the glyph/ icon.

Execution: The app is designed to be launched via the mux_launch.sh script, which handles the environment pathing for the muOS runtime.

Permissions: Run the following via SSH if the app fails to open:

chmod +x tailscale_gui.py
chmod +x mux_launch.sh


💡 Troubleshooting

If the application fails to initialize, a crash report is generated automatically:

error_log.txt: If the app closes unexpectedly, check this file in the root directory for specific library load errors or path misconfigurations.

Dependency Check: Verify that the libSDL2 stack is accessible in your /lib path.

Logging: If the GUI remains black, inspect the mux_launch.sh output by running it manually via shell.

⚖️ Credits & Philosophy

Part of the Chou Henka Project ecosystem. Architected and maintained by Kentani Kenji (Sir Pips du Wilson).

The network is the computer. The Rintrompo guides the data.

Sbrobs.
