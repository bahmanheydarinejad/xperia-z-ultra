#!/bin/sh
# ==============================================================================
# Xperia Z Ultra: Boot-to-App Kiosk Supervisor (Shows App Screen ONLY)
# ==============================================================================
# This watchdog ensures the phone boots directly into the fullscreen modular
# application on /dev/graphics/fb0. No Android UI, no lock screen, no desktop.
# If the app exits or crashes, it automatically respawns within 1 second.
# ==============================================================================

APP_SLOT="/opt/app"
FB_BLANK="/sys/class/graphics/fb0/blank"
BACKLIGHT="/sys/class/leds/lcd-backlight/brightness"

echo "[*] Kiosk Supervisor initializing..."

# 1. Kill Android SurfaceFlinger & Zygote if lingering, so direct FB0 is unimpeded
if command -v stop >/dev/null 2>&1; then
    stop surfaceflinger 2>/dev/null || true
    stop zygote 2>/dev/null || true
fi

# 2. Hardware Display Bring-up
[ -f "$FB_BLANK" ] && echo 0 > "$FB_BLANK" 2>/dev/null || true
[ -f "$BACKLIGHT" ] && echo 180 > "$BACKLIGHT" 2>/dev/null || true

# 3. Kiosk Respawn Watchdog Loop
echo "[+] Starting Kiosk App Watchdog on /dev/graphics/fb0..."

while true; do
    if [ -f "$APP_SLOT/entrypoint.sh" ]; then
        echo "[*] Launching $APP_SLOT/entrypoint.sh..."
        /bin/sh "$APP_SLOT/entrypoint.sh" 2>&1 | tee -a /var/log/kiosk-app.log
    elif [ -f "$APP_SLOT/main.py" ]; then
        echo "[*] Launching $APP_SLOT/main.py..."
        python3 "$APP_SLOT/main.py" 2>&1 | tee -a /var/log/kiosk-app.log
    else
        echo "[!] No application found in $APP_SLOT. Waiting for deployment..."
        sleep 3
        continue
    fi

    EXIT_CODE=$?
    echo "[!] Kiosk app exited with code $EXIT_CODE. Respawning in 1 second..."
    sleep 1
done
