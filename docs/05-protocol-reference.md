# WK7 Observed Protocol Reference

Everything here was observed on a **retail LG WK7 ThinQ** (Cast 1.36.157053,
Eureka v9) or recovered from decompiling the **Google Home app** v3.40.48.2
(classes aeqe/aeps/aepo/aepz/aehz/aehx/aehy/aepg) — as noted per section.
Sorted from physical layer up.

## 1. The setup access point (observed)

- Broadcast only while unconfigured (factory reset, or pre-join). Once
  `save_wifi` has persisted and the unit reboots, the AP is gone.
- SSID: `LG-WK7_XXXX.n019` — the 4-digit suffix is **randomized per reset**
  (observed: `_8764`, `_0169`, `_3658`, `_8878`, `_9457`), so match on the
  `LG-WK7` prefix. Open (no password). 2.4 GHz.
- The speaker runs DHCP and is the gateway of a tiny **/29**
  (observed 192.168.255.248/29, speaker = .249, client = .251).
- The AP **beacons intermittently** — a failed connect usually means "scan
  again", not "gone".
- TCP ports open on the speaker during setup mode: **53, 8008, 8009, 8443,
  9000, 9741, 10001**. Full 1-65535 scan found nothing else.
- While joining a new network the AP drops mid-join — senders talking to the
  setup IP lose contact even though their last request may have succeeded
  (the root cause of the save-confirmation loss; see Eureka §3).
- The Wi-Fi radio is less limited than "2.4 GHz only": observed joining a
  nominally-5 GHz SSID (either dual-band broadcast by the router or actual
  dual-band capability — not yet distinguished).

## 2. Eureka setup REST API (observed + decompiled Google Home app)

Base: `https://<speaker>:8443`, TLS with a self-signed cert → `curl -sk` /
no-verify. Same endpoints also answer on `http://<speaker>:8008` for GETs.

Probing semantics (reliable across all our tests): POST `{}` →
**404** = endpoint absent in this build; **400** = exists, body rejected;
**500** = body passed schema but the handler choked (schema mismatch, NOT a
dead backend).

| Endpoint | Method | Body | Status on this build |
|---|---|---|---|
| `/setup/eureka_info?options=detail,320` | GET | — | 200: name, model, setup_state, wpa_configured, wpa_state, tos_accepted, public_key, connected, ssid, uptime |
| `/setup/scan_results` | GET | — | 200: APs visible to the speaker (ssid, bssid, wpa_auth, wpa_cipher, signal) |
| `/setup/connect_wifi` | POST | see schema below | 200 only with encrypted body; 500 for any plaintext/extra/missing-field variant |
| `/setup/save_wifi` | POST | **empty** | 200 `{"setup_state":64}`; flips wpa_configured true |
| `/setup/set_eureka_info` | POST | e.g. `{"name":"kitchen"}` | 200; persists (tos_accepted verified) |
| `/setup/play_sound` | POST | `{"sound_id":1}` | 200; plays local chime |
| `/setup/reboot` | POST | `{"params":"now"}` | 200; verify via uptime actually dropping (sometimes ignored once configured) |
| `/setup/forget_wifi`, `/setup/scan_wifi`, `/setup/get_app_device_id`, `/setup/send_log_report` | POST | — | present per the app's endpoint inventory (grep of `l("...")` in the decompiled sources); not tested |
| `/setup/configure_ap`, `/setup/scan_ap`, `/setup/set_network`, `/setup/reboot_now`, `/setup/save_network`, `/setup/finish`, `/setup/smart_home/actions/setup` | POST | — | **404 — absent in this firmware** |

### 2.1 connect_wifi wire format (decompiled from aeqe.java/aeps.java)

```json
{"ssid":"...", "wpa_auth":7, "wpa_cipher":4, "wpa_id":0,
 "scan_ssid":0, "enc_passwd":"<base64>"}
```
- `enc_passwd` = base64( RSA PKCS1v15( UTF-8(Wi-Fi password),
  device public_key ) ). The app's `aehz.a()` confirms padding and that the
  plaintext `passwd` fallback exists in the protocol — but this unit rejects
  it (500); encryption is mandatory here.
- Strict schema: extra fields (bssid, signal_level) or missing
  `wpa_id`/`scan_ssid` → 500. `wpa_auth`: WPA2_PSK=7 (open=1, WEP=2/3,
  WPA2_SAE=9). `wpa_cipher`: CCMP=4 (TKIP=3, AES=5) — take real values from
  the speaker's own `scan_results`. `scan_ssid:1` for hidden SSIDs.
- **Sequence**: connect_wifi (joins) → save_wifi (persists). Without
  save_wifi the join is lost at the next power cycle. save_wifi works both
  via the setup AP and via the LAN address after joining.
- `eureka_info.public_key` is a **bare RSAPublicKey** DER
  (`SEQUENCE{INTEGER n, INTEGER e}`), not SubjectPublicKeyInfo — the app
  patches the SPKI header on by hand (the `m` byte array in `aehz.java`).

## 3. Cast (observed via pychromecast + our stdlib client)

