#!/bin/sh
# ==============================================================================
# PS5 DualSense Kiosk Controller Entrypoint
# ==============================================================================
cd "$(dirname "$0")"

# Ensure LCD backlight is unblanked and bright
[ -f /sys/class/graphics/fb0/blank ] && echo 0 > /sys/class/graphics/fb0/blank
[ -f /sys/class/leds/lcd-backlight/brightness ] && echo 3000 > /sys/class/leds/lcd-backlight/brightness

echo "[*] Launching PS5 DualSense Kiosk Controller..."
exec /usr/bin/python3 main.py
