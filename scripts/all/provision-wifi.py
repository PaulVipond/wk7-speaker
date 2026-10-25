#!/usr/bin/env python3
"""provision-wifi.py — bring a factory-reset LG WK7 ThinQ speaker back online.

Works on Windows, macOS, and Linux with nothing but Python 3 installed
(no external libraries; the RSA step is implemented natively below).

It exists for one job: teach the speaker your home Wi-Fi again, even though
the LG/Google app that used to do this no longer exists.

WHAT YOU DO:
  1. Power the speaker on and wait for its light show to finish.
  2. Connect THIS computer to the speaker's setup Wi-Fi network.
     It has a name like "LG-WK7_XXXX.n019" and needs no password.
  3. Run:   python3 provision-wifi.py
  4. Answer the questions (your Wi-Fi's name and password).
  5. Wait for "SUCCESS", then reconnect your computer to your home Wi-Fi.
  6. Done — the speaker now appears in any app with a Cast symbol.

QUICK TEST ANY TIME (speaker already set up, computer on home Wi-Fi):
      python3 provision-wifi.py --test
  Finds the speaker on your network and plays a test radio station
  through it. Press Enter to stop.

Your Wi-Fi password is used only to send it to the speaker on your own
network, encrypted, and is never stored or sent anywhere else.

For background and the full technical story, see the repository's README and
docs/01-wifi-provisioning.md.
"""

import base64
import json
import secrets
import socket
import ssl
import sys
import time
import urllib.request
import urllib.error
import getpass
from threading import Thread

TEST_URL = "https://ice1.somafm.com/groovesalad-128-mp3"  # ambient radio, plain mp3

DEFAULT_SPEAKER_IP = "192.168.255.249"  # the speaker's address on its setup network

# ---------------------------------------------------------------------------
# Minimal RSA (public key only, PKCS#1 v1.5 encryption) — pure stdlib.
# ---------------------------------------------------------------------------

def _tlv(data, off):
    """Parse one DER TLV at offset. Returns (tag, value_bytes, next_offset)."""
    tag = data[off]
    off += 1
    ln = data[off]
    off += 1
    if ln & 0x80:
        nbytes = ln & 0x7F
        ln = int.from_bytes(data[off:off + nbytes], "big")
        off += nbytes
    end = off + ln
    return tag, data[off:end], end


def parse_spki_public_key(b64_der):
    """Extract (modulus, exponent) ints from a base64 public key.

    Handles both encodings seen in the wild: a full SubjectPublicKeyInfo
    (SEQUENCE { algorithm, BIT STRING }) and a bare RSAPublicKey
    (SEQUENCE { INTEGER n, INTEGER e }) — the WK7 serves the bare form
    (the original Google Home app patched the SPKI header on by hand).
    """
    der = base64.b64decode(b64_der)
    _, outer, _ = _tlv(der, 0)
    if outer and outer[0] == 0x02:
        # bare RSAPublicKey: SEQUENCE { INTEGER n, INTEGER e }
        _, n_bytes, n_off = _tlv(outer, 0)
        _, e_bytes, _ = _tlv(outer, n_off)
    else:
        # SubjectPublicKeyInfo: SEQUENCE { SEQUENCE (algorithm), BIT STRING }
        _, _, off = _tlv(outer, 0)            # skip algorithm SEQUENCE
        _, keybits, _ = _tlv(outer, off)      # BIT STRING
        # BIT STRING: first byte = number of unused bits (0 here); the rest is
        # SEQUENCE { INTEGER n, INTEGER e }
        _, rsapub, _ = _tlv(keybits, 1)
        _, n_bytes, n_off = _tlv(rsapub, 0)
        _, e_bytes, _ = _tlv(rsapub, n_off)
    # strip possible leading zero of DER INTEGERs
    n_bytes = n_bytes[1:] if n_bytes[0] == 0 else n_bytes
    e_bytes = e_bytes[1:] if e_bytes[0] == 0 else e_bytes
    return int.from_bytes(n_bytes, "big"), int.from_bytes(e_bytes, "big")


