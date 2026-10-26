# USB Port & Microphone Unlock — The MICOM Plan

The two remaining locked capabilities (USB service port, microphone) share one
gatekeeper: the **MICOM microcontroller** — the square TQFP on the mainboard.
The community repo has already decompiled its UART protocol
(`WK7-reforged/WK7-software-for-unlocked-bootloader/wk7-probe/MICOM_PROTOCOL.md`).
This document is the practical plan for using it on a retail unit.

## Background

- The Qualcomm SoC has ONE USB controller. The MICOM muxes it between the
  internal Wi-Fi/BT module (QCA9377) and the external micro-USB service port.
- LG's boot code watches for a USB host handshake for ~38–60 s after boot;
  with no host (or no data lines — a charge-only cable), it keeps the mux on
  Wi-Fi. This matches the observed total silence in dmesg.
- Retail units appear not to expose ADB over USB even with good cables
  (repo issue #4: two owners, known-good cables, every port, Win+Mac — both
  failed; one gave up). The author's device was a developer prototype with
  `ro.sys.usb.default.config = diag,adb`.
- The MICOM's own firmware image is named `M17111305_DV_USB_Mode.hex` — LG
  service used a USB mode, so an activation trigger exists.
- **The protocol has a documented command `0xC2` (USB switch control)** with a
  state byte — the mux is commandable. The state values are the one unknown
  ("still need to be read from the caller code" per the repo).

## The MICOM UART protocol (from MICOM_PROTOCOL.md)

Link: 115200 baud, 8N1. On the SoC side it is `/dev/ttyHSL1` (UART2); our access
is the physical MICOM pads. GPIOs GPIO_22/66/67 nearby (roles unconfirmed).

Frame (host → MICOM):

| Byte | Field |
|---|---|
| 0 | guide code `0xE5` |
| 1 | transaction ID (1..127, increments, wraps to 1) |
| 2 | CMD1 |
| 3 | CMD2 |
| 4 | checksum = (0xE5 + TID + CMD1 + CMD2 + LEN + sum(DATA)) & 0xFF |
| 5 | LEN (max 12) |
| 6.. | DATA |

Reply: same header, TID = request TID | 0x80, checksum = sum of all bytes
except byte 4, DATA[0] = status (0x80 OK, 0xFF error). Read timeout 500 ms.

Key commands: 0xA1/00 sync (`AA`), 0xB0/00 poll keys (LG polls every 30 ms),
0xC0/FD+FE LED ring colours, 0xC1/FF function LED scenario, **0xC2/00 USB
switch (state byte)**, 0xD9/00 MCU reset (AVOID), 0xE0/80 MCU version,
0xE0/81 touch controller version, 0xF0/xx touch firmware update (AVOID).

Key codes seen on the wire: 01 play/pause, 02 hotword, 03/04 vol±, 05 function,
06 mic mute, 07 factory reset, 08/09 skip, 0x11 play/pause long-press;
hidden/service: **0x83, 0x85, 0x91** — likely the interesting ones.

## Equipment

- Phillips screwdriver (bottom rubber ring off, 4 screws).
- USB-UART adapter (CP2102 / FT232 / CH340, a few pounds), 3.3 V logic.
- Optional: logic analyzer for clean traces; a plain UART tap suffices.
- A USB data cable (already on order) for the experiments that follow.

## Phase 1 — Find the MICOM UART pads (multimeter work)

1. Open the speaker (bottom rubber, 4 screws; document each step with photos
   for this folder).
2. Locate the MICOM: the square TQFP near the interface board (the protocol
   doc says it's the square chip; the author's photos in
   WK7-reforged/web-assets may help identify it).
3. Find its UART lines. Approaches in order:
   a. Test pads labelled/clustered near the MICOM; UART RX/TX/GND usually
      appear together.
   b. With the speaker running, touch the scope/adapter to candidate pads and
      look for 115200 traffic — the SoC polls keys every 30 ms, so the RX/TX
      lines are ALIVE with data. This is the fastest identification method:
      any pad with periodic short bursts is a UART line.
   c. Continuity from the SoC's UART2/BLSP pins (0x78AF000 region) if the
      board has SoC test pads — harder.
