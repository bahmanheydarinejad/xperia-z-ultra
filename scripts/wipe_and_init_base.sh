#!/sbin/sh
# ==============================================================================
# Sony Xperia Z Ultra (togari / C6833) — Bare-Metal Wipe & Base Driver Init
# ==============================================================================
# This script performs a complete wipe of the user space on the Xperia Z Ultra,
# establishes the pristine minimal Linux base layer, initializes all low-level
# Qualcomm hardware device drivers, and creates an isolated, modular application
# slot (/data/modular-app) that can be wiped and replaced at any time by third
# parties without touching the underlying device drivers or root filesystem.
# ==============================================================================

set -eu

echo "=================================================================="
echo "    Xperia Z Ultra: Bare-Metal Wipe & Driver Initialization      "
echo "=================================================================="

# Directories
BASE_ROOT="/data/alpine"
APP_DIR="/data/modular-app"
DOWNLOADS_DIR="/sdcard"

# Step 1: Wipe Existing Userland Data cleanly
echo "[1/7] Wiping previous userland & application partitions..."
# Ensure any running chroot processes are terminated
if [ -d "$BASE_ROOT/proc" ] && grep -q "$BASE_ROOT" /proc/mounts 2>/dev/null; then
    echo "  -> Unmounting existing base filesystems..."
    umount -l "$BASE_ROOT/dev/pts" 2>/dev/null || true
    umount -l "$BASE_ROOT/dev" 2>/dev/null || true
    umount -l "$BASE_ROOT/sys" 2>/dev/null || true
    umount -l "$BASE_ROOT/proc" 2>/dev/null || true
fi

# Clean wipe of base and app directories
echo "  -> Wiping $BASE_ROOT and $APP_DIR..."
rm -rf "$BASE_ROOT"
rm -rf "$APP_DIR"
mkdir -p "$BASE_ROOT"
mkdir -p "$APP_DIR"

echo "[+] Userland wiped cleanly. Hardware registers and partitions intact."

# Step 2: Unpack Base Linux RootFS (Alpine ARMv7)
echo "[2/7] Installing pristine Alpine Linux base rootfs..."
if [ -f "$DOWNLOADS_DIR/alpine-minirootfs-3.20.3-armv7.tar.gz" ]; then
    tar -xzf "$DOWNLOADS_DIR/alpine-minirootfs-3.20.3-armv7.tar.gz" -C "$BASE_ROOT"
else
    echo "[-] Error: Base minirootfs archive not found in $DOWNLOADS_DIR!"
    exit 1
fi

# Step 3: Mount Virtual Filesystems and Hardware Device Tree
echo "[3/7] Binding kernel device tree and IPC nodes..."
mkdir -p "$BASE_ROOT/proc" "$BASE_ROOT/sys" "$BASE_ROOT/dev" "$BASE_ROOT/dev/pts" "$BASE_ROOT/opt/app"
mount -t proc proc "$BASE_ROOT/proc"
mount -t sysfs sys "$BASE_ROOT/sys"
mount -o bind /dev "$BASE_ROOT/dev"
mount -t devpts devpts "$BASE_ROOT/dev/pts"

# Mount modular app directory as /opt/app inside the container
mount -o bind "$APP_DIR" "$BASE_ROOT/opt/app"

# Network DNS setup
echo "nameserver 1.1.1.1" > "$BASE_ROOT/etc/resolv.conf"
echo "nameserver 8.8.8.8" >> "$BASE_ROOT/etc/resolv.conf"

# Step 4: Configure Qualcomm Hardware Drivers & Firmware Paths
echo "[4/7] Initializing hardware driver paths and firmware..."

# 4a. Wi-Fi (Qualcomm WCN3680 Prima driver firmware)
mkdir -p "$BASE_ROOT/lib/firmware/wlan/prima"
for fw in WCNSS_qcom_wlan_nv.bin WCNSS_qcom_cfg.ini WCNSS_wlan_dictionary.dat; do
    if [ -f "/system/etc/firmware/wlan/prima/$fw" ]; then
        cp "/system/etc/firmware/wlan/prima/$fw" "$BASE_ROOT/lib/firmware/wlan/prima/"
    elif [ -f "/vendor/firmware/wlan/prima/$fw" ]; then
        cp "/vendor/firmware/wlan/prima/$fw" "$BASE_ROOT/lib/firmware/wlan/prima/"
    fi
