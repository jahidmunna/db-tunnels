# Contributing to DB Tunnels

---

## Development setup

```bash
git clone https://github.com/jahidmunna/db-tunnels.git
cd db-tunnels

# Install all deps including dev tools (creates .venv automatically)
uv sync

# Run the app
uv run db-tunnels

# Run tests
uv run pytest -v
```

Requirements: macOS 12+, Python 3.12+, uv, autossh (`brew install autossh`)

---

## Project structure

```
src/db_tunnels/
├── __init__.py           # version, public API exports
├── main.py               # PyQt6 GUI — windows, panels, dialogs
├── tunnel_model.py       # Tunnel + ForwardRule dataclasses, JSON persistence
├── tunnel_manager.py     # autossh process lifecycle, connection diagnosis
├── ssh_key_manager.py    # SSH key discovery, generation, ssh-copy-id
└── preflight.py          # startup dependency + connectivity checks

tests/                    # pytest suite — mirrors src/ module structure
docs/                     # CHANGELOG, CONTRIBUTING (this file), SHIPPING
build.sh                  # builds .app and .dmg
```

---

## Making changes

1. Fork the repo and create a branch: `git checkout -b feature/your-feature`
2. Make changes inside `src/db_tunnels/`
3. Add or update tests in `tests/`
4. Run `uv run pytest` — all must pass
5. Open a pull request against `main`

---

## Where to make changes

| What you want to change | File |
|---|---|
| Data model / tunnel config schema | `src/db_tunnels/tunnel_model.py` — update `to_dict` / `from_dict` too |
| autossh process / reconnect / diagnosis | `src/db_tunnels/tunnel_manager.py` |
| UI — panels, dialogs, buttons | `src/db_tunnels/main.py` |
| SSH key generation / copy-to-server | `src/db_tunnels/ssh_key_manager.py` |
| Startup checks (add a new tool check) | `src/db_tunnels/preflight.py` — add `check_*()` and call in `run_all_checks()` |

---

## Tests

```bash
uv run pytest                               # all 77 tests
uv run pytest tests/test_tunnel_model.py -v # single file
uv run pytest -k "ipv6"                     # filter by name
```

No real subprocesses, network calls, or filesystem writes in tests — autossh, ssh, socket, and file I/O all mocked.

When adding new code, add matching tests. Keep mocks scoped to the test file, not conftest.

---

## Building a release

```bash
bash build.sh clean   # wipe previous build
bash build.sh         # produces dist/DB Tunnels.app + DB Tunnels.dmg
```

Never commit `build/`, `dist/`, `*.dmg`, `*.app`, `*.spec`, or `*.icns` — all gitignored.

---

## Reporting bugs

Open a GitHub issue at https://github.com/jahidmunna/db-tunnels/issues with:

- macOS version and chip (Intel / Apple Silicon)
- Steps to reproduce
- What you expected vs what happened
- Log tab contents if tunnel-related

---

## Code style

- No `type: ignore` — fix the types
- No bare `except:` — catch specific exceptions
- Comments only for non-obvious WHY, not what
- Prefer editing existing files over creating new ones
- No half-finished implementations or TODO stubs in PRs
