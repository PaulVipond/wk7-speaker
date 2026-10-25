# Bring Your LG WK7 ThinQ Speaker Back to Life

> **With thanks and credit where it belongs:** this project stands on the work
> of **tomkubik**, whose **[WK7-reforged](https://github.com/tomkubik/WK7-reforged)**
> project is the seminal work on this speaker. WK7-reforged
> reverse-engineered the WK7's hardware (including the full MICOM
> microcontroller protocol), built complete replacement firmware, and
> documented every finding. This repository is a follow-on: using those
> findings to restore Wi-Fi and casting on a stock, factory-reset unit
> without opening it. His project is also the place for further research —
> the community effort to unlock the microphone, restore the buttons and
> lights, and replace the firmware entirely lives there.

LG and Google switched off the servers this speaker depends on. If you have a
WK7 that sits there showing amber lights, or one you factory-reset and can
never set up again — it is not broken. This guide restores it as a normal
wireless speaker you can play music on from your phone, tablet, or computer.

You don't need a technical background to follow this guide — but the one-time
setup step involves running a small program on a computer, so if that's not
you, it's a good job to hand to a friend or family member who is comfortable
with computers. It takes about 10 minutes, once.

## What you'll have afterwards

- The speaker joins your home Wi-Fi by itself, every time you plug it in.
- **You can play audio on it over your network** — with the tools in this
  repository (`--test` plays a built-in radio-station test), and with
  software that speaks the Cast protocol directly: Home Assistant (its
  Google Cast integration works — announcements, streams, scripts),
  mkchromecast, and similar local-first tools.
