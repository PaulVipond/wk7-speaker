# WK7 Wi-Fi Provisioning — How It Was Done

The stock provisioning path (LG companion app + cloud) is dead. This unit was
provisioned by talking the Google Home app's own protocol directly to the
speaker's Eureka setup API — a protocol recovered by decompiling the app.

## 1. The setup AP

After factory reset (and every boot while unconfigured), the WK7 broadcasts an
open access point: `LG-WK7_XXXX.n019` (2.4 GHz, BSSID like
FA:8F:CA:XX:XX:XX). The AP **beacons intermittently** — if a connect fails,
rescan and retry; do not assume it's gone.

Connect with a locked-BSSID nmcli profile (flaky otherwise):

```
nmcli connection add type wifi ifname wlp0s20f3 con-name wk7setup \
  802-11-wireless.ssid "LG-WK7_XXXX.n019" \
  802-11-wireless.mode infrastructure \
  802-11-wireless.bssid FA:8F:CA:XX:XX:XX
nmcli connection up wk7setup
```

Do NOT set `802-11-wireless-security.key-mgmt none` — that adds a security
section NetworkManager then rejects ("passwords required").

You get DHCP on a tiny /29; the speaker is the gateway (e.g. 192.168.255.249).

## 2. The Eureka setup API

`https://<speaker-ip>:8443` — self-signed cert, use `curl -sk`.
Endpoints on this firmware (Cast 1.36.157053, Eureka v9):

| Endpoint | Method | State |
|---|---|---|
| `/setup/eureka_info?options=detail,320` | GET | works — name, model, setup_state, wpa_configured, tos_accepted, RSA public_key |
| `/setup/scan_results` | GET | works — APs the speaker can see (ssid/bssid/wpa_auth/wpa_cipher) |
| `/setup/connect_wifi` | POST | works (encrypted body only) |
| `/setup/save_wifi` | POST | works (EMPTY body) — persists credentials |
| `/setup/set_eureka_info` | POST | works (e.g. `{"name":"kitchen"}`, `tos_accepted`) |
| `/setup/play_sound` | POST | works — `{"sound_id":1}` plays a local chime |
| `/setup/reboot` | POST | works — `{"params":"now"}`; verify via `uptime` dropping |
| `/setup/forget_wifi`, `/setup/scan_wifi`, `/setup/get_app_device_id`, `/setup/send_log_report` | POST | present (not tested) |
| `/setup/configure_ap`, `/setup/scan_ap`, `/setup/set_network`, `/setup/reboot_now`, `/setup/smart_home/actions/setup` | POST | **404 — absent in this build** |

Probing rule: `{}` → 404 = endpoint absent; 400 = exists but wrong body;
500 = body passed schema but handler choked. Earlier 500s were schema
mismatch (missing `wpa_id`/`scan_ssid`), not a dead backend.

## 3. The connect_wifi wire format

Recovered from the decompiled Google Home app (classes aeqe/aeps/aehz/aehx/
aehy in the obfuscated sources). The request that returns 200 OK:

```json
{
  "ssid": "YourWifiSSID",
  "wpa_auth": 7,
  "wpa_cipher": 4,
  "wpa_id": 0,
  "scan_ssid": 0,
  "enc_passwd": "<base64>"
}
```

- `enc_passwd` = base64( RSA PKCS1v15-encrypt( <Wi-Fi password>,
  <device public_key> ) ). The public key comes from `eureka_info.public_key`
  (base64 DER SubjectPublicKeyInfo). Wrap it as a PEM and:
  `printf '%s' "$PSK" | openssl pkeyutl -encrypt -pubin -inkey pub.pem | base64 -w0`
- Plaintext `passwd` instead of `enc_passwd` returns 500 on this unit —
  encryption is required.
- Extra fields (bssid, signal_level) or missing fields (wpa_id, scan_ssid)
  return 500.
- Enums: wpa_auth — WPA2_PSK=7 (others: open=1, WEP=2/3, WPA2_SAE=9);
  wpa_cipher — CCMP=4 (TKIP=3, AES=5). Take real values from the speaker's own
  `scan_results` entry.
- `scan_ssid: 1` is for hidden SSIDs.

## 4. Persistence

`connect_wifi` alone joins but does NOT save — credentials are lost at the
next power cycle. Immediately after a successful connect:

```
curl -sk -X POST -H "Content-Type: application/json" -d '' \
  https://<speaker>:8443/setup/save_wifi
```

Reply `{"setup_state":64}` and `wpa_configured: true`. Verified: after this,
the speaker rejoins Wi-Fi automatically after cold power-off (tested twice).

## 5. After joining the LAN

- The setup AP keeps broadcasting (dual station/AP mode) until reboot; ignore it.
- Find the speaker on the LAN: `avahi-browse -rt _googlecast._tcp`
  (friendly name, model, IP, port 8009 in one hit) — no ping sweep needed.
- Port 5555 is NOT open on retail units (that was the developer prototype).
  Wi-Fi ADB is not available; do not confuse other LAN devices that answer
  `adb connect` (on our network an unrelated Android TV answered on 5555 and
  demanded authorization — verify `getprop ro.product.model` before touching
  anything).

## 6. Ready-to-run script

`scripts/provision-wifi.sh` does the whole dance: hop to the setup AP with a
guaranteed `trap`-based rollback to home Wi-Fi, build the PEM from
`eureka_info`, encrypt, POST connect_wifi, wait for association, then POST
save_wifi. Edit the variables at the top (Wi-Fi interface, home connection
profile name, SSID) and put your Wi-Fi password in `wifi_psk.txt` beside the
script (gitignored — never commit it). It must run on a machine with Wi-Fi and
NetworkManager; the rollback makes it safe on a single-NIC laptop whose
session depends on internet.

## 7. How the wire format was recovered (the technique)

No mirror had the pulled LG app, and search engines are bot-walled from curl.
But any Android phone with the Google Home app installed is an APK source:

```
adb shell pm path com.google.android.apps.chromecast.app   # + splits
adb pull <each path>
# decompile: jadx release zip from github.com/skylot/jadx
jadx -q --no-res -d out/ base.apk
grep -rn 'wpa_auth' out/sources/                     # finds the JSON builders
grep -rohE 'l\("[a-z_]+", ?' out/sources/defpackage/ # lists every setup endpoint
```

The builder class (`aeqe.java`/`aeps.java`) shows the exact fields; `aehz.java`
shows the RSA encryption (RSA/None/PKCS1Padding, base64 of the raw DER key with
header patching — equivalent to wrapping in a PEM).
