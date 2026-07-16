#!/usr/bin/env python3
"""Best-effort bridge from Codex CLI hooks to the Zima OLED.

The hook action is supplied by config.toml. Hook input is a JSON object on
stdin. This adapter deliberately produces no diagnostics and always exits 0;
OLED updates must never interfere with Codex.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


TRANSCRIPT_TAIL_BYTES = 1024 * 1024
WINDOWS = {300: 0, 10080: 1}
STATUSES = {
    "session": "idle",
    "working": "working",
    "waiting": "waiting",
    "idle": "idle",
}


def extract_model(event: Any) -> str | None:
    """Return the Codex model slug when the hook supplied one."""
    if not isinstance(event, dict):
        return None
    model = event.get("model")
    return model.strip() if isinstance(model, str) and model.strip() else None


def format_model_for_oled(model: str) -> str:
    """Turn a GPT model slug into a compact OLED label."""
    match = re.fullmatch(
        r"gpt[-_\s]+(\d+(?:\.\d+)*)(?:[-_\s]+(.+))?",
        model,
        flags=re.IGNORECASE,
    )
    if match is None:
        return model

    version, variant = match.groups()
    if not variant:
        return version
    variant = re.sub(r"[-_\s]+", " ", variant).strip().lower()
    return f"{version} {variant}"


def _percent(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 255
    if not math.isfinite(value):
        return 255
    return max(0, min(100, int(value + 0.5)))


def _rate_limits_from_record(record: Any) -> dict[str, Any] | None:
    """Accept the current Codex JSONL shape plus two simple fixture shapes."""
    if not isinstance(record, dict):
        return None

    candidates: list[Any] = []
    payload = record.get("payload")
    if isinstance(payload, dict) and payload.get("type") == "token_count":
        candidates.append(payload)
    if record.get("type") == "token_count":
        candidates.append(record)
    candidates.append(record.get("token_count"))

    for candidate in candidates:
        if isinstance(candidate, dict) and isinstance(candidate.get("rate_limits"), dict):
            return candidate["rate_limits"]
    return None


def usage_from_rate_limits(rate_limits: Any) -> tuple[int, int]:
    """Map 300/10080-minute windows to the OLED's 5h/7d percentages."""
    usage = [255, 255]
    if not isinstance(rate_limits, dict):
        return usage[0], usage[1]

    for name in ("primary", "secondary"):
        window = rate_limits.get(name)
        if not isinstance(window, dict):
            continue
        minutes = window.get("window_minutes")
        if isinstance(minutes, float) and minutes.is_integer():
            minutes = int(minutes)
        index = WINDOWS.get(minutes)
        if index is not None:
            usage[index] = _percent(window.get("used_percent"))
    return usage[0], usage[1]


def read_transcript_usage(path_value: Any) -> tuple[int, int]:
    """Read the newest token_count record from at most the last 1 MiB."""
    if not isinstance(path_value, str) or not path_value:
        return 255, 255

    try:
        path = Path(path_value).expanduser()
        with path.open("rb") as transcript:
            transcript.seek(0, 2)
            size = transcript.tell()
            start = max(0, size - TRANSCRIPT_TAIL_BYTES)
            transcript.seek(start)
            tail = transcript.read(TRANSCRIPT_TAIL_BYTES)

        # A bounded read may start in the middle of a JSONL record.
        if start:
            newline = tail.find(b"\n")
            tail = b"" if newline < 0 else tail[newline + 1 :]

        for raw_line in reversed(tail.splitlines()):
            try:
                rate_limits = _rate_limits_from_record(json.loads(raw_line))
            except Exception:
                continue
            if rate_limits is not None:
                return usage_from_rate_limits(rate_limits)
    except Exception:
        pass
    return 255, 255


def push_zima(*args: str) -> None:
    """Invoke the existing Raw HID CLI with a short, silent timeout."""
    try:
        subprocess.run(
            [sys.executable, str(Path(__file__).with_name("zima_push.py")), *args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=0.75,
            check=False,
        )
    except Exception:
        pass


def handle_event(
    action: str,
    event: Any,
    push: Callable[..., None] = push_zima,
) -> None:
    """Push metadata first and the requested lifecycle state last."""
    model = extract_model(event)
    if model is not None:
        push("model", format_model_for_oled(model))

    transcript_path = event.get("transcript_path") if isinstance(event, dict) else None
    five_hour, seven_day = read_transcript_usage(transcript_path)
    push("usage", str(five_hour), str(seven_day))

    status = STATUSES.get(action)
    if status is not None:
        push("status", status)


def main() -> int:
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    try:
        event = json.load(sys.stdin)
        if action in STATUSES:
            handle_event(action, event)
    except BaseException:
        pass

    # Codex Stop hooks expect JSON on stdout. {} means "no decision".
    if action == "idle":
        print("{}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BaseException:
        # Last-resort fail-open guard, including interpreter shutdown edge cases.
        sys.exit(0)
