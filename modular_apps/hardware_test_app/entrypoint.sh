#!/bin/sh
# Entrypoint for Togari All-Module Diagnostic Test Suite
# Boot directly into fullscreen Kiosk Dashboard on /dev/graphics/fb0
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$APP_DIR:$PYTHONPATH"

# Unblank display hardware & set comfortable backlight
if [ -f "/sys/class/graphics/fb0/blank" ]; then
    echo 0 > /sys/class/graphics/fb0/blank 2>/dev/null || true
fi
if [ -f "/sys/class/leds/lcd-backlight/brightness" ]; then
    echo 180 > /sys/class/leds/lcd-backlight/brightness 2>/dev/null || true
fi

if [ "$1" = "--cli" ] || [ "$1" = "cli" ]; then
    echo "[*] Running CLI Acceptance Audit..."
    exec python3 "$APP_DIR/app_hardware_diagnostic.py"
elif [ "$1" = "--json" ] || [ "$1" = "json" ]; then
    exec python3 "$APP_DIR/app_hardware_diagnostic.py" --json
else
    echo "[*] Launching Fullscreen Direct-Framebuffer Kiosk Dashboard..."
    exec python3 "$APP_DIR/app_hardware_diagnostic.py" --kiosk
fi
