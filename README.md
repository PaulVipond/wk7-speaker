# Bring Your LG WK7 ThinQ Speaker Back From the Dead

LG and Google switched off the servers this speaker depends on. If you have a
WK7 that sits there showing amber lights, or one you factory-reset and can
never set up again — it is **not** broken. This guide brings it back to life
as a normal wireless speaker you can play music on from your phone, tablet,
or computer.

You do NOT need to be technical to read this guide — but the one-time setup
step does involve running a small program on a computer, so if that's not you,
this is a great job to hand to a friend, colleague, or teenager who's
comfortable with computers. It takes about 10 minutes, once.

## What you'll have afterwards

- The speaker joins your home Wi-Fi by itself, every time you plug it in.
- It appears in apps the same way other wireless speakers do — anything with
  a "Cast" symbol (a small TV/wifi icon) can play on it: YouTube, BBC Sounds,
  Plex, VLC, and many more. iPhones and Android phones both work.
- Home Assistant users get a controllable speaker too.
- It stays like this permanently. Power cuts, moving house (well — you'd
  re-run setup for a new Wi-Fi), unplugging it: all fine.

## What will NOT come back

Being honest, because the sales brochure isn't:

- **The voice assistant is gone for good.** "OK Google" talked to Google's
  servers, and those servers no longer accept this speaker. No fix exists or
  will ever exist for that. What you get back is a *speaker* — and a very
  good one (it was tuned by Meridian, a hi-fi company).
- The lights on top will stay amber. That's the speaker telling you it can't
  reach Google — think of it as a permanently lit "no service" indicator,
  like an old phone showing no signal. It doesn't affect anything.
- Spotify's app won't list the speaker directly (see "Spotify" below).

## What you need

1. Your LG WK7 speaker and its power supply.
2. Your home Wi-Fi name and password. **It must be a 2.4 GHz network** — this
   is the older, longer-range kind of Wi-Fi. If you only see one network
   name, you're probably fine. If your Wi-Fi has both "something" and
   "something_5G" names, use the one *without* 5G.
3. A laptop or desktop computer with Wi-Fi, **running Linux** (the setup
   program currently needs it — anyone can install Linux on a spare machine
   or use a bootable USB stick, or borrow a Linux laptop). The script handles
   everything; the helper just types a couple of commands.

## The one-time setup (your helper does this)

1. Download this repository's files ("Code" → "Download ZIP") and open the
   `scripts` folder on the Linux computer.
2. Put your Wi-Fi password in a file called `wifi_psk.txt` (just the
   password, nothing else, and never share that file with anyone).
3. Edit the few "EDIT ME" lines at the top of `provision-wifi.sh`:
   - `SSID` — your Wi-Fi's name
   - `HOME_CONN` — the name your Linux computer uses for your Wi-Fi
     (in Linux, the command `nmcli connection show` lists it)
   - Leave the rest alone.
4. Make sure the speaker is powered on. It doesn't matter what state it's in.
5. Run the script:

   ```
   bash provision-wifi.sh
   ```

6. Wait a few minutes. The script prints progress and at the end you want to
   see `wpa_configured:true` in the final lines.
7. That's it. Plug your phone into the same Wi-Fi, open an app with a Cast
   button, tap the Cast symbol, and the speaker appears under its name
   (something like "LG-WK7_XXXX"). Pick it, press play, music comes out.

Full technical details of what the script does — including for people who
want to reproduce it on other devices or understand the protocol — are in
the `docs/` folder.

## Troubleshooting

- **The script says the speaker's setup network is unreachable.** The
  speaker only broadcasts its special setup Wi-Fi in certain states. Power
  the speaker off and on, then run the script within a couple of minutes of
  it finishing its light show. The setup network is called something like
  "LG-WK7_XXXX.n019".
- **Music apps on the phone don't show the speaker.** Check the phone is on
  the same Wi-Fi, and that it's the 2.4 GHz one the speaker was set up with.
  Turning Wi-Fi off and back on the phone usually makes it appear.
- **Speaker stops appearing after you move it / change Wi-Fi.** Re-run the
  one-time setup with the new Wi-Fi details. The speaker forgets Wi-Fi
  settings if you change its network — that's normal.
- **No sound while casting.** In the app's Cast controls, try sliding the
  volume up — the speaker remembers its volume separately and sometimes it's
  just low.

## Spotify

The Spotify app is special: it refuses to show speakers that Google hasn't
registered — and since Google's registration is dead, the WK7 never appears
in Spotify's device list directly. Everything else (YouTube, BBC, VLC,
Chrome, Plex...) is unaffected.

Workarounds if Spotify is your main thing:
- Cast your whole phone screen/tab audio from the Chrome browser, or
- Ask your helper about the "spotifyd bridge" — software that makes Spotify
  see the speaker indirectly (details in `docs/04`).

## Going further (for the technically curious)

The `docs/` folder contains the full engineering story and the roadmap for
the community effort: making the buttons and lights work again, synchronized
multi-room playback, and the quest to switch the microphone back on
(the last big unsolved challenge). Start with `docs/00-technical-reference.md`.
