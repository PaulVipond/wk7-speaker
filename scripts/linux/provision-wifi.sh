#!/bin/bash
# provision-wifi.sh — provision a factory-reset LG WK7 ThinQ over its setup AP
# using the stock Eureka setup API (wire format recovered from the decompiled
# Google Home app; see docs/01-wifi-provisioning.md).
#
# EDIT THE VARIABLES BELOW, then run on a Wi-Fi machine with NetworkManager.
# The script hops to the speaker's setup AP and ALWAYS rolls back to your home
# Wi-Fi (trap-based), so it is safe on a single-NIC laptop.
#
# Requires: nmcli, curl, openssl, and an existing nmcli profile "wk7setup"
# bound to the speaker's setup AP (see docs/01 §1).
set -u

# Optional local override: if local.sh exists (gitignored), it wins. Use it to
# keep real values out of the committed file.
[ -f "$(dirname "$0")/local.sh" ] && . "$(dirname "$0")/local.sh"

# ---- EDIT ME ----------------------------------------------------------
WIFI_IF="wlp0s20f3"              # your Wi-Fi interface
HOME_CONN="YourHomeWifi"         # nmcli profile name of your home Wi-Fi
SSID="YourWifiSSID"              # the 2.4 GHz SSID to provision (WK7 is 2.4-only)
PSK_FILE="wifi_psk.txt"          # file containing the Wi-Fi password (one line)
T=192.168.255.249                # speaker IP on its setup AP (DHCP gateway of the /29)
# ----------------------------------------------------------------------
# NOTE: wifi_psk.txt is gitignored. Never commit it.

LOG="provision.log"
PUB="wk7_pub.pem"
exec >"$LOG" 2>&1

restore() {
  echo "=== ROLLBACK: restoring $HOME_CONN ==="
  nmcli device disconnect "$WIFI_IF" >/dev/null 2>&1
  for i in 1 2 3 4 5; do
    nmcli connection up id "$HOME_CONN" >/dev/null 2>&1 && break
    sleep 3
  done
  ping -c1 -W3 1.1.1.1 >/dev/null 2>&1 && echo "ROLLBACK OK" || echo "ROLLBACK WARNING"
}
trap restore EXIT

PSK=$(tr -d '\r\n' < "$PSK_FILE")
[ -n "$PSK" ] || { echo "no password in $PSK_FILE"; exit 1; }

echo "=== provision start $(date) ==="
nmcli connection up wk7setup >/dev/null 2>&1
sleep 5
ping -c1 -W2 "$T" || { echo "speaker setup AP unreachable, abort"; exit 1; }

# Pull the device RSA public key (base64 DER SPKI) and wrap it as a PEM.
curl -sk -m 5 "https://$T:8443/setup/eureka_info" | grep -o '"public_key":"[^"]*"' | cut -d'"' -f4 \
  | (echo "-----BEGIN PUBLIC KEY-----"; fold -w 64; echo "-----END PUBLIC KEY-----") > "$PUB"
openssl pkey -pubin -in "$PUB" -noout 2>/dev/null || { echo "pubkey BAD"; exit 1; }
echo "pubkey OK"

# enc_passwd = base64(RSA PKCS1v15(password, device_pubkey)).
# The exact JSON schema matters: extra fields or missing wpa_id/scan_ssid => HTTP 500.
ENC=$(printf '%s' "$PSK" | openssl pkeyutl -encrypt -pubin -inkey "$PUB" 2>/dev/null | base64 -w0)
BODY="{\"ssid\":\"$SSID\",\"wpa_auth\":7,\"wpa_cipher\":4,\"wpa_id\":0,\"scan_ssid\":0,\"enc_passwd\":\"$ENC\"}"

echo "=== POST /setup/connect_wifi ==="
curl -sk -m 12 -X POST -H "Content-Type: application/json" -i -d "$BODY" \
  "https://$T:8443/setup/connect_wifi" | head -8

echo "=== waiting for association ==="
for i in $(seq 1 20); do
  sleep 3
  ST=$(curl -sk -m 3 "https://$T:8443/setup/eureka_info" 2>/dev/null \
       | grep -o '"connected":[a-z]*\|"ssid":"[^"]*"' | tr '\n' ' ')
  echo "  $i: ${ST:-AP gone (may be switching networks)}"
  echo "$ST" | grep -q '"connected":true' && break
done

echo "=== POST /setup/save_wifi (MANDATORY for persistence) ==="
curl -sk -m 10 -X POST -H "Content-Type: application/json" -d '' \
  "https://$T:8443/setup/save_wifi" | head -2
echo

echo "=== final state ==="
curl -sk -m 3 "https://$T:8443/setup/eureka_info" \
  | grep -o '"connected":[a-z]*\|"wpa_configured":[a-z]*\|"wpa_state":[0-9]*\|"ssid":"[^"]*"'
echo
echo "wpa_configured should be true. Find the speaker on your LAN with:"
echo "  avahi-browse -rt _googlecast._tcp"
echo "=== done $(date) — see $LOG if anything failed ==="
