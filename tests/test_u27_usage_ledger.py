from __future__ import annotations

import json
import multiprocessing as mp
import os
import tempfile
import unittest
from pathlib import Path

from v7_harness.coord.usage_ledger import record_usage, UsageRejected


def _entry(work_id: str) -> dict:
    return {
        "schema": "uaos-usage-v2",
        "work_id": work_id,
        "actor": "antigravity",
        "model": "qwen2.5-coder:7b",
        "kind": "pilot",
        "collection_mode": "manual",
        "input_tokens": 1200,
        "output_tokens": 250,
        "wall_time_s": 1.5,
        "outcome": "PASS",
        "receipt": "local-run-12345",
        "independent_verifier": "codex",
        "rsi_eligible": True,
        "exclusion_reason": None,
    }


def _writer(root: str, prefix: str, count: int) -> None:
    p_root = Path(root)
    for i in range(count):
        record_usage(p_root, _entry(f"{prefix}_{i}"))


class TestU27UsageLedger(unittest.TestCase):
    def test_record_usage_normal(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            entry = _entry("TEST_U27_01")
            entry_copy = dict(entry)
            self.assertNotIn("ts", entry)
            p = record_usage(root, entry)
            self.assertEqual(entry, entry_copy)
            self.assertNotIn("ts", entry)
            self.assertTrue(p.is_file())
            lines = p.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            data = json.loads(lines[0])
            self.assertEqual(data["work_id"], "TEST_U27_01")
            self.assertEqual(data["schema"], "uaos-usage-v2")
            self.assertIn("ts", data)
            self.assertIsInstance(data["ts"], (int, float))

    def test_record_usage_secret_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            record = _entry("TEST_SEC")
            record["receipt"] = "Bearer abcdefghijklmnopqrstuvwxyz123456"
            with self.assertRaises(UsageRejected):
                record_usage(root, record)

    def test_record_usage_missing_required(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            record = _entry("TEST_MISSING")
            del record["receipt"]
            with self.assertRaises(UsageRejected):
                record_usage(root, record)

    def test_record_usage_lock_timeout(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            usage_dir = root / ".coord" / "usage"
            usage_dir.mkdir(parents=True, exist_ok=True)
            lock_path = usage_dir / "runs.jsonl.lock"
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            try:
                record = _entry("TEST_LOCK_TIMEOUT")
                with self.assertRaises(UsageRejected) as cm:
                    record_usage(root, record, lock_timeout_s=0.05)
                self.assertIn("lock timeout", str(cm.exception))
                target_file = usage_dir / "runs.jsonl"
                if target_file.exists():
                    lines = target_file.read_text(encoding="utf-8").splitlines()
                    self.assertEqual(len(lines), 0)
                else:
                    self.assertFalse(target_file.exists())
            finally:
                os.close(fd)
                try:
                    os.unlink(str(lock_path))
                except OSError:
                    pass

    def test_record_usage_concurrency_stress(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ctx = mp.get_context("spawn")
            num_workers = 4
            recs_per_worker = 10
            processes = []
            for idx in range(num_workers):
                p = ctx.Process(
                    target=_writer,
                    args=(str(root), f"w{idx}", recs_per_worker),
                )
                p.start()
                processes.append(p)

            for p in processes:
                p.join(timeout=15.0)
                self.assertEqual(p.exitcode, 0)

            target_file = root / ".coord" / "usage" / "runs.jsonl"
            self.assertTrue(target_file.is_file())
            lines = target_file.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), num_workers * recs_per_worker)
            work_ids = set()
            for idx, line in enumerate(lines):
                obj = json.loads(line)
                self.assertIn("work_id", obj, f"Corrupted record at line {idx}")
                work_ids.add(obj["work_id"])
            self.assertEqual(len(work_ids), num_workers * recs_per_worker)


if __name__ == "__main__":
    unittest.main()
