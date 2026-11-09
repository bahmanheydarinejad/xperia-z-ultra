# Togari All-Module Hardware Diagnostic & Acceptance Test Suite

This application is the official reference implementation for the **Modular Application Architecture** on the Sony Xperia Z Ultra (togari / MSM8974) running pure Alpine Linux.

## Key Features
1. **Zero Android Overhead**: Runs purely on downstream Linux kernel and Alpine ARMv7 userland.
2. **Boot-to-App Screen Only**: Autostarts directly into fullscreen kiosk mode on `/dev/graphics/fb0` (1080x1920 32-bit ARGB).
3. **Tests All 8 Hardware Modules**:
   - Screen / Framebuffer (`/dev/graphics/fb0`)
   - Touchscreen Digitizer (`/dev/input/event*`, Clearpad / Maxim MAX11871)
   - 6-Axis Gyroscope & Accelerometer (InvenSense MPU6500 IIO stream)
   - Wi-Fi WLAN (Qualcomm WCN3680 Prima driver / `wlan0`)
   - Bluetooth LE (Qualcomm WCN3680 High-Speed UART `/dev/ttyHS0` -> `hci0`)
   - Cellular Modem (Qualcomm MDM9225 baseband via `/dev/smdcntl0` & `rmnet0`)
   - NFC Controller (NXP PN544 I2C `/dev/pn544` & `libnfc`)
   - Battery & PMIC Guardian (`/sys/class/power_supply/battery/`)
4. **Completely Isolated & Wipable**:
   - Resides strictly in `/opt/app` (`/data/modular-app`).
   - Can be wiped, replaced, or hot-swapped by third-party developers at any time using:
     ```sh
     modular-app-mgr wipe
     modular-app-mgr install /path/to/any_new_app.tar.gz
     modular-app-mgr start
     ```

## Manifest Specification (`manifest.json`)
Every modular app package contains a `manifest.json` defining metadata, required hardware nodes, and capabilities:
```json
{
  "name": "togari-all-module-diagnostic",
  "version": "1.0.0",
  "runtime": "python3",
  "entrypoint": "entrypoint.sh",
  "isolated_slot": "/opt/app"
}
```

## Running Modes
- **Fullscreen Kiosk Mode (Default)**:
  `python3 app_hardware_diagnostic.py --kiosk`
- **CLI Acceptance Audit**:
  `python3 app_hardware_diagnostic.py`
- **JSON Telemetry Export**:
  `python3 app_hardware_diagnostic.py --json`
