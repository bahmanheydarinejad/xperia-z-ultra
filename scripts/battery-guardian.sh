#!/bin/sh
# Battery Guardian: 24/7 SBC Li-ion Swelling Prevention Check
# Target SoC: 55% - 65%
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
NODE="/sys/class/power_supply/battery/charging_enabled"
CAP_NODE="/sys/class/power_supply/battery/capacity"

mkdir -p /var/log

if [ -f "$NODE" ] && [ -f "$CAP_NODE" ]; then
    CAP=$(cat "$CAP_NODE" 2>/dev/null)
    STATUS=$(cat "$NODE" 2>/dev/null)

    if [ -n "$CAP" ] && [ -n "$STATUS" ]; then
        if [ "$CAP" -ge 65 ] && [ "$STATUS" -eq 1 ]; then
            echo 0 > "$NODE"
            echo "[$(date)] Capacity ${CAP}% >= 65%. Charging disabled." >> /var/log/battery-guardian.log
        elif [ "$CAP" -le 55 ] && [ "$STATUS" -eq 0 ]; then
            echo 1 > "$NODE"
            echo "[$(date)] Capacity ${CAP}% <= 55%. Charging enabled." >> /var/log/battery-guardian.log
        fi
    fi
fi
