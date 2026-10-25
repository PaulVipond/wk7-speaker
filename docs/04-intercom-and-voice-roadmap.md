# House Intercom, Voice Control & Music — End-State Architecture

Target: four WK7s (kitchen / bedroom / lounge / garage) as rooms in a fully
local smart home. No cloud dependencies anywhere.

## Capability map of one WK7

| Capability | Stock (today) | With Reforged | Notes |
|---|---|---|---|
| Music out (Cast) | YES (VLC/HA/pychromecast) | via Cast? no — replaced | Google/Spotify senders hide the unregistered device (see doc 02) |
| Spotify native | no (bridge needed) | YES (spotifyd on-device) | stock fails Spotify's availability check |
| AirPlay 2 | no | YES (shairport-sync + nqptp) | whole Apple ecosystem + its own sync |
| Synced multi-room | no (cloud Cast groups dead) | YES (moOde Opus/RTP or AirPlay 2) | stock same-URL casting drifts seconds |
| Buttons/LED/volume-per-amp | dead/amber | YES (MICOM daemon) | protocol already decoded |
| TTS announcements | YES (via Cast) | YES | HA, castctl, any Cast sender |
| Microphone | NO | NO (unbuilt everywhere) | the open project — doc 03 |
| HA voice satellite | after mic unlock | after mic unlock | wyoming-satellite in the chroot |

## Tier 1 — Buildable today (stock firmware)

Home Assistant in Docker on the always-on machine (already runs Docker):
- 4 media_player entities (one per speaker), auto-discovered.
- Announce/TTS to any room or all rooms; radio automation; per-room scripts.
- Phone mic → speaker: NOT live pass-through. HA Assist is text/intent based.
  Three broadcast options:
  1. Voice-message broadcast (RECOMMENDED): phone widget records a clip → HA
     plays it on all speakers. Real voice, ~3-5 s delay. ~30 lines of HA.
  2. TTS broadcast: speak/type "broadcast dinner is ready" → Piper voice on
     all speakers. Instant, synthetic.
  3. Live mic stream (icecast/RTSP server → cast URL): possible but 1-3 s Cast
     buffer lag and 24/7 server; only if 1 isn't enough.
- Spotify: spotifyd/librespot bridge on the always-on machine. One instance
  per speaker, named per room ("Kitchen", "Lounge"...) → they appear in
  Spotify's device picker; HA's Spotify integration can also target them.
  Requires Spotify Premium. Latency seconds; control fully native Spotify UX.

## Tier 2 — Requires Reforged firmware install (USB/ADB or MICOM path, doc 03)

- Native Spotify Connect per speaker (no bridge, no always-on PC).
- AirPlay 2 + moOde multi-room: one of the three Raspberry Pis on the LAN runs
  moOde as the jukebox/sender; WK7s join as synchronized receivers (Opus/RTP
  multicast; Reforged ships wk7-igmp to keep group membership alive on the
  3.10 kernel). AirPlay 2 gives Apple-originated sync via nqptp.
- moOde control: web UI (http://moode.local) for browsing/grouping; MPD
  protocol underneath → HA's MPD integration exposes it as a media_player;
  HTTP command API for scripts.
- Web dashboard per speaker (http://wk7.local): per-source gain, LED
  brightness, button lock, restarts. Buttons and LED ring work.

Locked-bootloader caveat: install works without flashing (Alpine chroot into
/data) but no auto-start on cold boot — one Wi-Fi ADB poke per power cycle
(acceptable for always-on speakers).

## Tier 3 — Requires the microphone unlock (doc 03 phase 4)

- WK7s as HA Assist voice satellites (wyoming-satellite in the chroot):
  mic PCM streams to HA; openWakeWord + Whisper + intents + Piper replies
  out of the speaker. Fully local voice control of the house.
  - Push-to-talk mode: high confidence (MICOM button daemon exists).
  - Hands-free: depends on capture quality and echo handling (mic hears the
    speaker's own output; hardware AEC may live in ADSP blobs).
- Two-way intercom: mic'd rooms talk; all rooms listen.
- Everything found feeds back to tomkubik/WK7-reforged (mic capture is the
  project's biggest open gap — our work would be the first).

## Sequenced build order (each step independently useful)

1. HA in Docker + speaker entities + TTS announce (an evening).
2. Voice-message broadcast automation (an evening).
3. spotifyd bridge prototype on the current speaker (an evening; Premium).
4. USB cable + MICOM UART work (a weekend of bench time, doc 03).
5. Reforged install if a shell materializes (per repo docs).
6. Voice satellites once mic capture exists.

## Network reconnaissance notes (generic)

- Map your own LAN before building: `avahi-browse -rt _googlecast._tcp` finds
  every Cast speaker; a parallel `nc -z -w1 <ip> 5555` sweep over live hosts
  reveals any device running ADB — on our network one unrelated Android TV
  answered on 5555 and would have demanded authorization. ALWAYS verify
  `getprop ro.product.model` before touching anything that answers ADB.
- Anything that Spotify CAN see (Sonos, Nest audio, etc.) is a useful
  sanity check for your Wi-Fi multicast/mDNS config, but is otherwise
  unrelated to the WK7 revival.
- One low-power always-on box (a Pi or a mini PC) should be designated the
  moOde sender / bridge host before Tier 2 begins.
