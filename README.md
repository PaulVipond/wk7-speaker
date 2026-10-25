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
- It appears in apps the same way other wireless speakers do — anything with
  a "Cast" symbol (a small TV/wifi icon) can play on it: YouTube, BBC Sounds,
  Plex, VLC, and many more. iPhones and Android phones both work.
- Home Assistant users get a controllable speaker too.
- It stays like this permanently. Power cuts and unplugging it are fine.

## What will not come back

- **The voice assistant is gone for good.** "OK Google" relied on Google's
  servers, and those servers no longer accept this speaker. What you get
  back is a speaker — and a very good one (it was tuned by Meridian, a
  respected hi-fi company).
- The lights on top will stay amber. This is the speaker saying it can't
  reach Google — similar to a phone showing "no service". It doesn't affect
  anything.
- Spotify's app won't list the speaker directly (see "Spotify" below).

## What you need

1. Your LG WK7 speaker and its power supply.
2. Your home Wi-Fi name and password. **It must be a 2.4 GHz network** — the
   older, longer-range kind of Wi-Fi. If your Wi-Fi has both "something" and
   "something_5G" names, use the one *without* 5G.
3. A laptop or desktop computer with Wi-Fi, **running Linux**. The setup
   program needs Linux; a spare machine or a bootable USB stick works, or
   borrow a Linux laptop. The script handles everything — the person helping
   just types a couple of commands.

## The one-time setup (your helper does this)

1. Download this repository's files ("Code" → "Download ZIP") and open the
   `scripts` folder on the Linux computer.
2. Put your Wi-Fi password in a file called `wifi_psk.txt` (just the
   password, nothing else, and don't share that file with anyone).
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

6. Wait a few minutes. The script prints progress, and at the end you want to
   see `wpa_configured:true` in the final lines.
7. That's it. Connect your phone to the same Wi-Fi, open an app with a Cast
   button, tap the Cast symbol, and the speaker appears under its name
   (something like "LG-WK7_XXXX"). Pick it, press play, and music plays.

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
- **Speaker stops appearing after you change your Wi-Fi.** Re-run the
  one-time setup with the new Wi-Fi details. This is expected — the speaker
  keeps settings for the Wi-Fi it knows.
- **No sound while casting.** In the app's Cast controls, try sliding the
  volume up — the speaker keeps its own volume setting and sometimes it's
  simply low.

## Spotify

The Spotify app is special: it only shows speakers that Google has
registered, and since Google's registration no longer works for this model,
the WK7 never appears in Spotify's device list directly. Other apps
(YouTube, BBC, VLC, Chrome, Plex...) are unaffected.

Options if Spotify is your main music source:
- Cast your whole phone screen or tab audio from the Chrome browser, or
- Ask your helper about the "spotifyd bridge" — software that lets Spotify
  reach the speaker indirectly (details in `docs/04`).

## Going further

The `docs/` folder contains the full engineering story and the roadmap for
the community effort: making the buttons and lights work again, synchronized
multi-room playback, and unlocking the microphone (the last big unsolved
challenge). Start with `docs/00-technical-reference.md`, and see
[WK7-reforged](https://github.com/tomkubik/WK7-reforged) for the active
firmware project.