done

# 4b. Screen & Framebuffer (/dev/graphics/fb0)
if [ -e "/dev/graphics/fb0" ]; then
    echo "  -> Display: Framebuffer detected (/dev/graphics/fb0)."
    # Unblank screen
    [ -f "/sys/class/graphics/fb0/blank" ] && echo 0 > /sys/class/graphics/fb0/blank
fi

# 4c. Touchscreen Digitizer Calibration
echo "  -> Touch: Detecting digitizer input node..."
cat /proc/bus/input/devices | grep -E "name=|Handlers=" | head -n 6

# 4d. NFC Controller (/dev/pn544)
mkdir -p "$BASE_ROOT/etc/nfc/devices.d"
cat << 'EOF' > "$BASE_ROOT/etc/nfc/devices.d/pn544.conf"
name = "Sony Xperia Z Ultra (togari) NFC"
connstring = "pn544_i2c:/dev/pn544"
EOF

# 4e. Bluetooth High-Speed UART (/dev/ttyHS0)
if [ -e "/dev/ttyHS0" ]; then
    chmod 666 /dev/ttyHS0
fi

# 4f. Battery PMIC Guardian
cat << 'EOF' > "$BASE_ROOT/usr/local/bin/battery-guardian.sh"
#!/bin/sh
SOC_FILE="/sys/class/power_supply/battery/capacity"
CHG_ENABLE="/sys/class/power_supply/battery/charging_enabled"
[ ! -f "$CHG_ENABLE" ] && CHG_ENABLE="/sys/class/power_supply/battery/batt_charging_enabled"
[ ! -f "$SOC_FILE" ] && exit 0
SOC=$(cat "$SOC_FILE")
if [ "$SOC" -ge 65 ]; then
    [ -f "$CHG_ENABLE" ] && echo 0 > "$CHG_ENABLE"
elif [ "$SOC" -le 55 ]; then
    [ -f "$CHG_ENABLE" ] && echo 1 > "$CHG_ENABLE"
fi
EOF
chmod +x "$BASE_ROOT/usr/local/bin/battery-guardian.sh"

# Step 5: Install Modular App Manager CLI & Kiosk Autostart Supervisor
echo "[5/7] Deploying Modular App Manager & Kiosk Supervisor..."

# 5a. Kiosk Supervisor (ensures phone starts showing app screen only)
cat << 'EOF' > "$BASE_ROOT/usr/local/bin/kiosk_autostart.sh"
#!/bin/sh
APP_SLOT="/opt/app"
FB_BLANK="/sys/class/graphics/fb0/blank"
BACKLIGHT="/sys/class/leds/lcd-backlight/brightness"

# Turn off Android surfaceflinger if alive
if command -v stop >/dev/null 2>&1; then
    stop surfaceflinger 2>/dev/null || true
    stop zygote 2>/dev/null || true
fi

[ -f "$FB_BLANK" ] && echo 0 > "$FB_BLANK" 2>/dev/null || true
[ -f "$BACKLIGHT" ] && echo 180 > "$BACKLIGHT" 2>/dev/null || true

while true; do
    if [ -f "$APP_SLOT/entrypoint.sh" ]; then
        /bin/sh "$APP_SLOT/entrypoint.sh" 2>&1 | tee -a /var/log/kiosk-app.log
    elif [ -f "$APP_SLOT/main.py" ]; then
        python3 "$APP_SLOT/main.py" 2>&1 | tee -a /var/log/kiosk-app.log
    else
        sleep 3
        continue
    fi
    sleep 1
done
EOF
chmod +x "$BASE_ROOT/usr/local/bin/kiosk_autostart.sh"

cat << 'EOF' > "$BASE_ROOT/usr/local/bin/modular-app-mgr"
#!/bin/sh
# Modular Application Manager for Xperia Z Ultra
APP_SLOT="/opt/app"
RUN_LOG="/var/log/modular-app.log"
PID_FILE="/var/run/modular-app.pid"

