#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARCH="$(uname -m)"
case "$ARCH" in
  arm64|x86_64) ;;
  *) echo "Unsupported macOS architecture: $ARCH" >&2; exit 1 ;;
esac
WORK="$(mktemp -d "${TMPDIR:-/tmp}/hp-printer-build.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
APP="$WORK/ICTHub Printer.app"
ICONSET="$WORK/AppIcon.iconset"
STAGE="$WORK/dmg"
OUT="$ROOT/dist/ICTHubPrinter-macos-$ARCH.dmg"

cd "$ROOT"
uv sync --locked --python 3.12 --group build
uv run --locked --python 3.12 pyinstaller --noconfirm --clean --onefile \
  --name ICTHubPrinterBackend --paths src \
  --collect-submodules uvicorn --collect-submodules hp_printer \
  --distpath "$WORK/backend" --workpath "$WORK/pyinstaller" \
  --specpath "$WORK" src/hp_printer/macos_entry.py

mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" "$ICONSET" "$STAGE" "$ROOT/dist"
cp "$ROOT/macos/Info.plist" "$APP/Contents/Info.plist"
cp "$WORK/backend/ICTHubPrinterBackend" "$APP/Contents/MacOS/ICTHubPrinterBackend"
swiftc -parse-as-library -swift-version 5 -O -target "$ARCH-apple-macosx13.0" \
  -framework AppKit -framework SwiftUI \
  "$ROOT/macos/ICTHubPrinterMac.swift" -o "$APP/Contents/MacOS/ICTHubPrinterMac"

for entry in '16 16x16' '32 16x16@2x' '32 32x32' '64 32x32@2x' \
             '128 128x128' '256 128x128@2x' '256 256x256' '512 256x256@2x' \
             '512 512x512' '1024 512x512@2x'; do
  size="${entry%% *}"
  name="${entry#* }"
  sips -s format png -z "$size" "$size" \
    "$ROOT/windows/ICTHubPrinter.Setup/Assets/printer.png" --out "$ICONSET/icon_$name.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"
codesign --force --deep --sign - "$APP"

cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cp "$ROOT/macos/README.txt" "$STAGE/README.txt"
rm -f "$OUT"
hdiutil create -volname "ICTHub Printer" -srcfolder "$STAGE" -format UDZO -ov "$OUT" >/dev/null
hdiutil verify "$OUT" >/dev/null
shasum -a 256 "$OUT" > "$ROOT/dist/SHA256SUMS-macos.txt"
printf 'Built %s\n' "$OUT"
