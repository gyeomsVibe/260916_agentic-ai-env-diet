"""Extreme / fault-injection suite for the SQLite pilot path (fake agy; no quota use).

Each scenario runs `python -m v7_harness.cli pilot ...` as a real subprocess in an isolated temp tree
and records observed behaviour. Results: .coord/runs/EXT/results.json
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
FAKE = Path(__file__).with_name("fake_agy_extreme.py")
PY = sys.executable
ORIGINAL = "def mul(a, b):\n    return a * b\n"
TEST = "import unittest\nimport calc\n\nclass T(unittest.TestCase):\n    def test_mul(self):\n        self.assertEqual(6, calc.mul(2, 3))\n"


def make_tree(root: Path, name: str = "src", extra_files: int = 0) -> Path:
    src = root / name
    src.mkdir(parents=True)
    (src / "calc.py").write_text(ORIGINAL, encoding="utf-8")
    (src / "test_calc.py").write_text(TEST, encoding="utf-8")
    for i in range(extra_files):
        (src / f"data{i:05d}.txt").write_text(str(i), encoding="utf-8")
    return src


def pilot(root: Path, src: Path, task: str, mode: str, *, timeout: int = 30, approve: str | None = None,
          accept: str | None = "python -m unittest -q", sleep: float = 0, work: Path | None = None,
          print_timeout: int = 5, popen: bool = False):
    work = work or root / "work"
    home = root / "home"
    home.mkdir(exist_ok=True)
    cmd = [PY, "-m", "v7_harness.cli", "pilot", "run", "--task", task, "--source", str(src), "--prompt", "add add()",
           "--work-dir", str(work), "--print-timeout", str(print_timeout), "--watch-root", str(home),
           "--agy-command", PY, str(FAKE)]
    if accept:
        cmd += ["--accept-cmd", accept]
    if approve:
        cmd += ["--approve", approve]
    env = dict(os.environ, EXT_MODE=mode, EXT_SLEEP=str(sleep), PYTHONPATH=str(PROJECT))
    if popen:
        return subprocess.Popen(cmd, cwd=PROJECT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    start = time.time()
    try:
        cp = subprocess.run(cmd, cwd=PROJECT, env=env, capture_output=True, timeout=timeout)
        rc, out, err = cp.returncode, cp.stdout, cp.stderr
    except subprocess.TimeoutExpired as exc:
        rc, out, err = "HARNESS_TIMEOUT", exc.stdout or b"", exc.stderr or b""
    wall = round(time.time() - start, 2)
    try:
        summary = json.loads(out.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        summary = None
    return {"rc": rc, "wall_s": wall, "summary": summary, "stderr_tail": err.decode("utf-8", errors="replace")[-300:]}


def db_state(work: Path) -> dict:
    db = work / "coord.sqlite3"
    if not db.exists():
        return {"db": "missing"}
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return {
            "integrity": c.execute("PRAGMA integrity_check").fetchone()[0],
            "attempts": c.execute("SELECT attempt_id,state FROM attempts").fetchall(),
            "deliveries": c.execute("SELECT delivery_id,state FROM deliveries").fetchall(),
            "active_leases": c.execute("SELECT count(*) FROM leases WHERE state='ACTIVE'").fetchone()[0],
        }
    finally:
        c.close()


def short(r: dict) -> dict:
    s = r.get("summary") or {}
    keys = ("state", "error_class", "effect_state", "promotion", "verdict_hint", "acceptance_exit")
    return {"rc": r["rc"], "wall_s": r["wall_s"], **{k: s.get(k) for k in keys}, "stderr_tail": r["stderr_tail"][-160:] if not s else ""}


def scenario(name, fn, results):
    t = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        try:
            out = fn(Path(tmp))
            status = out.pop("_verdict", "OBSERVED")
        except Exception as exc:  # harness-level crash is itself a finding
            out, status = {"harness_exception": repr(exc)[:300]}, "HARNESS_ERROR"
    results.append({"id": name, "verdict": status, "secs": round(time.time() - t, 1), **out})
    print(f"{name}: {status} ({results[-1]['secs']}s)", flush=True)


def x01_concurrent_same_workdir(tmp):
    srcs = [make_tree(tmp, f"src{i}") for i in range(6)]
    with ThreadPoolExecutor(6) as ex:
        rs = list(ex.map(lambda i: pilot(tmp, srcs[i], f"C{i}", "slow", sleep=1.5), range(6)))
    ok = sum(1 for r in rs if (r["summary"] or {}).get("state") == "SUCCEEDED")
    locked = sum(1 for r in rs if "BROKER_ALREADY_RUNNING" in r["stderr_tail"])
    st = db_state(tmp / "work")
    good = st.get("integrity") == "ok" and ok + locked == 6 and ok >= 1
    return {"succeeded": ok, "lock_rejected": locked, "db": st, "_verdict": "PASS" if good else "FAIL"}


def x02_same_task_double_submit(tmp):
    src = make_tree(tmp)
    with ThreadPoolExecutor(2) as ex:
        rs = list(ex.map(lambda _: pilot(tmp, src, "D1", "slow", sleep=1.5), range(2)))
    st = db_state(tmp / "work")
    runs = [short(r) for r in rs]
    one_exec = len(st.get("attempts", [])) == 1
    return {"runs": runs, "db": st, "_verdict": "PASS" if one_exec and st.get("integrity") == "ok" else "FAIL"}


def x03_kill_pilot_midrun_then_reconcile(tmp):
    src = make_tree(tmp)
    p = pilot(tmp, src, "K1", "slow", sleep=20, popen=True)
    time.sleep(6)
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
    p.wait(timeout=30)
    before = db_state(tmp / "work")
    blocked = pilot(tmp, src, "K1", "success")
    rec = subprocess.run([PY, "-m", "v7_harness.cli", "pilot", "reconcile", "--task", "K1", "--work-dir", str(tmp / "work")],
                         cwd=PROJECT, capture_output=True, env=dict(os.environ, PYTHONPATH=str(PROJECT)))
    rerun = pilot(tmp, src, "K1", "success")
    after = db_state(tmp / "work")
    ok = (short(blocked)["verdict_hint"] == "BLOCKED" and b"ABANDONED" in rec.stdout
          and short(rerun)["state"] == "SUCCEEDED" and after["active_leases"] == 0 and (src / "calc.py").read_text() == ORIGINAL)
    return {"db_after_kill": before, "rerun_without_reconcile": short(blocked), "reconcile_stdout": rec.stdout.decode()[-120:],
            "rerun_after_reconcile": short(rerun), "db_final": after, "_verdict": "PASS" if ok else "FAIL"}


def x04_hang_beyond_timeout(tmp):
    src = make_tree(tmp)
    r = pilot(tmp, src, "H1", "hang", print_timeout=1, timeout=150)
    s = short(r)
    ok = s["state"] != "SUCCEEDED" and s["promotion"] in ("BLOCKED", None) and r["wall_s"] < 140
    return {"result": s, "db": db_state(tmp / "work"), "_verdict": "PASS" if ok else "FAIL"}


def x05_child_process_hang_tree_kill(tmp):
    src = make_tree(tmp)
    before = subprocess.run(["tasklist", "/FI", "IMAGENAME eq python.exe"], capture_output=True, text=True).stdout.count("python.exe")
    r = pilot(tmp, src, "H2", "spawn_child_hang", print_timeout=1, timeout=150)
    time.sleep(2)
    after = subprocess.run(["tasklist", "/FI", "IMAGENAME eq python.exe"], capture_output=True, text=True).stdout.count("python.exe")
    s = short(r)
    return {"result": s, "python_procs_before": before, "python_procs_after": after,
            "_verdict": "PASS" if s["state"] != "SUCCEEDED" and after <= before else "FAIL"}


def x06_huge_stdout(tmp):
    src = make_tree(tmp)
    r = pilot(tmp, src, "B1", "huge_output", timeout=120)
    s = short(r)
    return {"result": s, "_verdict": "PASS" if s["state"] != "SUCCEEDED" and r["rc"] != "HARNESS_TIMEOUT" else "FAIL"}


def x07_binary_garbage(tmp):
    src = make_tree(tmp)
    s = short(pilot(tmp, src, "G1", "garbage"))
    return {"result": s, "_verdict": "PASS" if s["error_class"] == "VALIDATION" and s["promotion"] in ("BLOCKED", None) else "FAIL"}


def x08_tamper_staging_before_approve(tmp):
    src = make_tree(tmp)
    first = pilot(tmp, src, "T1", "success")
    bid = first["summary"]["bundle_id"]
    (tmp / "work" / "stage" / "T1" / "calc.py").write_text("import os  # tampered\n", encoding="utf-8")
    second = pilot(tmp, src, "T1", "success", approve=bid)
    ok = (src / "calc.py").read_text() == ORIGINAL and short(second)["promotion"] != "APPLIED"
    return {"first": short(first), "approve_after_tamper": short(second), "source_unchanged": (src / "calc.py").read_text() == ORIGINAL,
            "_verdict": "PASS" if ok else "FAIL"}


def x09_source_changed_before_approve(tmp):
    src = make_tree(tmp)
    first = pilot(tmp, src, "S1", "success")
    (src / "test_calc.py").write_text(TEST + "\n# human edit\n", encoding="utf-8")
    second = pilot(tmp, src, "S1", "success", approve=first["summary"]["bundle_id"])
    ok = "def add" not in (src / "calc.py").read_text() and short(second)["promotion"] != "APPLIED"
    return {"approve_after_source_edit": short(second), "_verdict": "PASS" if ok else "FAIL"}


def x10_escape_to_staging_parent(tmp):
    src = make_tree(tmp)
    r = pilot(tmp, src, "E1", "escape_parent")
    escaped = (tmp / "work" / "stage" / "ESCAPED_FROM_STAGING.txt").exists()
    s = short(r)
    detected = s["error_class"] == "EXTERNAL_WRITE"
    return {"result": s, "escaped_file_exists": escaped, "detected": detected,
            "_verdict": "PASS" if detected else ("GAP" if escaped else "FAIL")}


def x11_delete_in_staging_then_approve(tmp):
    src = make_tree(tmp)
    first = pilot(tmp, src, "R1", "delete_file", accept=None)
    s1 = short(first)
    bid = (first["summary"] or {}).get("bundle_id")
    second = pilot(tmp, src, "R1", "delete_file", approve=bid or "x", accept=None)
    ok = (src / "test_calc.py").exists() and short(second)["promotion"] != "APPLIED"
    return {"first": s1, "approve": short(second), "source_file_kept": (src / "test_calc.py").exists(), "_verdict": "PASS" if ok else "FAIL"}


def x12_corrupted_db(tmp):
    src = make_tree(tmp)
    pilot(tmp, src, "Z0", "success")
    db = tmp / "work" / "coord.sqlite3"
    data = bytearray(db.read_bytes())
    for i in range(100, min(len(data), 4096)):
        data[i] = 0xFF
    db.write_bytes(bytes(data))
    for suffix in ("-wal", "-shm"):
        p = Path(str(db) + suffix)
        if p.exists():
            p.unlink()
    r = pilot(tmp, src, "Z1", "success")
    s = short(r)
    ok = s["state"] != "SUCCEEDED" and (src / "calc.py").read_text() == ORIGINAL
    return {"result": s, "_verdict": "PASS" if ok else "FAIL"}


def x13_large_source_tree(tmp):
    src = make_tree(tmp, extra_files=5000)
    r = pilot(tmp, src, "L1", "success", timeout=300)
    return {"result": short(r), "files": 5002, "_verdict": "PASS" if short(r)["state"] == "SUCCEEDED" else "FAIL"}


def x14_many_generated_files(tmp):
    src = make_tree(tmp)
    r = pilot(tmp, src, "M1", "many_files", timeout=300)
    s = r["summary"] or {}
    return {"result": short(r), "changed_files": len(s.get("changed_files") or []), "_verdict": "PASS" if s.get("state") == "SUCCEEDED" and len(s.get("changed_files") or []) == 2001 else "FAIL"}


def x15_unicode_space_paths(tmp):
    src = make_tree(tmp, "소스 폴더 with space")
    first = pilot(tmp, src, "U1", "unicode")
    bid = (first["summary"] or {}).get("bundle_id")
    second = pilot(tmp, src, "U1", "unicode", approve=bid) if bid else first
    applied = (src / "한글 파일 name.py").exists()
    return {"first": short(first), "approve": short(second), "unicode_file_applied": applied,
            "_verdict": "PASS" if short(second)["promotion"] == "APPLIED" and applied else "FAIL"}


def x16_replay_storm(tmp):
    src = make_tree(tmp)
    first = pilot(tmp, src, "P1", "success")
    with ThreadPoolExecutor(8) as ex:
        rs = list(ex.map(lambda _: pilot(tmp, src, "P1", "success"), range(8)))
    st = db_state(tmp / "work")
    replayed = sum(1 for r in rs if (r["summary"] or {}).get("replayed"))
    locked = sum(1 for r in rs if "BROKER_ALREADY_RUNNING" in r["stderr_tail"])
    ok = len(st["attempts"]) == 1 and st["integrity"] == "ok" and replayed + locked == 8
    return {"replayed": replayed, "lock_rejected": locked, "db": st, "_verdict": "PASS" if ok else "FAIL"}


def main() -> int:
    results: list[dict] = []
    for name, fn in [
        ("X01_concurrent_6_tasks_same_workdir", x01_concurrent_same_workdir),
        ("X02_same_task_double_submit", x02_same_task_double_submit),
        ("X03_kill_pilot_midrun_reconcile_rerun", x03_kill_pilot_midrun_then_reconcile),
        ("X04_agy_hang_beyond_timeout", x04_hang_beyond_timeout),
        ("X05_child_process_hang_tree_kill", x05_child_process_hang_tree_kill),
        ("X06_60MB_stdout", x06_huge_stdout),
        ("X07_binary_garbage_stdout", x07_binary_garbage),
        ("X08_tamper_staging_before_approve", x08_tamper_staging_before_approve),
        ("X09_source_edit_before_approve", x09_source_changed_before_approve),
        ("X10_write_outside_staging_not_watch_root", x10_escape_to_staging_parent),
        ("X11_delete_in_staging_then_approve", x11_delete_in_staging_then_approve),
        ("X12_corrupted_sqlite_ledger", x12_corrupted_db),
        ("X13_source_tree_5000_files", x13_large_source_tree),
        ("X14_agent_generates_2000_files", x14_many_generated_files),
        ("X15_unicode_and_space_paths", x15_unicode_space_paths),
        ("X16_replay_storm_8_parallel", x16_replay_storm),
    ]:
        scenario(name, fn, results)
        Path(__file__).with_name("results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    counts = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print(json.dumps(counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
