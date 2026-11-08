#!/sbin/sh
# Start Alpine Linux Chroot on Xperia Z Ultra
ALPINE_DIR="/data/alpine"

echo "[*] Initializing Alpine Linux environment..."

# Mount filesystem namespaces
[ -d "$ALPINE_DIR/proc" ] || mkdir -p "$ALPINE_DIR/proc"
[ -d "$ALPINE_DIR/sys" ] || mkdir -p "$ALPINE_DIR/sys"
[ -d "$ALPINE_DIR/dev" ] || mkdir -p "$ALPINE_DIR/dev"
[ -d "$ALPINE_DIR/dev/pts" ] || mkdir -p "$ALPINE_DIR/dev/pts"
[ -d "$ALPINE_DIR/run" ] || mkdir -p "$ALPINE_DIR/run"
[ -d "$ALPINE_DIR/var/empty" ] || mkdir -p "$ALPINE_DIR/var/empty"
chmod 700 "$ALPINE_DIR/var/empty"

mountpoint -q "$ALPINE_DIR/proc" || mount -t proc proc "$ALPINE_DIR/proc"
mountpoint -q "$ALPINE_DIR/sys" || mount -t sysfs sys "$ALPINE_DIR/sys"
mountpoint -q "$ALPINE_DIR/dev" || mount -o bind /dev "$ALPINE_DIR/dev"
mountpoint -q "$ALPINE_DIR/dev/pts" || mount -t devpts devpts "$ALPINE_DIR/dev/pts"

# Ensure DNS resolution
cat << 'EOF' > "$ALPINE_DIR/etc/resolv.conf"
nameserver 1.1.1.1
nameserver 8.8.8.8
EOF

# Ensure SSH host keys exist
if [ ! -f "$ALPINE_DIR/etc/ssh/ssh_host_rsa_key" ]; then
    chroot "$ALPINE_DIR" /usr/bin/env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin /usr/bin/ssh-keygen -A
fi

# Start SSH daemon
if ! pgrep -f "/usr/sbin/sshd" > /dev/null 2>&1; then
    echo "[*] Starting OpenSSH server on port 2222..."
    chroot "$ALPINE_DIR" /usr/bin/env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin /usr/sbin/sshd
else
    echo "[*] OpenSSH server already active."
fi

# Configure Battery Guardian Cron (checks every 2 mins)
if ! grep -q "battery-guardian.sh" "$ALPINE_DIR/etc/crontabs/root" 2>/dev/null; then
    echo "*/2 * * * * /usr/local/bin/battery-guardian.sh" >> "$ALPINE_DIR/etc/crontabs/root"
fi

# Start crond daemon
if ! pgrep -f "crond" > /dev/null 2>&1; then
    echo "[*] Starting Cron service (crond)..."
    chroot "$ALPINE_DIR" /bin/busybox crond -b -l 8
fi

# Run Battery Guardian once immediately
chroot "$ALPINE_DIR" /bin/sh /usr/local/bin/battery-guardian.sh

echo "[+] Alpine Linux SBC ready! SSH available on port 2222."
