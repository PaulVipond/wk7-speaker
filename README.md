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
   Wi-Fi when it asks, press Enter, and music plays from the speaker. Press
   Enter again to stop it.
7. After that, connect your phone to the same Wi-Fi, open any app with a
   Cast symbol, tap it, and the speaker appears (named like "LG-WK7_XXXX").
   Pick it, press play, and music plays.

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

The `docs/` folder contains a technical overview and a potential roadmap for restoring function: making the buttons and lights work again, synchronized
multi-room playback, and unlocking the microphone (the last big unsolved
challenge). Start with `docs/00-technical-reference.md`, and see
[WK7-reforged](https://github.com/tomkubik/WK7-reforged) for the active
firmware project.
