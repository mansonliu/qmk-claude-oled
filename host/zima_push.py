#!/usr/bin/env python3
"""Push Claude Code state to the splitkb Zima OLED over QMK Raw HID.

Usage:
  zima_push.py model "Fable 5"          # set model name line
  zima_push.py status working           # idle|working|waiting|error
  zima_push.py usage 62 41              # set 5h/7d usage; 255 = unknown
  zima_push.py client codex              # claude|codex animation identity
  zima_push.py animation                 # push host-side Codex animation settings
  zima_push.py info "~/git/foo"         # set info line
  zima_push.py statusline               # Claude Code statusline mode:
                                        #   reads statusline JSON on stdin,
                                        #   pushes model+info, prints text

All pushes are best-effort: if the keyboard is unplugged the script exits 0
silently so statusline/hooks never break.
"""
import json
import os
import re
import sys

# Zima: current QMK VID is 0x8D1D, older builds shipped 0xFEED. PID is stable.
VIDS = (0x8D1D, 0xFEED)
PID = 0xF75B
RAW_USAGE_PAGE = 0xFF60
RAW_USAGE = 0x61
REPORT_LEN = 32

# Messages ride alongside the VIA/Vial protocol: byte 0 is a magic command id
# VIA doesn't use, which the firmware handles in raw_hid_receive_kb().
CLAUDE_MAGIC = 0x63

CMD_MODEL = 0x01
CMD_STATUS = 0x02
CMD_INFO = 0x03
CMD_USAGE = 0x04  # payload: five-hour %, seven-day % (0-100, 255 = unknown)
CMD_CLIENT = 0x05
CMD_ANIMATION = 0x06

STATUS_CODES = {"idle": 0, "working": 1, "waiting": 2, "error": 3}
CLIENT_CODES = {"claude": 0, "codex": 1}

# Codex animation parameters live here on the host. After the supporting
# firmware is installed once, changing these values does not require flashing.
CODEX_ANIMATION = {
    "left_x": 5,
    "right_x": 25,
    "top_page": 4,
    "bottom_page": 11,
    "horizontal_segments": 4,
    "dot_count": 4,
    "dot_spacing": 1,
    "frame_ms": 120,
    "dot_width": 4,
    "dot_bits": 0x3C,
}


def find_device():
    import hid

    for info in hid.enumerate():
        if (
            info["product_id"] == PID
            and info["vendor_id"] in VIDS
            and info["usage_page"] == RAW_USAGE_PAGE
            and info["usage"] == RAW_USAGE
        ):
            dev = hid.Device(path=info["path"])
            return dev
    return None


def send(reports):
    """reports: list of (cmd, payload-bytes). Silently no-op without device."""
    try:
        dev = find_device()
        if dev is None:
            return False
        try:
            for cmd, payload in reports:
                data = bytes([CLAUDE_MAGIC, cmd]) + payload[: REPORT_LEN - 2]
                data = data.ljust(REPORT_LEN, b"\x00")
                dev.write(b"\x00" + data)  # leading report ID
        finally:
            dev.close()
        return True
    except Exception:
        return False


def text_payload(s):
    # OLED text line: 21 visible columns, ASCII only (QMK font).
    s = s.encode("ascii", "replace")[:21]
    return s + b"\x00"


def animation_payload(values=None):
    """Encode Codex orbit settings; optional values are the ten CLI fields."""
    if values:
        if len(values) != 10:
            raise ValueError("animation needs 10 values")
        parsed = [int(value, 0) for value in values]
        config = dict(zip(CODEX_ANIMATION, parsed))
    else:
        config = CODEX_ANIMATION

    frame_ms = config["frame_ms"]
    encoded = [
        config["left_x"],
        config["right_x"],
        config["top_page"],
        config["bottom_page"],
        config["horizontal_segments"],
        config["dot_count"],
        config["dot_spacing"],
        (frame_ms + 5) // 10,
        config["dot_width"],
        config["dot_bits"],
    ]
    if any(value < 0 or value > 255 for value in encoded):
        raise ValueError("animation values must encode as bytes")
    if not 30 <= frame_ms <= 2550:
        raise ValueError("frame_ms must be 30..2550")
    return bytes(encoded)


def strip_version(name):
    # OLED shows the model family only: "Fable 5" -> "Fable",
    # "Opus 4.8" -> "Opus". Trailing parentheticals go too.
    name = re.sub(r"\s*\(.*\)$", "", name)
    words = name.split()
    while len(words) > 1 and re.fullmatch(r"[\d.]+", words[-1]):
        words.pop()
    return " ".join(words) or name


def shorten_dir(path, home):
    if home and path.startswith(home):
        path = "~" + path[len(home):]
    if len(path) > 21:
        path = "..." + path[-18:]
    return path


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2

    mode = sys.argv[1]

    if mode == "model":
        send([(CMD_MODEL, text_payload(sys.argv[2]))])
    elif mode == "status":
        code = STATUS_CODES.get(sys.argv[2])
        if code is None:
            print(f"unknown status: {sys.argv[2]}", file=sys.stderr)
            return 2
        send([(CMD_STATUS, bytes([code]))])
    elif mode == "info":
        send([(CMD_INFO, text_payload(sys.argv[2]))])
    elif mode == "notification":
        # Claude Code Notification hook: only real action-needed notifications
        # (permission request / question) should trigger WAITING. The 60s-idle
        # "waiting for your input" nag is just an idle conversation — ignore.
        try:
            data = json.load(sys.stdin)
        except Exception:
            return 0
        msg = (data.get("message") or "").lower()
        if "waiting for your input" in msg:
            return 0
        send([(CMD_STATUS, bytes([STATUS_CODES["waiting"]]))])
    elif mode == "usage":
        def clamp(s):
            value = int(s)
            return 255 if value == 255 else max(0, min(100, value))
        send([(CMD_USAGE, bytes([clamp(sys.argv[2]), clamp(sys.argv[3])]))])
    elif mode == "client":
        code = CLIENT_CODES.get(sys.argv[2])
        if code is None:
            print(f"unknown client: {sys.argv[2]}", file=sys.stderr)
            return 2
        send([(CMD_CLIENT, bytes([code]))])
    elif mode == "animation":
        try:
            payload = animation_payload(sys.argv[2:])
        except (TypeError, ValueError) as error:
            print(f"invalid animation: {error}", file=sys.stderr)
            return 2
        send([(CMD_ANIMATION, payload)])
    elif mode == "statusline":
        try:
            data = json.load(sys.stdin)
        except Exception:
            return 0
        model = (data.get("model") or {}).get("display_name") or "?"
        cwd = (data.get("workspace") or {}).get("current_dir") or data.get("cwd") or ""
        info = shorten_dir(cwd, os.path.expanduser("~"))

        def pct(window):
            v = ((data.get("rate_limits") or {}).get(window) or {}).get("used_percentage")
            return 255 if v is None else max(0, min(100, int(round(v))))

        u5, u7 = pct("five_hour"), pct("seven_day")
        send([
            (CMD_CLIENT, bytes([CLIENT_CODES["claude"]])),
            (CMD_MODEL, text_payload(strip_version(model))),
            (CMD_INFO, text_payload(info)),
            (CMD_USAGE, bytes([u5, u7])),
        ])
        usage_txt = "" if u5 == 255 else f" | 5h {u5}%"
        print(f"{model} | {info}{usage_txt}")
    else:
        print(f"unknown command: {mode}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
