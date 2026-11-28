#!/usr/bin/env bash
# Creates ~/Applications/Peak.app: double-click to open Peak. Run once from the repo on the Mac that will use it.
# It only points at this checkout; nothing is copied, signed or uploaded.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
uv_bin=$(command -v uv || true)
[[ -n "$uv_bin" ]] || { echo "Install uv first: brew install uv" >&2; exit 1; }
[[ -f "$repo/apps/web/out/index.html" ]] || { echo "Build the screens first: (cd apps/web && npm ci && npm run build)" >&2; exit 1; }
app="$HOME/Applications/Peak.app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
cat > "$app/Contents/MacOS/peak" <<SH
#!/bin/bash
# Apps opened from Finder don't get the shell's PATH, so the paths are fixed at install time.
cd "$repo/services/backend"
exec "$uv_bin" run --extra mac python -m peak.local >> "\$HOME/Library/Logs/Peak.log" 2>&1
SH
chmod +x "$app/Contents/MacOS/peak"
cat > "$app/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Peak</string>
  <key>CFBundleDisplayName</key><string>Peak</string>
  <key>CFBundleIdentifier</key><string>work.mturner.peak</string>
  <key>CFBundleExecutable</key><string>peak</string>
  <key>CFBundleIconFile</key><string>Peak</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
# Icon from the app's own 512 px icon (sips and iconutil ship with macOS).
icon_src="$repo/apps/web/public/icons/icon-512.png"
if command -v iconutil >/dev/null && [[ -f "$icon_src" ]]; then
  set_dir=$(mktemp -d)/Peak.iconset; mkdir -p "$set_dir"
  for s in 16 32 128 256 512; do
    sips -z $s $s "$icon_src" --out "$set_dir/icon_${s}x${s}.png" >/dev/null
    sips -z $((s*2)) $((s*2)) "$icon_src" --out "$set_dir/icon_${s}x${s}@2x.png" >/dev/null
  done
  iconutil -c icns "$set_dir" -o "$app/Contents/Resources/Peak.icns"
fi
mkdir -p "$HOME/Library/Logs"
echo "Installed $app. Open it from Finder or Spotlight, and drag it to the Dock to keep it there."
