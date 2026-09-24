"""U31: reproduce gaps between the five metaphors and the mailbox/sentinel code.

Run from the project root: python .coord/runs/U31/metaphor_probe.py
Every probe works in a fresh temp directory, so the real mailbox, stream and ledger are never touched.
Each line prints CONFIRMED (the gap reproduces) or NOT_REPRODUCED (the gap is fixed).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from v7_harness.coord.mailbox import Mailbox  # noqa: E402
from v7_harness.coord.sentinel import check_ledger_reconciliation, run_sentinel_cycle  # noqa: E402
from v7_harness.coord.stream import append_event  # noqa: E402


def fresh() -> tuple[Path, Mailbox]:
    root = Path(tempfile.mkdtemp())
    mailbox_root = root / ".coord" / "mailbox"
    mailbox_root.mkdir(parents=True)
    return root, Mailbox(mailbox_root)


def verdict(gap: bool) -> str:
    return "CONFIRMED" if gap else "NOT_REPRODUCED"


def probe_redelivery() -> None:
    root, box = fresh()
    append_event(root, actor="claude", kind="RUN", step="S1", summary="done", evidence={"cmd": "x", "exit": 0})
    run_sentinel_cycle(root, box)
    first = [i for i in box.list_inbox() if i.startswith("evt_")]
    box.ack(box.claim(first[0], "codex"))
    run_sentinel_cycle(root, box)
    again = [i for i in box.list_inbox() if i.startswith("evt_")]
    print("P1 acked event redelivered by the next sentinel cycle:", verdict(bool(again)), again)


def probe_stale_recovery() -> None:
    root, box = fresh()
    path = box.publish("m1", {"n": 1})
    published_two_minutes_ago = time.time() - 120
    os.utime(path, (published_two_minutes_ago, published_two_minutes_ago))
    claim = box.claim("m1", "worker")
    recovered = box.recover_stale_claims(stale_timeout_s=60)
    ack_path = box.ack(claim)
    gap = recovered == ["m1"] and not ack_path.is_file()
    print("P2 fresh claim treated as stale; ack reports a file it never wrote:", verdict(gap),
          f"recovered={recovered} ack_written={ack_path.is_file()} inbox={box.list_inbox()}")


def probe_nack_loss() -> None:
    root, box = fresh()
    box.publish("m2", {"v": "old"})
    claim = box.claim("m2", "worker")
    box.publish("m2", {"v": "new"})
    box.nack(claim)
    inbox_file = box.inbox_dir / "m2.json"
    survivors = [json.loads(inbox_file.read_text(encoding="utf-8"))["payload"]] if inbox_file.exists() else []
    survivors += [json.loads(p.read_text(encoding="utf-8"))["payload"] for p in box.claimed_dir.glob("*.json")]
    print("P3 nack after a same-id republish keeps only one of two messages:", verdict(len(survivors) < 2), survivors)


def probe_reconciliation() -> None:
    root, _ = fresh()
    run = root / ".coord" / "pilot" / "runs" / "T1"
    run.mkdir(parents=True)
    summary = {"state": "FAILED", "error_class": "NEEDS_RECONCILIATION", "verdict_hint": "BLOCKED"}
    (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    found = check_ledger_reconciliation(root / ".coord" / "pilot")
    print("P4 real NEEDS_RECONCILIATION summary missed by the sentinel:", verdict(found == []), found)


def probe_bell() -> None:
    root, box = fresh()
    (root / ".work").mkdir()
    (root / ".work" / "QUIET_LOCK").write_text(json.dumps({"pid": 999999, "started_at": time.time()}), encoding="utf-8")
    result = run_sentinel_cycle(root, box)
    wakes = [i for i in box.list_inbox() if i.startswith("wake_")]
    print("P5 P1 wake exists only as a mailbox file (no queue/OS signal):",
          verdict(result["p1_wake_emitted"] and bool(wakes)), wakes)


if __name__ == "__main__":
    probe_redelivery()
    probe_stale_recovery()
    probe_nack_loss()
    probe_reconciliation()
    probe_bell()
