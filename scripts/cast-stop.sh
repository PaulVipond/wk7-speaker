#!/usr/bin/env python3
import time
import pychromecast

r = pychromecast.get_chromecasts()
casts = r[0] if isinstance(r, tuple) else r
target = None
for c in casts:
    try:
        if "WK7" in (c.cast_info.friendly_name or ""):
            target = c
            break
    except Exception:
        pass
target.wait()
print("quitting receiver app on", target.cast_info.friendly_name)
target.quit_app()
time.sleep(3)
# belt and braces: also stop any media session
try:
    target.media_controller.block_until_active(3)
except Exception:
    pass
try:
    target.media_controller.stop()
except Exception as e:
    print("media stop:", e)
time.sleep(2)
print("app status now:", target.status.status_text if target.status else "?")
print("media state:", target.media_controller.status.player_state)