- Discovery: `_googlecast._tcp` mDNS, port 8009. Observed TXT record
  fields on this unit (meanings partly community-inferred, not official):

  | Field | Observed value | Meaning |
  |---|---|---|
  | `fn` | `LG-WK7_XXXX` | friendly name (set via set_eureka_info) |
  | `md` | `LG WK7 ThinQ Speaker` | model string |
  | `id` | UUID | cast device UUID (regenerated each factory reset) |
  | `cd` | 32-hex hash | device certificate digest — **regenerated each
    factory reset**, never signed/activated by Google |
  | `st` | `2` | setup state: not fully set up / unregistered |
  | `rs` | empty | receiver state |
  | `nf` | `1` | ? (community: "not foreground"?) |
  | `bs` | hotspot BSSID | the setup AP's BSSID persists in the record |
  | `ca` | `67588` | capabilities bitmask (community-inferred) |
  | `ve` | `05` | version |
  | `rm` / `ic` | hash / `/setup/icon.png` | ? / icon path |

  **Sender gating (field-tested; mechanism inferred, not officially
  documented anywhere):** consumer senders built on Google's Cast SDK
  (YouTube app, Chrome's Cast feature, Spotify) discover the device via
  mDNS but do not list it. Their filter combines the discovery flags
  (`st=2` = unregistered) with the app-availability handshake — the
  sender asks the device (CastV2 AppAvailability) whether it can run the
  sender's receiver app, and the answer on a registered Cast device
  traces back to Google's cloud registry through factory-issued device
  certificates. This unit's identity is self-generated (cd changes per
  reset) and its registration died with Android Things, so the handshake
  chain fails and the senders hide the device. Senders that skip these
  checks (VLC — verified; pychromecast/HA; mkchromecast; this repo's
  client) work normally.
- Port 8009 speaks **CastV2**: TLS (self-signed, no verify) + 4-byte
  big-endian length prefix + a CastMessage protobuf:

```
field 1  varint   protocol_version = 0 (CASTV2_1_0)
field 2  string   source_id      (sender-chosen, e.g. "sender-0")
field 3  string   destination_id ("receiver-0" or app transportId)
field 4  string   namespace
field 5  varint   payload_type = 0 (STRING)
field 6  string   payload_utf8   (JSON)
```

- Namespaces: `urn:x-cast:com.google.cast.tp.connection` (connect/close),
  `...tp.heartbeat` (PING/PONG), `com.google.cast.receiver` (GET_STATUS,
  LAUNCH, STOP), `com.google.cast.media` (LOAD, media status).
- Handshake rules (each learned from a live failure):
  1. Send `{"type":"CONNECT"}` on the connection namespace to `receiver-0`
     immediately after TLS — otherwise the receiver answers
     `{"type":"CLOSE"}` to everything.
  2. **Never `LAUNCH` the Default Media Receiver (CC1AD845) when it is
     already running** — LAUNCH kills the existing session and your cached
     transportId becomes invalid. GET_STATUS first; LAUNCH only if absent.
  3. After LAUNCH, extract `sessionId` + `transportId` from the
     RECEIVER_STATUS payload, CONNECT to the transportId, then LOAD on the
     media namespace with snake_case keys (`autoplay`, `current_time`).
  4. **A bare `{"type":"STOP"}` is silently ignored** — the receiver
     requires `sessionId` in the STOP payload. (This bug shipped: our
     20-second test "stopped cleanly" while audio kept playing.)
  5. The receiver sends PING frames; replying PONG is polite but not
     required for short sessions.
- Orphaned streams: media launched by a sender that exits keeps playing; a
  NEW sender sees "no session active" and media-level stop cannot kill it.
  Receiver-level STOP (with sessionId) or a fresh LAUNCH-and-STOP does.
- Unregistered devices accept the Default Media Receiver (local, embedded)
  fine. Field-tested sender gating: the YouTube app, Chrome browser Cast
  (phone + desktop) and Spotify never list the speaker — they discover it
  via mDNS, then check Google's cloud device registry / receiver-app
  entitlement and hide it. Senders using the Default Media Receiver (VLC —
  verified, this repo's client, pychromecast/HA, mkchromecast) work.
  Google Home app management: dead.

## 4. MICOM UART (community-documented — WK7-reforged)

Not our own work: the full frame protocol lives in
`WK7-reforged/.../wk7-probe/MICOM_PROTOCOL.md`. Summary: 115200 8N1, frames
`E5 TID CMD1 CMD2 CKSUM LEN DATA`, commands include **0xC2/00 USB switch
control** (state values still unknown), LEDs (0xC0), keys (0xB0 poll, hidden
service codes 0x83/0x85/0x91), MCU version/reset. Our plan for using it:
`docs/03-usb-mic-unlock-micom.md`.

## 5. Firmware/OS facts (observed + repo)

- Cast build 1.36.157053, Eureka v9, Android Things, Qualcomm APQ8009,
  Linux 3.10.49. No USB ADB observed on retail units (repo issue #4
  reports the same); no port 5555 on Wi-Fi (that was the dev prototype).
- After full provisioning + reboot the speaker appears on the LAN, joins
  the same SSID each boot (`wpa_configured` true persists), and keeps
  casting (verified after cold power-off).
