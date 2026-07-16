#!/usr/bin/env python3
"""Push Claude Code state to the splitkb Zima OLED over QMK Raw HID.

Usage:
  zima_push.py model "Fable 5"          # set model name line
  zima_push.py status working           # idle|working|waiting|error
  zima_push.py info "~/git/foo"         # set info line
  zima_push.py statusline               # Claude Code statusline mode:
                                        #   reads statusline JSON on stdin,
                                        #   pushes model+info, prints text

All pushes are best-effort: if the keyboard is unplugged the script exits 0
silently so statusline/hooks never break.
"""
import json
import os
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

STATUS_CODES = {"idle": 0, "working": 1, "waiting": 2, "error": 3}


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
    elif mode == "statusline":
        try:
            data = json.load(sys.stdin)
        except Exception:
            return 0
        model = (data.get("model") or {}).get("display_name") or "?"
        cwd = (data.get("workspace") or {}).get("current_dir") or data.get("cwd") or ""
        info = shorten_dir(cwd, os.path.expanduser("~"))
        send([
            (CMD_MODEL, text_payload(model)),
            (CMD_INFO, text_payload(info)),
        ])
        print(f"{model} | {info}")
    else:
        print(f"unknown command: {mode}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