- **Important limitation — being straight with you:** apps from Google and
  Spotify (YouTube, the Chrome browser's Cast feature, the Spotify app) will
  NOT list this speaker. Those apps only show devices registered with
  Google's cloud, and that registration died when Google shut down the
  platform. The speaker still speaks the Cast protocol — those particular
  apps just refuse to talk to devices Google no longer recognizes.
- It stays like this permanently. Power cuts and unplugging it are fine.

## What will not come back

- **The voice assistant is gone for good.** "OK Google" relied on Google's
  servers, and those servers no longer accept this speaker. What you get
  back is a speaker — and a very good one (it was tuned by Meridian, a
  respected hi-fi company).
- The lights on top will stay amber. This is the speaker saying it can't
  reach Google — similar to a phone showing "no service". It doesn't affect
  anything.
- Spotify's app won't list the speaker directly (see "What can actually
  cast to it" below).

## What you need

1. Your LG WK7 speaker and its power supply.
2. Your home Wi-Fi name and password. **It must be a 2.4 GHz network** — the
   older, longer-range kind of Wi-Fi. If your Wi-Fi has both "something" and
   "something_5G" names, use the one *without* 5G.
3. Almost any computer (Windows, Mac, or Linux) with Wi-Fi, with
   **Python 3** installed. Python 3 is free and usually already there on Mac
   and Linux; on Windows it's a quick download from python.org.

## The one-time setup

1. Power the speaker on and wait for its light show to finish.
2. On the computer, connect to the speaker's own Wi-Fi network. It appears
   in your normal Wi-Fi list with a name like **"LG-WK7_XXXX.n019"** (the
   number is different each time — just pick the one starting with
   "LG-WK7") and needs no password.
3. Download this repository's files ("Code" → "Download ZIP"), open the
   `scripts/all` folder, and run:

   ```
   python3 provision-wifi.py
   ```

   (On Windows, the command may be just `python`.)

4. Answer the questions when asked: your Wi-Fi's name, then your Wi-Fi
   password (typing the password is hidden, and it is sent only to the
   speaker on your own network — never stored, never sent anywhere else).
5. Wait for the big **SUCCESS** message.
6. The tool then offers to play a test — reconnect the computer to your home
   Wi-Fi when it asks, press Enter, and the tool plays a radio station
   through the speaker for 20 seconds and then stops it automatically.
7. After that, the speaker is on your network for good. To play audio use
   the tools above — or see "What can actually cast to it" below for the
   honest list of what works and what doesn't.

**Quick test any time** — if the speaker is already set up and this computer
is on your home Wi-Fi, you can make it play a test radio station and stop
again with one command:

```
python3 scripts/all/provision-wifi.py --test
```

If you use Linux and prefer a fully automated version that switches Wi-Fi
for you (including the rollback), there is one in `scripts/linux/` —
`provision-wifi.sh`. The technical details of both, including how the
protocol was reverse-engineered, are in `docs/01-wifi-provisioning.md`.

## Troubleshooting

- **The script says the speaker's setup network is unreachable.** The
  speaker only broadcasts its special setup Wi-Fi in certain states. Power
  the speaker off and on, then run the script within a couple of minutes of
  it finishing its light show. The setup network is called something like
  "LG-WK7_XXXX.n019".
- **YouTube / Chrome / Spotify don't show the speaker.** This is not a fault
  and not fixable by reconnecting — those apps only list devices registered
  with Google's cloud, and this speaker's registration no longer exists.
  See "What can actually cast to it" below.
- **Speaker stops working after you change your Wi-Fi.** Re-run the
  one-time setup with the new Wi-Fi details. This is expected — the speaker
  keeps settings for the Wi-Fi it knows.
- **No sound during the built-in test.** The tool plays at whatever volume
  the speaker remembers — the volume can be raised later with the tools in
  `scripts/` (see docs/02).

## What can actually cast to it

Being precise, because this is the biggest let-down to understand up front:

- **Doesn't work:** YouTube, the Chrome browser's Cast feature, the Spotify
  app — anything that checks Google's device registry before showing a
  speaker. Those senders see the speaker on the network and hide it because
  its Google registration died with the platform.
- **Does work:** the tools in this repository; **VLC** (PC and Android —
  verified; it casts via the open Default Media Receiver, so Google's
  registry never enters into it); Home Assistant (its Cast integration
  speaks the protocol directly — announcements, radio, scripts);
  mkchromecast; and any software using the Default Media Receiver path.
- **Possibly works:** other third-party casting apps (BubbleUPnP, LocalCast
  and friends) — same principle as VLC: if the app uses the Default Media
  Receiver it will work; if it insists on its own Google-registered
  receiver app it won't. Try yours — it'll be obvious in seconds.

Options if Spotify is your main music source:
- The "spotifyd bridge" — software that lets Spotify reach the speaker
  indirectly (details in `docs/04`), or
- The community firmware (WK7-reforged) installs native Spotify Connect on
  the speaker itself — see "Going further".

## Playing music with VLC (the everyday way)

VLC is the easiest app that works with this speaker. It plays your own
files, internet radio, and playlists, and its casting isn't blocked by
Google. Get it free at videolan.org (also on Android and iPhone app stores).

**On a computer:**
1. Connect to the same Wi-Fi as the speaker, open VLC, and start playing
   something.
2. Open the menu **Playback → Renderer** (top menu bar; on some versions
   it's under "Renderer" in the playback controls).
3. The speaker appears in the list under its name (like "LG-WK7_XXXX") —
   pick it and the sound moves to the speaker.

**On a phone:** open VLC, play something, then in the playback menu look
for the renderer / "play on another device" option and pick the speaker.

**If the speaker doesn't appear in the list:** make sure the phone/computer
is on your home Wi-Fi (not the speaker's old setup network, not mobile
data). Casting discovery can take a minute after the speaker joins. As a
fallback, VLC on a computer can also cast straight to the speaker's
network address — the setup tool prints that address at the end of setup
(and `python3 scripts/all/provision-wifi.py --test` shows it any time);
see `docs/02-cast-control.md` for the exact command.

**Streams to try** (direct audio URLs, verified working): in VLC use
Media → Open Network Stream and paste one of these, then cast:

```
https://ice1.somafm.com/groovesalad-128-mp3   — ambient/chill
https://ice1.somafm.com/dronezone-128-aac     — spacey ambient
https://ice1.somafm.com/defcon-128-mp3        — electronic
https://stream.radioparadise.com/aac-128      — eclectic rock mix
```

Many more at somafm.com — copy the address of any "MP3" link on their
playlist page.

## Going further

The `docs/` folder contains a technical overview and a potential roadmap for restoring function: making the buttons and lights work again, synchronized
multi-room playback, and unlocking the microphone (the last big unsolved
challenge). Start with `docs/00-technical-reference.md`, and see
[WK7-reforged](https://github.com/tomkubik/WK7-reforged) for the active
firmware project.
