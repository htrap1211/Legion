# Legion - P2P File Sharing System

**Legion** is a robust, decentralized peer-to-peer file sharing application built with Python. It features dynamic leader election, automatic peer discovery, and a sleek terminal-based user interface (TUI).

## 🚀 Features

- **Decentralized Architecture**: No central server required. Peers communicate directly.
- **Automatic Leader Election**: Uses a modified Bully Algorithm to elect a coordinator for the network.
- **Fault Tolerance**: Automatically detects leader failures and triggers re-election (Self-Healing).
- **Real-time Discovery**: Peers automatically find each other on the local network using UDP broadcasting.
- **File Integrity**: Verifies downloaded files using SHA-256 checksums.
- **Terminal UI**: A hacker-style TUI built with `curses` for easy interaction.

## 🛠️ Installation

### Prerequisites
- Python 3.6+
- Network access (Local LAN recommended)

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/htrap1211/Legion.git
   cd Legion
   ```

2. Install dependencies (Windows only):
   *Note: Linux/macOS users do not need to install anything as `curses` is built-in.*
   ```bash
   pip install windows-curses
   ```

## 💻 Usage

Start the application:
```bash
python main.py
```

### Commands

| Command | Description |
|---------|-------------|
| `list` | List files in your local shared directory. |
| `publish` | Announce your shared files to the network. |
| `share <path>` | Add a specific file to your shared folder and publish it. |
| `search` | List all files available in the network (Global Catalog). |
| `download <filename>` | Download a file from the network. |
| `cd <path>` | Change current working directory. |
| `help` | Show available commands. |
| `quit` | Exit the application. |

## 🏗️ Architecture

- **Networking**: Uses UDP for discovery/heartbeats and TCP for reliable file transfer.
- **Concurrency**: Multi-threaded design to handle UI, networking, and file I/O simultaneously.
- **Protocol**: Custom JSON-based protocol for peer communication.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
