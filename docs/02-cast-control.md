# Cast Control on the WK7

## What works

The stock Cast receiver is fully functional as a **local** Cast target. The
speaker never completed Google registration (that cloud is dead), which does
not matter for casting to the Default Media Receiver.

Verified working:
- pychromecast `play_media(<stream-url>, 'audio/mpeg')` — real audio out,
  state PLAYING, volume control.
- `scripts/all/provision-wifi.py --test` (our stdlib CastV2 client) — the
  built-in 20-second playback test.
- `POST /setup/play_sound {"sound_id":1}` — local confirmation chime.
- Home Assistant: the Google Cast integration is pychromecast underneath, so
  the speaker appears as a media_player entity (play/pause/stop/volume,
  play_media, TTS announcements) — no cloud involved. (High confidence from
  the shared stack; not yet tested on a live HA install.)

NOT working — Google/Spotify senders hide unregistered devices (field-tested
on YouTube's app and Chrome's Cast feature, phone and desktop; Spotify was
confirmed earlier):
- YouTube app: speaker not listed.
- Chrome browser Cast (tab/desktop audio): speaker not listed.
- Spotify app: speaker not listed.
These senders discover the speaker over mDNS (avahi shows it clearly) but
then check Google's cloud device registry / receiver-app entitlement before
showing it, and a device whose registration died with Android Things fails
that check. The Cast protocol itself is fully alive — only the walled-garden
senders refuse. Expect similar behavior from any sender that launches its
own cloud-hosted receiver app.

Untested, probably device-by-device:
- Third-party casting apps (VLC, BubbleUPnP, LocalCast, Plex) — depends on
  whether they use the Default Media Receiver path (works) or their own
  registered receiver apps (likely gated). mkchromecast (pychromecast-based)
  should work.

Also dead, permanently:
- Google Assistant voice (cloud-only, permanently dead).
- Google Home app management and Cast groups (cloud-managed).

## Multi-speaker layout

Every WK7 is an independent endpoint (unique serial-suffixed name, unique
UUID/IP). Provision each one individually (doc 01), then rename per room:

```
curl -sk -X POST -H "Content-Type: application/json" \
  -d '{"name":"kitchen"}' https://<speaker-ip>:8443/setup/set_eureka_info
```

Control individually with `scripts/castctl.py`:

```
castctl.py list
castctl.py play  kitchen https://ice1.somafm.com/groovesalad-128-mp3
castctl.py vol   kitchen 0.3
castctl.py stop  kitchen
castctl.py status kitchen
```

Room matching is a case-insensitive substring of the friendly name.

Synced multi-room over stock Cast is NOT possible (Google groups are cloud);
same-URL-to-all drifts by seconds. Real sync needs Reforged firmware (moOde
Opus/RTP multicast or AirPlay 2/nqptp) — see doc 04.

## Pitfalls (hard-won)

1. **Orphaned streams**: media launched by a sender that later exited keeps
   playing. A NEW sender reports "no session is active" and
   `media_controller.stop()` does nothing. Kill playback with
   `cast.quit_app()` (`scripts/linux/cast-stop.py`). Verify silence before claiming
   success — the stop-from-a-fresh-sender path lies.
2. **pychromecast API (v13+)**: `get_chromecasts()` returns a tuple
   `(casts, browser)`; metadata is `cast.cast_info.friendly_name/.host`
   (not `.device`); player state is `cast.media_controller.status.player_state`
   (not `cast.status.player_state`); call
   `media_controller.block_until_active(timeout)` before reading state or you
   get UNKNOWN (sync lag).
3. Cast devices buffer live streams 1-3 s — any mic-passthrough intercom built
   over Cast has inherent lag.
4. Volume set before a reboot persists (observed) — good; but note the amp
   starts loud at 1.0 after `save_wifi`/reset cycles. Set volume explicitly.
