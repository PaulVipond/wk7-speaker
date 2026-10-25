#!/usr/bin/env python3
"""micom-sniff.py — MICOM UART tap for the LG WK7.

Sniff mode (passive, zero risk):
    micom-sniff.py sniff /dev/ttyUSB0
Send mode (injection, after you know what you're doing):
    micom-sniff.py send /dev/ttyUSB0 CMD1 CMD2 [HEXDATA...]
    e.g. micom-sniff.py send /dev/ttyUSB0 C2 00 01

Protocol (from WK7-reforged .../wk7-probe/MICOM_PROTOCOL.md):
  frame: E5 TID CMD1 CMD2 CKSUM LEN DATA...
  checksum (host->MICOM): (E5 + TID + CMD1 + CMD2 + LEN + sum(DATA)) & 0xFF
  checksum (reply): sum of all bytes except byte 4
  reply: TID = req TID | 0x80, DATA[0] = 0x80 OK / 0xFF error

NEVER send D9 (MCU reset) or F0 (touch fw update).

Decodes live, flags 0xC2 (USB switch) traffic, logs raw bytes with timestamps
to micom_raw_TIMESTAMP.log next to stdout.
"""
import sys
import time
import serial

CMDS = {
    (0xA1, 0x00): "sync/handshake",
    (0xB0, 0x00): "key poll",
    (0xC0, 0xFD): "LED ring (no reply)",
    (0xC0, 0xFE): "LED ring (reply)",
    (0xC1, 0xFF): "function LED scenario",
    (0xC2, 0x00): "USB SWITCH",      # the interesting one
    (0xD9, 0x00): "MCU RESET (avoid)",
    (0xE0, 0x80): "MCU version",
    (0xE0, 0x81): "touch version",
    (0xE0, 0x90): "MCU LED info",
    (0xF0, None): "touch fw update (avoid)",
}


def cs_frame(tid, c1, c2, data):
    ln = len(data)
    ck = (0xE5 + tid + c1 + c2 + ln + sum(data)) & 0xFF
    return bytes([0xE5, tid, c1, c2, ck, ln] + list(data))


def name(c1, c2):
    return CMDS.get((c1, c2)) or CMDS.get((c1, None)) or ""


def sniff(port):
    raw_log = open(f"micom_raw_{time.strftime('%Y%m%d_%H%M%S')}.log", "wb")
    ser = serial.Serial(port, 115200, timeout=0.05)
    buf = bytearray()
    print(f"[*] sniffing {port} at 115200 8N1 — Ctrl-C to stop")
    print("[*] waiting for UART traffic; key polls arrive every ~30 ms if wired right")
    while True:
        chunk = ser.read(256)
        if chunk:
            raw_log.write(chunk)
            raw_log.flush()
            buf.extend(chunk)
            # parse frames out of the buffer
            while len(buf) >= 6:
                # resync on guide code
                if buf[0] != 0xE5:
                    buf.pop(0)
                    continue
                tid, c1, c2 = buf[1], buf[2], buf[3]
                ln = buf[5]
                if len(buf) < 6 + ln:
                    break
                data = bytes(buf[6:6 + ln])
                frame = bytes(buf[:6 + ln])
                reply = bool(tid & 0x80)
                # reply checksum: sum of all bytes except byte 4
                exp_ck = (sum(frame) - frame[4]) & 0xFF
                tag = "REPLY" if reply else "CMD"
                ok = "OK" if exp_ck == frame[4] else f"BADCK({exp_ck:02x})"
                label = name(c1, c2)
                print(f"[{time.strftime('%H:%M:%S')}.{int(time.time()*1000)%1000:03d}] "
                      f"{tag} TID={tid & 0x7F:02x} {c1:02x} {c2:02x} "
                      f"{' '.join(f'{b:02x}' for b in data)}  {ok}  {label}")
                if c1 == 0xC2:
                    print("    >>> USB SWITCH TRAFFIC — note the state byte "
                          f"(data[0]=0x{data[0]:02x} if present) <<<")
                del buf[:6 + ln]


def send(port, c1s, c2s, data_hex):
    ser = serial.Serial(port, 115200, timeout=0.5)
    tid = 0x40  # mid-range TID to reduce collision with LG app IDs
    c1, c2 = int(c1s, 16), int(c2s, 16)
    if (c1, c2) in ((0xD9, 0x00),) or c1 == 0xF0:
        print("refusing to send dangerous command")
        return 1
    data = bytes(int(x, 16) for x in data_hex)
    frame = cs_frame(tid, c1, c2, data)
    print("TX:", " ".join(f"{b:02x}" for b in frame))
    ser.write(frame)
    t0 = time.time()
    resp = ser.read(32)
    if resp:
        print("RX:", " ".join(f"{b:02x}" for b in resp))
        if len(resp) >= 7 and resp[0] == 0xE5:
            st = resp[6]
            print("status:", "0x80 OK" if st == 0x80 else f"0x{st:02x} (error?)")
    else:
        print("no reply within 500 ms (collision or MICOM busy — retry)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("sniff", "send"):
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] == "sniff":
        sniff(sys.argv[2])
    else:
        sys.exit(send(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:]))