4. Wire: adapter RX → MICOM-TX-line (SoC TX), adapter TX → observe only in
   sniff phase; adapter GND → speaker GND. DO NOT power the adapter from the
   speaker for phase 1.

Safety: the tap is passive in phase 1 — zero risk to the speaker.

## Phase 2 — Boot-time sniffing (answers "what combination activates it")

Capture the UART during boot in these scenarios, logging raw bytes with
timestamps:

| Run | Cable in service port | Held at power-on | Question it answers | Result (2026-10-25, this unit) |
|---|---|---|---|---|
| A | no | — | baseline: does boot ever send 0xC2? | (UART tap not yet wired — pending) |
| B | yes (to laptop, lsusb/udevadm monitor running) | — | does LG's code flip the mux when a host is present? | **NEGATIVE — zero USB events across full boot; the handshake window never begins** |
| C | yes | play/pause (short hold, factory-reset avoided) | does a long-press route USB? | **NEGATIVE** |
| D | yes | mic mute | service combo? | **NEGATIVE** |
| E | yes | vol− | service combo? | **NEGATIVE** |
| F | yes | each in turn: other buttons | catch hidden key codes 0x83/0x85/0x91 | (pending) |

Field-test conclusion (runs B–E): the retail firmware never enumerates the
USB port in DEVICE mode under any externally-triggerable boot condition.
Watcher methodology: `udevadm monitor --kernel --subsystem-match=usb`
(as a normal user — more reliable than watching dmesg scroll), validated by
plugging a known device mid-run; a validated watcher would have caught even
a one-second enumeration blink. This matches the two independent failures
in the WK7-reforged repo's issue #4. **Reframed after the Google Home
findings below: these tests all used a plug-to-plug cable, which leaves the
USB ID pin floating — host-mode ports may never come up without an
OTG-style (ID-grounded) plug. Device mode is inert; HOST mode is untested.**

### Cross-platform clue: the Google Home service port (2026-10-25)

Two 2017 r/googlehome threads about the original Google Home (Marvell
Berlin SoC — different silicon, sibling Cast-era platform) documented:

- The service port works as a USB **HOST** port: the official Chromecast
  Ultra Ethernet adapter plugged into it gives the device wired networking
  instantly. A non-powered adapter failed — the port supplies very little
  power, so bus-powered peripherals need a powered hub.
- A hidden **bootloader USB mode** exists there: holding MUTE while
  applying power (cable pre-attached) enumerates the device for a few
  seconds ("BG2CD") before parking in the bootloader with dim LEDs. The
  enumeration blink is so short people needed several attempts to read it.
- (Historical: the original Chromecast was rooted via the USB "HubCap"
  exploit, fail0verflow 2014 — the ancestor of USB-port attack research on
  this family.)

Implications for the WK7:

1. **ID-pin theory (primary)**: a micro-B host port decides to host via the
   ID pin, grounded only by OTG-style plugs. A plain cable to a laptop
   (ID floating) may never trigger the MICOM's mux at all — consistent
   with runs B–E showing zero electrical activity. The decisive test is an
   OTG adapter.
2. The `eureka_info` API has shown an `ethernet_connected` field (always
   false so far) in every dump — this platform explicitly contemplates
   USB-Ethernet, exactly as the Google Home supported.
3. Observable mux-switch tell: on the Google Home, plugging into the port
   disabled the capacitive top controls. On the WK7, a mux switch may
   visibly change button/LED behavior — watch for it during the tests.

### New experiments (host-mode matrix)

| Run | Plug | Peripheral | Watch |
|---|---|---|---|
| G | micro-USB **OTG adapter** (ID-grounded) | none (adapter only) | LED/button behavior change; eureka_info |
| H | OTG adapter | USB flash drive (self-powered not needed) | eureka_info; any LED change |
| I | OTG adapter + **powered USB hub** | USB-Ethernet dongle (RTL8152/ASIX) | **eureka_info `ethernet_connected`** — the jackpot |
| J | OTG adapter + powered hub | USB-UART bridge (CP2102) wired for the MICOM pads | n/a — this is doc 03 phase 2 anyway |

**Host-mode results (2026-10-26, all with a verified-good chain):**

