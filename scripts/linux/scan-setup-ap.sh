#!/bin/bash
# WK7 setup-hotspot probe: connect, scan, try ADB, roll back to home Wi-Fi.
# All output to provision.log. Never exits without restoring your home Wi-Fi.
# EDIT the variables below to match your machine and speaker's setup AP SSID.
[ -f "$(dirname "$0")/local.sh" ] && . "$(dirname "$0")/local.sh"
LOG="setup-ap-probe.log"
AP_SSID="LG-WK7_XXXX.n019"
WIFI_IF="wlp0s20f3"
HOME_CONN="YourHomeWifi"

exec >"$LOG" 2>&1
set -u

restore() {
  echo "=== ROLLBACK: restoring $HOME_CONN ==="
  nmcli device disconnect "$WIFI_IF" >/dev/null 2>&1
  for i in 1 2 3 4 5; do
    nmcli connection up id "$HOME_CONN" >/dev/null 2>&1 && break
    sleep 3
  done
  sleep 2
  if ping -c1 -W3 1.1.1.1 >/dev/null 2>&1; then
    echo "ROLLBACK OK: internet restored"
  else
    echo "ROLLBACK WARNING: no ping to 1.1.1.1, check manually"
  fi
  ip addr show "$WIFI_IF" | grep inet
}
trap restore EXIT

echo "=== probe started $(date) ==="
ip addr show "$WIFI_IF" | grep inet

echo "=== connecting to $AP_SSID ==="
nmcli device wifi connect "$AP_SSID" ifname "$WIFI_IF"
sleep 8
ip addr show "$WIFI_IF" | grep inet
ip route

GW=$(ip route | awk "/$WIFI_IF/&&/via/{print \$3; exit}")
SUBNET=$(ip route | awk "/$WIFI_IF/&&/dev/{print \$1; exit}")
echo "gateway=$GW subnet=$SUBNET"

# Candidate device IPs: gateway plus common fixed addresses
CANDS="$GW 192.168.4.1 192.168.43.1 192.168.49.1 192.168.5.1 192.168.0.1"

echo "=== ping sweep candidates ==="
for ip in $CANDS; do
  ping -c1 -W2 "$ip" >/dev/null 2>&1 && echo "PING OK: $ip"
done

echo "=== port scan on gateway $GW ==="
for p in 5555 5037 5556 80 443 8080 8888 9999 7777 6666 5554 4444 3000 5000; do
  if nc -z -w1 "$GW" "$p" 2>/dev/null; then echo "OPEN: $GW:$p"; fi
done

echo "=== port 5555 sweep of $SUBNET ==="
prefix="${SUBNET%.*}"
for i in $(seq 1 254); do
  ( nc -z -w1 "$prefix.$i" 5555 2>/dev/null && echo "ADB-PORT OPEN: $prefix.$i" ) &
done
wait

echo "=== arp table ==="
ip neigh show dev "$WIFI_IF"

echo "=== http probes ==="
for ip in $CANDS; do
  for p in 80 8080; do
    echo "--- http://$ip:$p/ ---"
    curl -s -m 3 -i "http://$ip:$p/" | head -15
  done
done

echo "=== adb attempts ==="
adb kill-server
for ip in $CANDS; do
  echo "--- adb connect $ip:5555 ---"
  timeout 5 adb connect "$ip:5555"
done
adb devices -l
DEVS=$(adb devices | awk 'NR>1 && $2=="device"{print $1}')
for d in $DEVS; do
  echo "--- getprop on $d ---"
  adb -s "$d" shell "getprop ro.product.model; getprop ro.product.device; getprop ro.build.type; getprop ro.debuggable; getprop ro.build.version.release; getprop ro.boot.verifiedbootstate; getprop ro.boot.vbmeta.device_state; getprop ro.sys.usb.default.config; getprop ro.secure" 2>&1
done

echo "=== probe finished $(date) ==="