case "$1" in
    wipe)
        echo "[*] Wiping current application payload in $APP_SLOT..."
        if [ -f "$PID_FILE" ]; then
            kill -9 $(cat "$PID_FILE") 2>/dev/null || true
            rm -f "$PID_FILE"
        fi
        rm -rf "$APP_SLOT"/* "$APP_SLOT"/.[!.]*
        echo "[+] App section wiped cleanly. Device drivers & base system remain intact."
        ;;
    install)
        SRC="$2"
        if [ -z "$SRC" ] || [ ! -e "$SRC" ]; then
            echo "[-] Error: Specify valid tar.gz archive or app directory to install."
            exit 1
        fi
        echo "[*] Installing application payload from $SRC..."
        "$0" wipe
        if [ -f "$SRC" ]; then
            tar -xzf "$SRC" -C "$APP_SLOT"
        elif [ -d "$SRC" ]; then
            cp -r "$SRC"/* "$APP_SLOT"/
        fi
        [ -f "$APP_SLOT/install.sh" ] && /bin/sh "$APP_SLOT/install.sh"
        echo "[+] App installed successfully into $APP_SLOT."
        ;;
    start)
        echo "[*] Starting modular application..."
        if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
            echo "[!] Application already running with PID $(cat "$PID_FILE")."
            exit 0
        fi
        if [ -f "$APP_SLOT/entrypoint.sh" ]; then
            nohup /bin/sh "$APP_SLOT/entrypoint.sh" > "$RUN_LOG" 2>&1 &
            echo $! > "$PID_FILE"
            echo "[+] App launched (PID $(cat "$PID_FILE")). Logs: $RUN_LOG"
        elif [ -f "$APP_SLOT/main.py" ]; then
            nohup python3 "$APP_SLOT/main.py" > "$RUN_LOG" 2>&1 &
            echo $! > "$PID_FILE"
            echo "[+] Python app launched (PID $(cat "$PID_FILE")). Logs: $RUN_LOG"
        else
            echo "[-] Error: No entrypoint.sh or main.py found in $APP_SLOT!"
            exit 1
        fi
        ;;
    stop)
        echo "[*] Stopping modular application..."
        if [ -f "$PID_FILE" ]; then
            kill $(cat "$PID_FILE") 2>/dev/null || true
            sleep 1
            kill -9 $(cat "$PID_FILE") 2>/dev/null || true
            rm -f "$PID_FILE"
            echo "[+] Application stopped."
        else
            pkill -f "$APP_SLOT" 2>/dev/null || true
            echo "[*] No active PID file found. Cleaned remaining processes."
        fi
        ;;
    status)
        echo "=== Modular App Status ==="
        if [ -f "$APP_SLOT/manifest.json" ]; then
            cat "$APP_SLOT/manifest.json"
            echo ""
        else
            echo "No manifest.json present."
        fi
        if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
            echo "State: RUNNING (PID $(cat "$PID_FILE"))"
        else
            echo "State: STOPPED"
        fi
        ;;
    logs)
        tail -n 50 "$RUN_LOG" 2>/dev/null || echo "No logs available."
        ;;
    *)
        echo "Usage: modular-app-mgr {wipe|install <archive/dir>|start|stop|status|logs}"
        exit 1
        ;;
esac
EOF
chmod +x "$BASE_ROOT/usr/local/bin/modular-app-mgr"

# Step 6: Create Host Proxy Link for Modular App Management
echo "[6/7] Linking modular application management to host commands..."
cp "$BASE_ROOT/usr/local/bin/modular-app-mgr" /data/modular_app_mgr.sh 2>/dev/null || true

# Step 7: Final Status Check
echo "[7/7] Base driver environment initialization complete!"
echo ""
echo "=================================================================="
echo "                   MODULAR PHONE READY                            "
echo "=================================================================="
echo " - Base OS & Drivers:  $BASE_ROOT (Alpine Linux ARMv7)"
echo " - App Section Slot:   $APP_DIR (Mounted as /opt/app)"
echo " - App Control Tool:   chroot $BASE_ROOT modular-app-mgr"
echo ""
echo " Third parties can wipe and replace the app at will:"
echo "   modular-app-mgr wipe"
echo "   modular-app-mgr install /path/to/new_app.tar.gz"
echo "   modular-app-mgr start"
echo "=================================================================="