def rsa_encrypt_pkcs1(message, n, e):
    """RSAES-PKCS1-v1_5 encryption with the public key (n, e)."""
    k = (n.bit_length() + 7) // 8
    m = message.encode("utf-8")
    if len(m) > k - 11:
        raise ValueError("message too long for this key")
    ps_len = k - len(m) - 3
    # non-zero random padding
    ps = bytearray()
    while len(ps) < ps_len:
        b = secrets.token_bytes(ps_len - len(ps))
        ps.extend(x for x in b if x != 0)
    em = b"\x00\x02" + bytes(ps) + b"\x00" + m
    c = pow(int.from_bytes(em, "big"), e, n)
    return c.to_bytes(k, "big")

# ---------------------------------------------------------------------------
# Finding the speaker on the home network (after the user reconnects)
# ---------------------------------------------------------------------------

def _lan_prefix():
    """Local IPv4 /24 prefix, e.g. '192.168.1' (no packet is actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))  # TEST-NET — never routed
        ip = s.getsockname()[0]
    except Exception:
        ip = "192.168.1"
    finally:
        s.close()
    return ip.rsplit(".", 1)[0]


def find_speaker_on_lan():
    """Scan the local /24 for the WK7 (Cast port 8009 + Eureka name check)."""
    prefix = _lan_prefix()
    hits = []

    def probe(i):
        try:
            sock = socket.create_connection((f"{prefix}.{i}", 8009), timeout=0.8)
            sock.close()
            hits.append(f"{prefix}.{i}")
        except Exception:
            pass

    threads = [Thread(target=probe, args=(i,)) for i in range(1, 255)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for ip in hits:
        try:
            _, info = api(ip, "/setup/eureka_info?options=detail,320")
            if str(info.get("name", "")).startswith("LG-WK7"):
                return ip
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Minimal CastV2 client — stdlib only (hand-rolled protobuf envelope).
# ---------------------------------------------------------------------------

_NS_RECEIVER = "urn:x-cast:com.google.cast.receiver"
_NS_MEDIA = "urn:x-cast:com.google.cast.media"
_NS_CONNECTION = "urn:x-cast:com.google.cast.tp.connection"
_APP_DEFAULT_MEDIA_RECEIVER = "CC1AD845"


def _varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _sfield(field, value):
    v = value.encode("utf-8") if isinstance(value, str) else value
    return _varint((field << 3) | 2) + _varint(len(v)) + v


def _cast_frame(source, dest, namespace, payload):
    """CastMessage protobuf: protocol_version=0, string payload."""
    msg = (b"\x08\x00"                      # field 1 varint 0 (CASTV2_1_0)
           + _sfield(2, source)
           + _sfield(3, dest)
           + _sfield(4, namespace)
           + b"\x28\x00"                    # field 5 varint 0 (STRING payload)
           + _sfield(6, json.dumps(payload)))
    return len(msg).to_bytes(4, "big") + msg


def _parse_frame(data):
    """Return (namespace, payload dict) from one CastMessage protobuf."""
    fields = {}
    off = 0
    while off < len(data):
        tag = 0
        shift = 0
        while True:
            b = data[off]
            off += 1
            tag |= (b & 0x7F) << shift
            shift += 7
            if not (b & 0x80):
                break
        field, wt = tag >> 3, tag & 7
        if wt == 0:
            val = 0
            shift = 0
            while True:
                b = data[off]
                off += 1
                val |= (b & 0x7F) << shift
                shift += 7
                if not (b & 0x80):
                    break
            fields[field] = val
        elif wt == 2:
            ln = 0
            shift = 0
            while True:
                b = data[off]
                off += 1
                ln |= (b & 0x7F) << shift
                shift += 7
                if not (b & 0x80):
                    break
            fields[field] = data[off:off + ln]
            off += ln
    try:
        payload = json.loads(fields.get(6, b"{}").decode("utf-8"))
    except Exception:
        payload = {}
    return fields.get(4, b"").decode("utf-8"), payload


class CastClient:
    """Very small CastV2 client: launch the Default Media Receiver, load a
    stream, stop it again. Just enough for the post-setup test."""

    def __init__(self, ip):
        self.src = "sender-wk7tool"
        self.req = 0
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        raw = socket.create_connection((ip, 8009), timeout=5)
        self.sock = ctx.wrap_socket(raw)
        self.sock.settimeout(10)
        # CastV2 requires a CONNECT handshake before anything else,
        # otherwise the receiver answers {"type":"CLOSE"} immediately.
        self._send("receiver-0", _NS_CONNECTION, {"type": "CONNECT", "userAgent": "wk7-setup-tool"})

    def _send(self, dest, ns, payload):
        self.req += 1
        payload.setdefault("requestId", self.req)
        self.sock.sendall(_cast_frame(self.src, dest, ns, payload))

    def _recv_until(self, match, timeout=15):
        """Read frames until match(namespace, payload) is truthy; return it."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                self.sock.settimeout(max(0.5, deadline - time.time()))
                hdr = b""
                while len(hdr) < 4:
                    chunk = self.sock.recv(4 - len(hdr))
                    if not chunk:
                        return None
                    hdr += chunk
                ln = int.from_bytes(hdr, "big")
                body = b""
                while len(body) < ln:
                    chunk = self.sock.recv(ln - len(body))
                    if not chunk:
                        return None
                    body += chunk
            except socket.timeout:
                return None
            ns, payload = _parse_frame(body)
            got = match(ns, payload)
            if got:  # matchers must return a truthy value (dict / state str)
                return got
        return None

    def launch_and_load(self, url, content_type="audio/mpeg"):
        def _app_from(p):
            return next((a for a in p.get("status", {})
                         .get("applications", [])
                         if a.get("appId") == _APP_DEFAULT_MEDIA_RECEIVER),
                        None)

        # 1) see whether the Default Media Receiver is already running
        self._send("receiver-0", _NS_RECEIVER, {"type": "GET_STATUS"})
        app = self._recv_until(
            lambda ns, p: (p.get("type") == "RECEIVER_STATUS"
                           and (_app_from(p) or None)),
            timeout=8)
        # only LAUNCH if it wasn't running — sending LAUNCH while it runs
        # kills the existing session and invalidates our transportId.
        if not app:
            self._send("receiver-0", _NS_RECEIVER,
                       {"type": "LAUNCH", "appId": _APP_DEFAULT_MEDIA_RECEIVER})
            app = self._recv_until(
                lambda ns, p: (p.get("type") == "RECEIVER_STATUS"
                               and (_app_from(p) or None)),
                timeout=20)
        if not app:
            return False
        session_id, transport_id = app["sessionId"], app["transportId"]

        # 2) load the stream into the app
        self._send(transport_id, _NS_CONNECTION, {"type": "CONNECT",
                                                  "userAgent": "wk7-setup-tool"})
        self._send(transport_id, _NS_MEDIA,
                   {"type": "LOAD", "sessionId": session_id,
                    "transportId": transport_id,
                    "media": {"contentId": url, "streamType": "BUFFERED",
                              "contentType": content_type},
                    "autoplay": True, "current_time": 0})
        state = self._recv_until(
            lambda ns, p: (p.get("type") == "MEDIA_STATUS"
                           and (p.get("status") or [{}])[0].get("playerState")),
            timeout=25)
        if isinstance(state, str):
            return state in ("PLAYING", "BUFFERING", "IDLE", "LOADING")
        return False

    def stop_app(self):
        self._send("receiver-0", _NS_RECEIVER, {"type": "STOP"})
        return True

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


