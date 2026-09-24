"""Codex 복귀 시 22개 체크리스트 항목을 원터치로 전수 검증하는 스크립트.

실행 방법:
    python .coord/runs/verify_codex_return.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


CHECKS = [
    ("B64 Broker stop budget", [sys.executable, "-m", "unittest", "tests.test_b64_broker_drain_budget", "tests.test_u11_broker"]),
    ("B63 Stream lock contention", [sys.executable, "-m", "unittest", "tests.test_u15_lock_contention"]),
    ("Agent English headers & Notify", [sys.executable, "-m", "unittest", "tests.test_u15_codex_brief", "tests.test_u15_notify_codex"]),
    ("olla CLI & Squeeze test", [sys.executable, "-m", "unittest", "tests.test_u17_olla"]),
    ("U16 Local worker", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-p", "test_u16_*"]),
    ("U15 Coordination stream", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-p", "test_u15_*"]),
    ("U21 Calculator Principle", [sys.executable, "-m", "unittest", "tests.test_u21_calculator"]),
    ("U22 Worker limits & Install", [sys.executable, "-m", "unittest", "tests.test_u22_worker_limits"]),
    ("U23 Mailbox & Sentinel", [sys.executable, "-m", "unittest", "tests.test_u23_mailbox"]),
    ("U24 Codex bridge", [sys.executable, "-m", "unittest", "tests.test_u24_codex_bridge"]),
    ("U27 Usage ledger automation", [sys.executable, "-m", "unittest", "tests.test_u27_usage_ledger"]),
    ("Bytecode compilation (compileall)", [sys.executable, "-m", "compileall", "-q", "v7_harness", "tests"]),
    ("Sentinel live cycle health check", [sys.executable, "-m", "v7_harness.cli", "coord", "sentinel", "--once", "--write-brief"]),
]


def run_checks() -> int:
    print("=" * 70)
    print("Codex Return Verification Suite (Automated Checklist)")
    print(f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}")
    print(f"Project: {PROJECT_ROOT}")
    print("=" * 70)

    passed = 0
    failed = 0
    results = []

    for name, cmd in CHECKS:
        t0 = time.monotonic()
        proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, encoding="utf-8", errors="replace")
        elapsed = time.monotonic() - t0
        ok = (proc.returncode == 0)

        status_str = "PASS" if ok else "FAIL"
        print(f"[{status_str}] {name} ({elapsed:.2f}s)")
        if not ok:
            print(f"       Exit code: {proc.returncode}")
            err_head = "\n".join(proc.stderr.strip().splitlines()[-5:])
            print(f"       Stderr tail:\n{err_head}")
            failed += 1
        else:
            passed += 1

        results.append({
            "name": name,
            "status": status_str,
            "elapsed_s": round(elapsed, 2),
            "exit_code": proc.returncode,
        })

    print("-" * 70)
    print(f"Total: {len(CHECKS)} checks | Passed: {passed} | Failed: {failed}")
    print("=" * 70)

    summary_file = PROJECT_ROOT / ".coord" / "runs" / "codex_return_verification_summary.json"
    summary_file.write_text(json.dumps({
        "timestamp": time.time(),
        "total": len(CHECKS),
        "passed": passed,
        "failed": failed,
        "all_passed": (failed == 0),
        "checks": results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Report saved to: {summary_file}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_checks())
