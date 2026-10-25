# WK7 Wi-Fi Provisioning — How It Was Done

The stock provisioning path (LG companion app + cloud) is dead. This unit was
provisioned by talking the Google Home app's own protocol directly to the
speaker's Eureka setup API — a protocol recovered by decompiling the app.

## 1. The setup AP

After factory reset (and every boot while unconfigured), the WK7 broadcasts an
open access point: `LG-WK7_XXXX.n019` (2.4 GHz, BSSID like
FA:8F:CA:XX:XX:XX). The numeric suffix is **randomized on each reset** (one
reset showed `_8764`, the next `_0169`), so match on the `LG-WK7` prefix
rather than a remembered name. The AP **beacons intermittently** — if a
connect fails, rescan and retry; do not assume it's gone.

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

Reply `{"setup_state":64}` and `wpa_configured: true`. Persistence notes,
all reboot-verified on real hardware:

- Provisioned with a **2.4 GHz** SSID: settings survive cold power-off
  (verified repeatedly).
- Provisioned with a **5 GHz-named** SSID (dual-band router): the join
  succeeds and `wpa_configured` reads true, but after a power cycle the
  unit reverted to setup mode with the credentials gone. Unresolved whether
  the LAN-side save_wifi doesn't persist or the unit wipes config when it
  cannot rejoin at boot — either way, **provision the 2.4 GHz name**.
- The save request can land while its HTTP response is lost (AP teardown
  mid-reply): an HTTP 000/refused save may still have succeeded. Never
  infer the save state from the HTTP result — re-read `wpa_configured`
  from the speaker.
- The setup AP teardown window after association is sometimes seconds and
  sometimes immediate — a save sent right after `connect_wifi` returns 200
  (before waiting for association) is the most reliable over-AP timing.
- The only trustworthy persistence test is a power cycle: reboot-verify
  once after provisioning.

## 5. After joining the LAN

- The setup AP keeps broadcasting (dual station/AP mode) until reboot; ignore it.
- Find the speaker on the LAN: `avahi-browse -rt _googlecast._tcp`
  (friendly name, model, IP, port 8009 in one hit) — no ping sweep needed.
- Port 5555 is NOT open on retail units (that was the developer prototype).
  Wi-Fi ADB is not available; do not confuse other LAN devices that answer
  `adb connect` (on our network an unrelated Android TV answered on 5555 and
  demanded authorization — verify `getprop ro.product.model` before touching
  anything).

## 6. Ready-to-run tools

**`scripts/all/provision-wifi.py`** — the recommended tool for everyone
(Windows/macOS/Linux, needs only Python 3, no external libraries). You
connect your computer to the speaker's setup network manually, then the
tool: fetches `eureka_info`, parses the RSA public key with a built-in
minimal DER/PKCS#1 implementation (no openssl dependency), encrypts the
password, POSTs `connect_wifi`, waits for association, and POSTs
`save_wifi` (with retry + state verification — the setup AP can blip
during the join). Prompts for SSID/password interactively (password
hidden); stores nothing. After SUCCESS it offers a built-in playback
test: it scans the local /24 for the speaker (port 8009 + Eureka name
check) and plays a test radio station through a minimal hand-rolled
CastV2 client (TLS + CastMessage protobuf + Default Media Receiver,
all stdlib). CastV2 notes learned the hard way: the sender must open
with `CONNECT` on the connection namespace or the receiver answers
`CLOSE`; never `LAUNCH` the media receiver if it is already running
(that kills the session and invalidates your transportId); and
response matchers must return truthy values only.

**`scripts/linux/provision-wifi.sh`** — fully automated Linux version using
NetworkManager: hops to the setup AP with a guaranteed `trap`-based rollback
to home Wi-Fi (safe on a single-NIC machine whose session depends on
internet), builds the PEM with openssl, then connect_wifi + save_wifi.
Edit the "EDIT ME" variables (Wi-Fi interface, home connection profile
name, SSID) or drop overrides in `scripts/linux/local.sh` (gitignored).
Put the Wi-Fi password in `wifi_psk.txt` beside it (gitignored).

Note: the setup AP stops broadcasting once the speaker is fully configured
and rebooted — a configured speaker that has been power-cycled shows up
directly on your LAN (find it with `avahi-browse -rt _googlecast._tcp`).
The tools only need the setup AP for first-time provisioning.

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
