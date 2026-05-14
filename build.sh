#!/bin/bash
# =============================================================================
# build.sh — Build DB Tunnels.app + DB Tunnels.dmg
#
# USAGE:
#   bash build.sh            # full build: .app + .dmg
#   bash build.sh app        # build .app only
#   bash build.sh dmg        # wrap existing dist/ into .dmg only
#   bash build.sh clean      # delete build/ dist/ and .dmg artefacts
#
# PREREQUISITES (one-time):
#   brew install create-dmg
#   uv add --group dev pyinstaller   (already in pyproject.toml)
# =============================================================================
set -euo pipefail

SPEC="DB Tunnels.spec"
APP="dist/DB Tunnels.app"
DMG="DB Tunnels.dmg"
ICON="AppIcon.icns"
ICON_PNG="assets/icon.png"

log()  { echo "▶ $*"; }
die()  { echo "✕ ERROR: $*" >&2; exit 1; }
need() { command -v "$1" &>/dev/null || die "'$1' not found. $2"; }

# ── Icon: PNG → .icns ─────────────────────────────────────────────────────────
task_icon() {
    [[ -f "$ICON" ]] && { log "AppIcon.icns exists — skipping."; return; }
    [[ -f "$ICON_PNG" ]] || die "icon.png not found in repo root."
    log "Converting icon.png → AppIcon.icns..."
    rm -rf icon.iconset && mkdir icon.iconset
    sips -z 16   16   "$ICON_PNG" --out icon.iconset/icon_16x16.png       2>/dev/null
    sips -z 32   32   "$ICON_PNG" --out icon.iconset/icon_16x16@2x.png    2>/dev/null
    sips -z 32   32   "$ICON_PNG" --out icon.iconset/icon_32x32.png       2>/dev/null
    sips -z 64   64   "$ICON_PNG" --out icon.iconset/icon_32x32@2x.png    2>/dev/null
    sips -z 128  128  "$ICON_PNG" --out icon.iconset/icon_128x128.png     2>/dev/null
    sips -z 256  256  "$ICON_PNG" --out icon.iconset/icon_128x128@2x.png  2>/dev/null
    sips -z 256  256  "$ICON_PNG" --out icon.iconset/icon_256x256.png     2>/dev/null
    sips -z 512  512  "$ICON_PNG" --out icon.iconset/icon_256x256@2x.png  2>/dev/null
    sips -z 512  512  "$ICON_PNG" --out icon.iconset/icon_512x512.png     2>/dev/null
    sips -z 1024 1024 "$ICON_PNG" --out icon.iconset/icon_512x512@2x.png  2>/dev/null
    iconutil -c icns icon.iconset -o "$ICON"
    rm -rf icon.iconset
    log "AppIcon.icns created."
}

# ── Spec: generate if missing, inject hidden imports ──────────────────────────
task_spec() {
    [[ -f "$SPEC" ]] && { log "Spec exists — skipping pyi-makespec."; return; }
    log "Generating PyInstaller spec..."
    uv run pyi-makespec \
        --windowed \
        --name "DB Tunnels" \
        --icon "$ICON" \
        --osx-bundle-identifier "com.dbtunnels.app" \
        --paths src \
        launcher.py
    uv run python3 - <<'PY'
import pathlib
spec = pathlib.Path("DB Tunnels.spec").read_text()
spec = spec.replace(
    "hiddenimports=[],",
    "hiddenimports=['db_tunnels.tunnel_model','db_tunnels.tunnel_manager','db_tunnels.ssh_key_manager','db_tunnels.preflight'],"
)
pathlib.Path("DB Tunnels.spec").write_text(spec)
PY
    log "Spec ready."
}

# ── App: build standalone .app ────────────────────────────────────────────────
task_app() {
    need uv "Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
    task_icon
    task_spec
    log "Syncing Python dependencies..."
    uv sync
    log "Building DB Tunnels.app (this takes ~30s)..."
    uv run pyinstaller "$SPEC" --noconfirm
    [[ -d "$APP" ]] || die ".app not found — check PyInstaller output above."
    log "Built: $APP  ($(du -sh "$APP" | cut -f1))"
}

# ── DMG: wrap dist/ into distributable installer ──────────────────────────────
task_dmg() {
    need create-dmg "Install: brew install create-dmg"
    [[ -d "$APP" ]] || die "'$APP' not found. Run: bash build.sh app"
    task_icon
    log "Building $DMG..."
    rm -f "$DMG"
    create-dmg \
        --volname "DB Tunnels" \
        --volicon "$ICON" \
        --window-pos 200 120 \
        --window-size 660 400 \
        --icon-size 120 \
        --icon "DB Tunnels.app" 180 185 \
        --hide-extension "DB Tunnels.app" \
        --app-drop-link 480 185 \
        "$DMG" \
        "dist/"
    log "Built: $DMG  ($(du -sh "$DMG" | cut -f1))"
    log ""
    log "Share '$DMG' with colleagues."
    log "Install: double-click DMG → drag DB Tunnels to Applications."
    log "First launch: right-click the app → Open  (one-time Gatekeeper bypass)."
}

# ── Clean ─────────────────────────────────────────────────────────────────────
task_clean() {
    log "Removing build/ dist/ and $DMG..."
    rm -rf build/ dist/ "$DMG"
    log "Clean."
}

# ── Dispatch ──────────────────────────────────────────────────────────────────
case "${1:-all}" in
    all)   task_app; task_dmg ;;
    app)   task_app ;;
    dmg)   task_dmg ;;
    clean) task_clean ;;
    *)     echo "Usage: bash build.sh [all|app|dmg|clean]"; exit 1 ;;
esac