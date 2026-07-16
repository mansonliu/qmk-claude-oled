#!/usr/bin/env python3
"""Tests for the Codex-to-Zima hook adapter (no keyboard required)."""

import json
import tempfile
import unittest
from pathlib import Path

from host import codex_hook, zima_push


class CodexHookTests(unittest.TestCase):
    def test_extracts_model_and_pushes_working(self):
        calls = []
        codex_hook.handle_event(
            "working",
            {"model": "gpt-5.4-codex", "transcript_path": None},
            lambda *args: calls.append(args),
        )
        self.assertEqual(
            calls,
            [
                ("model", "5.4 codex"),
                ("usage", "255", "255"),
                ("status", "working"),
            ],
        )

    def test_formats_gpt_model_for_oled(self):
        cases = {
            "gpt-5.6-sol": "5.6 sol",
            "GPT 5.6 SOL": "5.6 sol",
            "gpt_5.6_sol_preview": "5.6 sol preview",
            "gpt-5.6": "5.6",
            "o3": "o3",
        }
        for model, expected in cases.items():
            with self.subTest(model=model):
                self.assertEqual(codex_hook.format_model_for_oled(model), expected)

    def test_reads_latest_rate_limits_and_maps_windows(self):
        records = [
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "rate_limits": {
                        "primary": {"used_percent": 1, "window_minutes": 300},
                        "secondary": {"used_percent": 2, "window_minutes": 10080},
                    },
                },
            },
            {"type": "unrelated"},
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "rate_limits": {
                        "primary": {"used_percent": 37.4, "window_minutes": 10080},
                        "secondary": {"used_percent": 62.6, "window_minutes": 300},
                    },
                },
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            transcript = Path(directory) / "rollout.jsonl"
            transcript.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(codex_hook.read_transcript_usage(str(transcript)), (63, 37))

    def test_missing_or_malformed_usage_is_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            transcript = Path(directory) / "rollout.jsonl"
            transcript.write_text("not json\n", encoding="utf-8")
            self.assertEqual(codex_hook.read_transcript_usage(str(transcript)), (255, 255))
        self.assertEqual(codex_hook.read_transcript_usage(None), (255, 255))

    def test_zima_push_preserves_unknown_usage_sentinel(self):
        reports = []
        original_argv = zima_push.sys.argv
        original_send = zima_push.send
        try:
            zima_push.sys.argv = ["zima_push.py", "usage", "255", "255"]
            zima_push.send = lambda value: reports.extend(value)
            self.assertEqual(zima_push.main(), 0)
        finally:
            zima_push.sys.argv = original_argv
            zima_push.send = original_send
        self.assertEqual(reports, [(zima_push.CMD_USAGE, bytes([255, 255]))])


if __name__ == "__main__":
    unittest.main()
