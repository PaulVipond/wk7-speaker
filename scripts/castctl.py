#!/usr/bin/env python3
"""castctl - control individual Cast speakers (e.g. WK7 rooms).
Usage:
  castctl.py list
  castctl.py play  <room> <url> [content-type]
  castctl.py stop  <room>
  castctl.py vol   <room> <0.0-1.0>
  castctl.py status <room>
Room matching is case-insensitive substring against the device's friendly name.
"""
import sys
import time
import pychromecast


def get_casts():
    r = pychromecast.get_chromecasts()
    return r[0] if isinstance(r, tuple) else r


def find(room):
    room = room.lower()
    for c in get_casts():
        try:
            fn = (c.cast_info.friendly_name or "").lower()
        except Exception:
            fn = ""
        if room in fn:
            c.wait()
            return c
    print(f"No device matching '{room}'. Known:" )
    for c in get_casts():
        try:
            print("  -", c.cast_info.friendly_name)
        except Exception:
            pass
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]

    if cmd == "list":
        for c in get_casts():
            try:
                ci = c.cast_info
                print(f"{ci.friendly_name:30s} {ci.model_name:25s} {ci.host}")
            except Exception:
                pass
        return

    if cmd == "status":
        c = find(sys.argv[2])
        try:
            c.media_controller.block_until_active(8)
        except Exception:
            pass
        s = c.media_controller.status
        print("state:", s.player_state, "| title:", s.title,
              "| time:", round(s.current_time or 0, 1),
              "| vol:", c.status.volume_level if c.status else "?")
        return

    if cmd == "play":
        room, url = sys.argv[2], sys.argv[3]
        ctype = sys.argv[4] if len(sys.argv) > 4 else "audio/mpeg"
        c = find(room)
        title = url.rsplit("/", 1)[-1][:60] or "stream"
        c.play_media(url, ctype, title=title)
        c.media_controller.block_until_active(10)
        time.sleep(2)
        print("PLAYING on", c.cast_info.friendly_name,
              ":", c.media_controller.status.player_state)
        return

    if cmd == "stop":
        c = find(sys.argv[2])
        c.media_controller.stop()
        print("stopped", c.cast_info.friendly_name)
        return

    if cmd == "vol":
        c = find(sys.argv[2])
        c.set_volume(float(sys.argv[3]))
        time.sleep(1)
        print("volume", c.cast_info.friendly_name, "=", c.status.volume_level)
        return

    print(__doc__)


if __name__ == "__main__":
    main()
