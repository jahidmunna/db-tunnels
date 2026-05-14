# DB Tunnels

[![CI](https://github.com/jahidmunna/db-tunnels/actions/workflows/ci.yml/badge.svg)](https://github.com/jahidmunna/db-tunnels/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![macOS](https://img.shields.io/badge/platform-macOS%2012%2B-lightgrey.svg)]()

macOS GUI for managing multiple `autossh` port-forwarding tunnels from a single interface. Start, stop, monitor, and edit tunnels without touching the terminal.

![DB Tunnels](docs/screenshots/DB%20Tunnels%20Thumbnail.png)

---

## Quick Start

```bash
# 1. Install Homebrew (skip if already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Install uv + autossh
brew install uv autossh

# 3. Clone
git clone https://github.com/jahidmunna/db-tunnels.git
cd db-tunnels

# 4. Install Python dependencies
uv sync

# 5. Launch
uv run db-tunnels
```

On first launch a preflight dialog checks all dependencies and offers one-click auto-install for anything missing.

---

## Features

- **Startup preflight** — checks `autossh`, `ssh`, `ssh-keygen`, `ssh-copy-id`, `sshpass`; tests jump-host port reachability; auto-installs via Homebrew
- **One-click start/stop** per tunnel, or bulk start/stop all
- **Live log stream** per tunnel (autossh stdout/stderr)
- **Status indicators** — Stopped / Starting / Connected / Error
- **Connection diagnosis** — on error, Info tab shows exact problem + copy-paste fix commands
- **Add / Edit / Delete** tunnels with a form UI — no config file editing
- **Multiple port forwards per tunnel** — unlimited `-L` rules per connection
- **IPv6 support** — brackets auto-applied in SSH `-L` syntax
- **SSH Key Manager** — generate keys, copy public key to server
- **Auto-reconnect** — `autossh` handles disconnects automatically
- **Persistent config** — `~/Library/Application Support/DBTunnels/tunnels.json`

---

## Requirements

| Requirement | Notes |
|---|---|
| macOS 12+ | Intel and Apple Silicon |
| Python 3.12+ | via Homebrew or pyenv |
| [uv](https://docs.astral.sh/uv/) | `brew install uv` |
| autossh | `brew install autossh` — required for tunnels |
| OpenSSH | bundled with macOS |
| sshpass | `brew install sshpass` — **optional**, only for "Copy to Server" with password auth |

---

## Installation (Development)

```bash
# Clone
git clone https://github.com/jahidmunna/db-tunnels.git
cd db-tunnels

# Install deps (creates .venv automatically)
uv sync

# Run
uv run db-tunnels
```

---

## Running Tests

```bash
uv run pytest          # all 77 tests
uv run pytest -v       # verbose
uv run pytest -k ipv6  # filter by name
```

Tests cover: data model, SSH flag building (IPv6), process lifecycle, log routing, persistence, preflight checks, key discovery/generation/copy. No real subprocesses or network calls — everything mocked.

---

## Project Structure

```
db-tunnels/
├── src/
│   └── db_tunnels/
│       ├── __init__.py           # version, public API exports
│       ├── main.py               # PyQt6 GUI — windows, panels, dialogs
│       ├── tunnel_model.py       # Tunnel + ForwardRule dataclasses, JSON persistence
│       ├── tunnel_manager.py     # autossh process lifecycle, connection diagnosis
│       ├── ssh_key_manager.py    # SSH key discovery, generation, ssh-copy-id
│       └── preflight.py          # startup dependency + connectivity checks
├── tests/
│   ├── test_tunnel_model.py      # model, serialisation, IPv6, persistence
│   ├── test_tunnel_manager.py    # process start/stop, callbacks, error paths
│   ├── test_ssh_key_manager.py   # key discovery, keygen, copy-to-server
│   └── test_preflight.py         # tool checks, port checks, auto-fix
├── docs/
│   ├── CONTRIBUTING.md           # dev setup, change guide, code style
│   ├── CHANGELOG.md              # version history
│   └── SHIPPING.md               # build, distribute, sign, notarise
├── .github/
│   └── workflows/
│       ├── ci.yml                # runs tests on every push + PR
│       └── release.yml           # builds .dmg and publishes GitHub release on tag
├── assets/
│   └── icon.png                  # app icon (1024x1024) — converted to .icns at build time
├── build.sh                      # bash build.sh → .app + .dmg
├── pyproject.toml                # project metadata, deps, build config
├── uv.lock                       # locked dependency tree
├── LICENSE                       # MIT
└── README.md
```

---

## Building the macOS App

One command builds a standalone `.app` and drag-to-install `.dmg`:

```bash
# Prerequisites (one-time)
brew install create-dmg
uv sync

# Build
bash build.sh          # → dist/DB Tunnels.app + DB Tunnels.dmg
bash build.sh clean    # wipe build artefacts
bash build.sh app      # .app only
bash build.sh dmg      # .dmg from existing dist/
```

See [`docs/SHIPPING.md`](docs/SHIPPING.md) for full distribution guide including Gatekeeper bypass and Apple notarisation.

---

## Tunnel Configuration

Config stored at `~/Library/Application Support/DBTunnels/tunnels.json`.

| Field | Description |
|---|---|
| `name` | Display name |
| `jump_host` | SSH jump host (`user@host`) |
| `jump_port` | SSH port on jump host |
| `forwards` | List of `{local_port, remote_host, remote_port}` rules |
| `keepalive_interval` | Seconds between SSH keepalive probes (default: 30) |
| `keepalive_count_max` | Missed probes before reconnect (default: 3) |
| `enabled` | Whether "Start All" includes this tunnel |
| `notes` | Free-text notes shown in the Info panel |

Three example tunnels are pre-loaded on first launch — replace with your own.

---

## How Auto-Reconnect Works

Each tunnel runs:

```bash
autossh -M 0 \
  -o 'ServerAliveInterval 30' \
  -o 'ServerAliveCountMax 3' \
  -N -L <local>:[<remote_host>]:<remote_port> \
  <jump_host> -p <jump_port>
```

`-M 0` uses SSH keepalives instead of autossh's own monitoring port. 3 missed keepalives triggers a reconnect. IPv6 hosts are auto-wrapped in `[brackets]`.

---

## SSH Key Manager

Access via the **🔑** button in the sidebar.

| Tab | Function |
|---|---|
| My Keys | Lists all `~/.ssh` keypairs — fingerprint, type, copy pubkey |
| Generate Key | Create ed25519 / rsa / ecdsa keys with optional passphrase |
| Copy to Server | Run `ssh-copy-id` to a remote host; password mode requires `sshpass` |

---

## Gatekeeper (unsigned app warning)

macOS blocks unsigned apps on first launch. Two fixes — both one-time only:

**Fix A (Terminal):**
```bash
xattr -cr "/Applications/DB Tunnels.app"
```

**Fix B (UI):** System Settings → Privacy & Security → scroll down → **Open Anyway**

For public distribution without warnings, see the codesign + notarisation steps in [`docs/SHIPPING.md`](docs/SHIPPING.md).

---

## Contributing

See [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md).

## Changelog

See [`docs/CHANGELOG.md`](docs/CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE).
