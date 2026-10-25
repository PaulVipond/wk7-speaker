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

Your Wi-Fi password is used only to send it to the speaker on your own
network, encrypted, and is never stored or sent anywhere else.

For background and the full technical story, see the repository's README and
docs/01-wifi-provisioning.md.
"""

import base64
import json
import secrets
import ssl
import sys
import urllib.request
import urllib.error
import getpass

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
# Talking to the speaker
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


def main():
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
    try:
        status, resp = api(ip, "/setup/save_wifi", "POST", "")
    except Exception:
        status, resp = 0, None
    saved = status == 200

    print()
    print("=" * 60)
    if saved:
        print("SUCCESS!")
        print()
        print('  1. Reconnect this computer to your home Wi-Fi.')
        print("  2. Connect your phone to the same Wi-Fi.")
        print("  3. Open any app with a Cast symbol, tap it, and the speaker")
        print(f"     appears (named \"{name}\").")
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