def run_playback_test(speaker_ip):
    """Play the test stream on the speaker.
    Returns a CastClient on success (caller stops it via stop_playback),
    or None on failure."""
    try:
        cc = CastClient(speaker_ip)
    except Exception:
        return None
    try:
        if cc.launch_and_load(TEST_URL):
            return cc
    except Exception:
        pass
    cc.close()
    return None


def stop_playback(cc):
    try:
        cc.stop_app()
    finally:
        cc.close()


# ---------------------------------------------------------------------------
# Talking to the speaker (setup API)
# ---------------------------------------------------------------------------

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE  # the speaker uses a self-signed certificate


def api(ip, path, method="GET", body=None):
    url = f"https://{ip}:8443{path}"
    data = None
    headers = {}
    if body is not None:
        data = body.encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, context=_ssl_ctx, timeout=10) as r:
        raw = r.read()
    return r.status, (json.loads(raw) if raw else {})


def play_test_20s(ip, seconds=20):
    """Play the test stream for `seconds`, then stop it with the reliable
    receiver-level stop (a plain media-stop can miss orphaned streams).
    Returns True if the stream started."""
    print(f"Playing a test radio station through the speaker for {seconds} seconds...")
    cc = run_playback_test(ip)
    if not cc:
        return False
    for remaining in range(seconds, 0, -5):
        print(f"  ...{remaining}s")
        time.sleep(min(5, remaining))
    stop_playback(cc)   # receiver-level STOP — the reliable method
    print("Stopped.")
    return True


