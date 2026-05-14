# Shipping Guide — DB Tunnels

How to build and distribute DB Tunnels to colleagues on macOS.

---

## What you ship

**`DB Tunnels.dmg`** (~53 MB) — drag-to-Applications installer.

Self-contained: no Python, no uv, no Terminal required on the recipient's machine.
Works on macOS 12+ (Intel and Apple Silicon).

---

## Build the DMG

### Prerequisites (one-time)

```bash
brew install create-dmg
uv sync   # installs PyInstaller into .venv
```

### Build

```bash
bash build.sh
```

Produces:
- `dist/DB Tunnels.app` — standalone double-clickable app (75 MB)
- `DB Tunnels.dmg` — distributable installer (53 MB)

### Build subcommands

| Command | What it does |
|---|---|
| `bash build.sh` | Full build: icon → .app → .dmg |
| `bash build.sh app` | .app only |
| `bash build.sh dmg` | Wrap existing `dist/` into .dmg |
| `bash build.sh clean` | Delete `build/` `dist/` and `.dmg` |

### Rebuild after code changes

```bash
bash build.sh clean && bash build.sh
```

---

## How recipients install

1. Receive `DB Tunnels.dmg`
2. Double-click the DMG — Finder window opens
3. Drag **DB Tunnels** to the **Applications** shortcut
4. Eject the DMG
5. Open **DB Tunnels** from Applications or Spotlight

---

## Gatekeeper warning (unsigned app)

macOS will block the app on first launch:
> _"DB Tunnels cannot be opened because the developer cannot be verified"_

This is expected. Two one-time fixes:

### Fix A — Terminal (fastest)

```bash
xattr -cr "/Applications/DB Tunnels.app"
```

Then open normally. Never blocked again.

### Fix B — System Settings

1. Dismiss the warning dialog → click **OK**
2. **System Settings → Privacy & Security → scroll down**
3. Click **Open Anyway** next to DB Tunnels
4. Enter Mac password if prompted

Both fixes are one-time only.

---

## Distributing publicly (no warnings)

Requires Apple Developer Program membership ($99/year).

### One-time setup

```bash
# Store credentials in Keychain
xcrun notarytool store-credentials "AC_PASSWORD" \
  --apple-id "you@example.com" \
  --team-id "YOURTEAMID" \
  --password "xxxx-xxxx-xxxx-xxxx"   # app-specific password from appleid.apple.com
```

### Sign → Notarise → Staple

```bash
# 1. Sign the .app
codesign --deep --force --verify --verbose \
  --sign "Developer ID Application: Your Name (YOURTEAMID)" \
  --options runtime \
  "dist/DB Tunnels.app"

# 2. Rebuild the DMG with signed app inside
bash build.sh dmg

# 3. Sign the DMG
codesign --sign "Developer ID Application: Your Name (YOURTEAMID)" \
  "DB Tunnels.dmg"

# 4. Submit to Apple for notarisation (1–5 min)
xcrun notarytool submit "DB Tunnels.dmg" \
  --keychain-profile "AC_PASSWORD" \
  --wait

# 5. Staple the ticket into the DMG
xcrun stapler staple "DB Tunnels.dmg"

# 6. Verify
spctl --assess --type open --context context:primary-signature \
  "dist/DB Tunnels.app" && echo "✓ Gatekeeper approved"
```

After stapling, anyone can open the DMG on any Mac with zero warnings.

---

## Shipping a new version

1. Make code changes in `src/db_tunnels/`
2. Bump version in `pyproject.toml` and `src/db_tunnels/__init__.py`
3. Add entry to `docs/CHANGELOG.md`
4. Run `bash build.sh clean && bash build.sh`
5. Send the new `DB Tunnels.dmg`

Recipients drag the new app to Applications to replace the old version.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `create-dmg: command not found` | `brew install create-dmg` |
| `uv: command not found` | `brew install uv` |
| PyInstaller import error | Add missing module to `hiddenimports` in `DB Tunnels.spec` |
| App opens but crashes | Run `uv run db-tunnels` to see the error in terminal |
| `DB Tunnels.dmg` already exists error | `bash build.sh clean` then rebuild |
| App shows "damaged" on recipient Mac | `xattr -cr "/Applications/DB Tunnels.app"` |
| autossh not found inside .app | Homebrew PATH is injected at startup — check preflight dialog |
