#!/sbin/sh
# Clean shutdown for Alpine Linux Chroot on Xperia Z Ultra
ALPINE_DIR="/data/alpine"

echo "[*] Stopping Alpine services..."
pkill -f "/usr/sbin/sshd" 2>/dev/null
pkill -f "battery-guardian.sh" 2>/dev/null

echo "[*] Unmounting filesystems..."
umount "$ALPINE_DIR/dev/pts" 2>/dev/null
umount "$ALPINE_DIR/dev" 2>/dev/null
umount "$ALPINE_DIR/sys" 2>/dev/null
umount "$ALPINE_DIR/proc" 2>/dev/null

echo "[+] Alpine Linux stopped cleanly."
