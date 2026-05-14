# Changelog

All notable changes to DB Tunnels are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.1.0] — 2026-05-13

Initial open source release.

### Added

**Core**
- macOS GUI built with PyQt6 — dark mode, sidebar navigation, detail panel
- `src/db_tunnels/` package layout with proper relative imports
- `uv` for dependency management and virtual environment

**Tunnel management**
- Add, edit, delete tunnels via form UI — no manual config editing
- Multiple port-forward rules per tunnel (unlimited `-L` flags)
- IPv6 host support — brackets auto-applied in SSH `-L` syntax
- `autossh` integration — `ServerAliveInterval` keepalives, auto-reconnects on drop
- Bulk start / stop all enabled tunnels from sidebar

**Monitoring**
- Live log streaming per tunnel (autossh stdout/stderr)
- Status indicators: Stopped / Starting / Connected / Error
- Connection diagnosis on error — Info tab shows exact problem + copy-paste fix:
  - Port closed / timed out → `nc -zv` test command
  - SSH auth failure → `ssh-add` command + SSH Key Manager pointer
  - Host key mismatch → `ssh-keygen -R` command
  - autossh missing → `brew install autossh`

**SSH Key Manager** (🔑 sidebar button)
- My Keys tab — lists all `~/.ssh` keypairs with fingerprint, type pill, copy pubkey
- Generate Key tab — create ed25519 / rsa / ecdsa keys with optional passphrase
- Copy to Server tab — runs `ssh-copy-id`; password mode via `sshpass`

**Startup preflight**
- Checks: autossh, ssh, ssh-keygen, ssh-copy-id, sshpass, jump-host port reachability
- Auto-installs missing tools via Homebrew with live output streaming
- Re-check button re-runs all checks after fixing
- Homebrew PATH injected at startup so bundled `.app` finds tools correctly

**Build / Distribution**
- `bash build.sh` — one command builds `dist/DB Tunnels.app` + `DB Tunnels.dmg`
- Subcommands: `all` / `app` / `dmg` / `clean`
- Static `assets/icon.png` committed to repo; converted to `.icns` via `sips` + `iconutil` at build time
- `launcher.py` entrypoint wraps package import for PyInstaller compatibility
- GitHub Actions release workflow — builds `.dmg` and attaches to GitHub Release on tag push

**Config**
- Persistent config at `~/Library/Application Support/DBTunnels/tunnels.json`
- Three example tunnels pre-loaded on first run (ClickHouse, IPv6, Postgres)

**Tests**
- 77 unit tests across 4 modules
- No real subprocesses, network calls, or filesystem side-effects — everything mocked
- CI via GitHub Actions (`macos-latest`)