Peripheral chain verified independently of the speaker: genuine RTL8152
dongle (lsusb `0bda:8152` — the chip whose `r8152` driver predates the 3.10
kernel), powered hub (5V/3A), dongle link tested end-to-end on a Linux
laptop (driver bound, carrier up) before the speaker runs.

| Run | Condition | Result |
|---|---|---|
| G | OTG hot-plug into running speaker | **NEGATIVE** — no LED/button reaction, no eureka change |
| I | Full chain present at power-on, fresh boot watched | **NEGATIVE** — normal LED boot sequence, `ethernet_connected` false at fresh uptime |

Interpretation: with the one remaining caveat that the OTG adapter's ID
grounding is unverified (no multimeter at test time), the ID-pin theory is
dead on this hardware if the adapter is genuine. Unlike the Google Home
(hardware ID detection on Marvell), the WK7's USB mux is **MICOM-commanded
(`0xC2`)** — and the retail firmware never sends the command under any
tested condition. USB externally is closed; **the MICOM UART is the path**.
A £5 multimeter beep test on the adapter would close the final caveat, and
a multimeter is required for the UART pad-hunt anyway (Phase 1).

Note: when interpreting "seeing the dongle on the network" — a hub-powered
dongle links to the router on its own; a new wired client in the router's
list is NOT evidence of USB adoption by the speaker. Only the speaker's own
`ethernet_connected` field (or visible behavior change) counts.

Expected outcomes: in run A we likely see the boot-time `0xC2` frames with the
"keep on Wi-Fi" state value; in run B (if the handshake logic is intact) the
alternate state value — which is the answer we need. If B never flips, the
retail boot script may have dropped the host-detection entirely, and run C-F
look for a service-mode trigger instead. Any captured 0x83/0x85/0x91 key code
is new knowledge for the community repo.

Capture tool: `scripts/micom-sniff.py` (included) — decodes frames live and
flags 0xC2 traffic. Raw log saved alongside.

## Phase 3 — Injection (the actual unlock attempt)

With cable attached and laptop watching `lsusb`/`dmesg -w`:

1. Handshake: send 0xA1/00 with `AA`, expect status 0x80 reply.
2. Send `0xC2/00` with the "external" state byte captured in phase 2
   (if unknown, try 0x00 and 0x01 — observable effect on lsusb makes the
   correct value self-evident).
3. Watch the laptop: any new USB enumeration is a win:
   - `05c6:901d` — adbd! Proceed to `adb devices`, `adb shell`,
     `getprop ro.boot.verifiedbootstate`, `getprop ro.build.type`.
   - `05c6:9008` — SoC in EDL mode (different path; flashing blocked without
     LG-signed firehose, but enumeration confirms the mux switched).
   - other `05c6:*` — diag/other function; report to the repo (new knowledge).
   - nothing — mux switched but SoC USB config inert; that itself tells us the
     retail USB config, and the mic work continues via UART anyway.
4. Collisions with LG's app polls: the SoC polls keys every 30 ms. Injected
   frames with our own TID range may interleave fine; if replies are garbled,
   stop LG's app first... which requires a shell — if we could, we'd already be
   done. In practice the 30 ms polls leave ample gap; retry on checksum errors.

Frame builder included in `scripts/micom-sniff.py` (send mode).

## Phase 4 — With a shell: microphone

Once any shell exists (USB adb from phase 3, or the Reforged install later):

1. `cat /proc/asound/pcm` — enumerate capture (MultiMedia3/4-class) routes.
2. `arecord -D ... -f S16_LE -r 16000 -c 1` experiments; check level with
   aplay on the laptop. The far-field array + ADSP beamforming blobs may
   need mixer settings (`tinymix`) — expect archaeology, per the repo's
   mixer_paths.xml notes.
3. Then voice control via Home Assistant: run wyoming-satellite in the
   Reforged Alpine chroot streaming PCM to HA Assist (Whisper STT +
   openWakeWord + Piper TTS). Push-to-talk first (MICOM buttons work), then
   hands-free if echo cancellation is workable. See doc 04.

## Contribute back

Every byte captured in phase 2 is new knowledge for tomkubik/WK7-reforged —
his MICOM_PROTOCOL.md explicitly lists the 0xC2 state values as an open
question, and issue #4 shows other retail owners stuck exactly here. Post
findings as a comment there (offer the logs + state values, not LG code).
