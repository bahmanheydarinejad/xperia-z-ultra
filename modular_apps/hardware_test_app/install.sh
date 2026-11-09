#!/bin/sh
# Setup and dependency hook for Togari All-Module Diagnostic Test Suite
set -e

echo "[*] Initializing dependencies for Togari All-Module Diagnostic App..."

# Check Python3 availability
if ! command -v python3 >/dev/null 2>&1; then
    echo "[*] Installing Python 3 and basic utilities..."
    apk add --no-cache python3 py3-pip evtest libqmi bluez i2c-tools wireless-tools wpa_supplicant || true
fi

# Make entrypoint executable
chmod +x /opt/app/entrypoint.sh 2>/dev/null || chmod +x entrypoint.sh 2>/dev/null || true

echo "[+] Application dependencies ready."