def quick_test():
    """Standalone mode: find the speaker on the home network and play the
    test stream. Returns exit code."""
    print("=== LG WK7 speaker quick test ===")
    print()
    print("Looking for the speaker on your network (a few seconds)...")
    ip = None
    for _ in range(6):
        ip = find_speaker_on_lan()
        if ip:
            break
        time.sleep(5)
    if not ip:
        print("No LG WK7 found on this network. Check this computer is on")
        print("your home Wi-Fi and the speaker is powered on.")
        return 1
    print(f"Found the speaker at {ip}.")
    ok = play_test_20s(ip)
    if not ok:
        print("The speaker responded but the test stream didn't start.")
        return 1
    print("The speaker is working.")
    return 0


def main():
    if "--test" in sys.argv:
        return quick_test()
    print("=== LG WK7 speaker setup ===")
    print()
    print("Step 1: connect this computer's Wi-Fi to the speaker's setup network")
    print('        (a network named like "LG-WK7_XXXX.n019", open, no password).')
    ip = input(f"Step 2: press Enter to check for the speaker "
               f"[default {DEFAULT_SPEAKER_IP}] ").strip() or DEFAULT_SPEAKER_IP

    try:
        status, info = api(ip, "/setup/eureka_info?options=detail,320")
    except Exception as ex:
        print()
        print(f"Could not reach the speaker at {ip}: {ex}")
        print()
        print("Most likely causes:")
        print('  - This computer is not connected to the "LG-WK7..." setup network.')
        print("    Check your Wi-Fi settings, reconnect, and run this again.")
        print("  - The speaker stopped broadcasting. Power it off and on, wait for")
        print("    the light show to finish, reconnect to its network, retry.")
        return 1

    name = info.get("name", "?")
    model = info.get("detail", {}).get("model_name", "unknown model")
    print(f"Found: {name} ({model})")
    lan_ip = None  # speaker's home-network address, once known

    ssid = input("Step 3: your home Wi-Fi name (2.4 GHz network): ").strip()
    if not ssid:
        print("No Wi-Fi name given — cancelling. Nothing was changed.")
        return 1
    psk = getpass.getpass("Step 4: your home Wi-Fi password (input is hidden): ")
    if not psk:
        print("No password given — cancelling. Nothing was changed.")
        return 1

    pub_b64 = info.get("public_key")
    if not pub_b64:
        print("The speaker did not provide its public key. Cancelling.")
        return 1
    n, e = parse_spki_public_key(pub_b64)
    enc = base64.b64encode(rsa_encrypt_pkcs1(psk, n, e)).decode("ascii")

    # Exact schema recovered from the original Google Home app — do not
    # "fix" field names or remove wpa_id/scan_ssid; the server is strict.
    body = json.dumps({
        "ssid": ssid,
        "wpa_auth": 7,      # WPA2-PSK
        "wpa_cipher": 4,    # CCMP
        "wpa_id": 0,
        "scan_ssid": 0,     # set to 1 for hidden networks
        "enc_passwd": enc,
    })

    print()
    print("Step 5: sending Wi-Fi settings to the speaker...")
    try:
        status, _ = api(ip, "/setup/connect_wifi", "POST", body)
    except urllib.error.HTTPError as ex:
        print(f"The speaker rejected the request (HTTP {ex.code}).")
        print("Double-check the Wi-Fi name and password, then run this again.")
        return 1
    if status != 200:
        print(f"The speaker rejected the request (HTTP {status}).")
        return 1

    print("Connecting... (up to 2 minutes)")
    connected = False
    for _ in range(40):
        import time
        time.sleep(3)
        try:
            _, st = api(ip, "/setup/eureka_info")
            if st.get("connected") and st.get("ssid") == ssid:
                connected = True
                break
        except Exception:
            pass  # the setup network may blip while it associates
    if not connected:
        print()
        print("The speaker did not confirm joining your Wi-Fi.")
        print("Check the Wi-Fi name/password and run this again.")
        return 1

    print("Step 6: saving the settings so they survive power cuts...")
    # The speaker's setup network can blip while it finalizes the join, so
    # retry the save and then verify against the device's actual state.
    saved = False
    for attempt in range(3):
        try:
            status, _ = api(ip, "/setup/save_wifi", "POST", "")
            if status == 200:
                saved = True
                break
        except Exception:
            pass  # network blip — the request may still have gone through
        try:
            _, st = api(ip, "/setup/eureka_info")
            if st.get("wpa_configured"):
                saved = True   # an earlier attempt already did it
                break
        except Exception:
            pass
        print("  (retrying the save step...)")
        import time
        time.sleep(5)
    if not saved:
        # The common case: the speaker drops its setup network during the
        # join, so the save can't be CONFIRMED over it even when it
        # succeeded. The speaker is now reachable over the home network —
        # confirm (or finish) the save there.
        print()
        print("The speaker switched to your home Wi-Fi while saving, so this")
        print("tool lost contact through the setup network. Reconnect this")
        print("computer to your home Wi-Fi, then press Enter to finish the")
        print("check over the home network...")
        try:
            input()
        except EOFError:
            pass
        print("Looking for the speaker on your home network (a few seconds)...")
        for _ in range(6):
            lan_ip = find_speaker_on_lan()
            if lan_ip:
                break
            time.sleep(5)
        if lan_ip:
            _, st = api(lan_ip, "/setup/eureka_info")
            if st.get("wpa_configured"):
                saved = True
            else:
                try:
                    status, _ = api(lan_ip, "/setup/save_wifi", "POST", "")
                    if status == 200:
                        saved = True
                except Exception:
                    pass

    print()
    print("=" * 60)
    if saved:
        print("SUCCESS!")
        print()
        # Offer the built-in playback test (also verifies everything
        # end-to-end from the home network, like a normal sender app).
        if lan_ip:
            prompt = ("Want to hear it working right away? Press Enter "
                      "(or type n to skip)... ")
        else:
            prompt = ("Want to hear it working right away? First reconnect\n"
                       "this computer to your home Wi-Fi, then press Enter "
                       "(or type n to skip)... ")
        try:
            ans = input(prompt).strip().lower()
        except EOFError:
            ans = "n"
        if ans != "n" and ans != "no":
            ip2 = lan_ip or find_speaker_on_lan()
            if not ip2:
                print("Couldn't find the speaker on your network yet — give it")
                print("a minute, or check this computer is on your home Wi-Fi.")
                print("You can also just test from your phone: open any app")
                print("with a Cast symbol and the speaker will be listed.")
            else:
                print(f"Found the speaker at {ip2}.")
                if play_test_20s(ip2):
                    print("Everything works — the speaker is set up.")
                else:
                    print("The speaker responded but the test stream didn't")
                    print("start. It may still work fine from your phone apps —")
                    print("try the Cast symbol in YouTube or BBC Sounds.")
        print()
        print('From your phone: connect it to the same Wi-Fi, open any app')
        print('with a Cast symbol, tap it, and the speaker appears')
        print(f'(named "{name}").')
        print()
        print("  If apps don't show it, toggle the phone's Wi-Fi off and on.")
    else:
        print("Connected, but the save step was not confirmed. The speaker")
        print("may forget the Wi-Fi after a power cut — if so, simply run")
        print("this tool again after the speaker restarts.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nCancelled. Nothing was changed.")
        sys.exit(1)
