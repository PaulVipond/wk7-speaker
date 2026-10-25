# LG WK7 ThinQ Speaker — Revival Project (Technical Reference)

Deep documentation for the revival of an LG WK7 ThinQ (XBOOM AI, 2018,
Android Things / Google Cast, Meridian-tuned) that LG and Google forcibly
retired: Android Things shut down (Jan 2022), the LG companion app was
pulled, and a factory reset trapped the unit in an unconfigurable setup loop.

If you just want your speaker working again, start with the main README
(one level up) — it assumes no technical background. This file is the
engineering record: what was done, exactly how, and what's next.

Project status: **speaker fully rescued at the network level.** It is a
permanent, first-class Cast speaker on the LAN with Wi-Fi credentials that
survive power cycles.

## Current state (verified)

- Speaker is provisioned on the home network and **auto-rejoins after
  cold power-off** (verified twice, including end-to-end cast test after reboot).
- Wi-Fi persistence achieved via the stock Eureka setup API: `connect_wifi`
  (encrypted) followed by `save_wifi` (empty body) flips `wpa_configured: true`.
- Cast receiver alive: broadcasts `_googlecast._tcp` as `LG-WK7_XXXX`
  (port 8009). Default Media Receiver verified playing real audio (SomaFM),
  volume control, quit-app stop. TTS/announcements/HA all viable.
- LED ring shows **amber** — expected and permanent: it means "connected to
  Wi-Fi but Google cloud unreachable". The cloud it wants no longer exists.
  Cosmetic only. Local TTS chime endpoint (`/setup/play_sound`) works.
- Voice Assistant: dead forever (cloud-only). Casting: fully working.
- Microphone: locked. No network path. Unlock requires code execution
  (see docs/03-usb-mic-unlock-micom.md).
- USB service port: no enumeration with any cable/port combination tried
  (consistent with repo issue #4: retail units appear not to expose USB ADB).
  A data cable is on order; the real path forward is the MICOM UART (see doc 03).

## What's in this folder

- `WK7-reforged/` — clone of github.com/tomkubik/WK7-reforged (community
  firmware: AirPlay 2, Spotify Connect, moOde, Alpine chroot in /data).
  Key reading: `WK7-software-for-unlocked-bootloader/wk7-probe/REPORT.md` and
  `MICOM_PROTOCOL.md`.
- `scripts/` — working tools from the rescue:
  - `all/provision-wifi.py` — cross-platform provisioning tool (Windows/
    macOS/Linux, Python 3 stdlib only — includes a built-in minimal RSA;
    prompts for Wi-Fi credentials, sends connect_wifi + save_wifi).
  - `linux/provision-wifi.sh` — fully automated Linux provisioning (safe
    NetworkManager hop with guaranteed rollback).
  - `linux/scan-setup-ap.sh` — connect to the speaker's setup AP and
    port-scan it.
  - `castctl.py` — per-room Cast control (list/play/stop/vol/status).
  - `micom-sniff.py` — MICOM UART tap: live frame decoder + frame sender
    (see doc 03).
  - `linux/cast-stop.py` — reliable stop (quit_app; plain stop misses
    orphaned streams).
- `docs/01-wifi-provisioning.md` — how the provisioning was reverse-engineered,
  the exact wire format, endpoint inventory, pitfalls.
- `docs/02-cast-control.md` — how casting works on this unit, what works from
  what software, multi-speaker strategy, known pitfalls.
- `docs/03-usb-mic-unlock-micom.md` — the full plan for unlocking the USB port
  and microphone via the MICOM UART, including the frame protocol and the
  boot-sniffing experiment design.
- `docs/04-intercom-and-voice-roadmap.md` — the end-goal architecture: 4-speaker
  house intercom, Home Assistant, Spotify routing, HA Assist voice satellites.

## Key facts learned (the short version)

1. A factory-reset WK7 broadcasts an open setup AP (`LG-WK7_XXXX.n019`) and
   runs the Chromecast Eureka setup REST API on https://<gateway>:8443 (self-
   signed; `curl -sk`). Ports on the setup AP: 53, 8008, 8009, 8443, 9000,
   9741, 10001. The speaker is the DHCP gateway of a tiny /29.
2. Provisioning the Wi-Fi requires the exact Google Home app schema, recovered
   by pulling the Google Home APK from an Android phone (adb) and decompiling
   with jadx. Missing `wpa_id`/`scan_ssid` (or extra fields) = HTTP 500.
   Plaintext password = 500. RSA-PKCS1-encrypted `enc_passwd` = 200 OK.
3. `POST /setup/save_wifi` (EMPTY body) is mandatory for persistence. Without
   it the join is lost at the next reboot.
4. Spotify does not list this speaker (it fails Spotify's receiver-app
   availability check because the device never completed Google registration).
   Don't be fooled by similarly-named devices from other brands appearing in
   Spotify's device picker.
5. The MICOM microcontroller owns the USB mux, and its UART protocol is
   documented in the Reforged repo — including command 0xC2 (USB switch
   control). This is the most promising unlock path for both USB-ADB and the
   microphone.
