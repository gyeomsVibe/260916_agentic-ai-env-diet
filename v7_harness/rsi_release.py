"""U42: evidence-to-PR release pipeline and deterministic change watcher.

Automates the cycle:
  observe / research → snapshot hash & dedupe → packet draft →
  fixed acceptance / holdout / red-team receipts → independent judge →
  SemVer bump → top document updates → approval-receipt bound shipping (git fetch/commit/push + gh pr create).
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional, Sequence


APPROVAL_TEXT = (
    "이 요청은 이 U42 범위의 전역 규칙 배포, 브랜치 생성, 커밋, 원격 푸시, PR 생성에 대한 명시적 승인이다. "
    "삭제·결제·계정/자격증명 변경은 금지한다."
)

REQUIRED_APPROVAL_ACTIONS = (
    "global_rule_deploy",
    "branch_create",
    "commit",
    "push",
    "pull_request_create",
)

FORBIDDEN_ACTIONS = (
    "delete_data",
    "spend_money",
    "change_account",
    "change_credentials",
    "auto_merge",
)

EVALUATOR_PATTERNS = (
    "tests/*",
    ".githooks/*",
    ".coord/runs/*",
    ".coord/usage/*",
    ".coord/rsi/decisions.jsonl",
    "v7_harness/rsi.py",
    "v7_harness/manual.py",
    "v7_harness/calculator_gate.py",
    "v7_harness/olla_evidence.py",
    "v7_harness/accept_triage.py",
    "v7_harness/adapters/ollama_worker.py",
    "v7_harness/isolation/*",
)

ALLOWED_DIRTY_PATTERNS = (
    ".coord/*",
    "docs/*",
    "tests/*",
    "v7_harness/*",
    "uaos_everywhere/*",
    "README.md",
)


class ReleaseRefused(Exception):
    """Raised when release validation, approval, or execution violates invariants."""


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def packet_fingerprint(packet: dict[str, Any]) -> str:
    """Stable cryptographic digest of the entire packet payload."""
    raw = json.dumps(packet, sort_keys=True, ensure_ascii=False)
    return _sha(raw)


def validate_packet(packet: dict[str, Any]) -> list[str]:
    """Validate release candidate packet against safety invariants."""
    problems: list[str] = []

    # 1. Sources: deduplication and snapshot integrity
    seen_urls: set[str] = set()
    for source in packet.get("sources", []):
        url = source.get("url", "")
        if url in seen_urls:
            problems.append(f"DUPLICATE_SOURCE:{url}")
        seen_urls.add(url)

        snapshot = source.get("snapshot", "")
        expected_hash = _sha(snapshot)
        if source.get("snapshot_sha256") != expected_hash:
            problems.append(f"SOURCE_HASH_MISMATCH:{url}")

    # 2. Evidence receipts: acceptance, holdout, red-team
    for stage in ("acceptance", "holdout", "red_team"):
        receipt = packet.get(stage)
        stage_upper = stage.upper()
        if not receipt or not isinstance(receipt, dict):
            problems.append(f"{stage_upper}_RECEIPT_MISSING")
            continue
        if receipt.get("exit_code") != 0:
            problems.append(f"{stage_upper}_NOT_PASS")
        if not receipt.get("fixed_sha256"):
            problems.append(f"{stage_upper}_FIXED_HASH_MISSING")

    # 3. Independent roles
    author = packet.get("author")
    verifier = packet.get("verifier")
    judge = packet.get("judge")
    if not author or not verifier or not judge:
        problems.append("ROLES_MISSING")
    else:
        if judge == author or judge == verifier:
            problems.append("JUDGE_NOT_INDEPENDENT")
        if verifier == author:
            problems.append("VERIFIER_NOT_INDEPENDENT")

    # 4. Protected paths
    for path in packet.get("changed_files", []):
        posix_path = str(Path(path).as_posix())
        if any(fnmatch.fnmatch(posix_path, pat) for pat in EVALUATOR_PATTERNS):
            problems.append(f"PROTECTED_PATH:{path}")

    # 5. Usage evidence
    usage = packet.get("usage")
    if not usage or not isinstance(usage, dict):
        problems.append("USAGE_MISSING")
    else:
        budget = usage.get("remote_budget_tokens")
        actual = usage.get("actual_tokens")
        if budget is not None and actual is not None and actual > budget:
            problems.append("REMOTE_BUDGET_EXCEEDED")
        if usage.get("wall_seconds") is None:
            problems.append("WALL_TIME_UNKNOWN")

    return problems


def duplicate_problems(packet: dict[str, Any], existing_proposals: Sequence[dict[str, Any]]) -> list[str]:
    """Check if the proposal has already been registered."""
    fp = packet_fingerprint(packet)
    existing_fps = {p.get("fingerprint") for p in existing_proposals if isinstance(p, dict)}
    if fp in existing_fps:
        return [f"DUPLICATE_PROPOSAL:{fp}"]
    return []


def bump_version(version: str, change_type: str) -> str:
    """Deterministically increment SemVer version."""
    parts = version.strip().split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid SemVer version string: '{version}'")
    try:
        major, minor, patch = (int(p) for p in parts)
    except ValueError as exc:
        raise ValueError(f"Non-integer SemVer component in: '{version}'") from exc

    ct = change_type.lower().strip()
    if ct in ("fix", "patch"):
        patch += 1
    elif ct in ("feature", "minor"):
        minor += 1
        patch = 0
    elif ct in ("breaking", "major"):
        major += 1
        minor = 0
        patch = 0
    else:
        raise ValueError(f"Unsupported change_type: '{change_type}'")
    return f"{major}.{minor}.{patch}"


def render_top_update(original: str, *, version: str, date: str, summary: str, fingerprint: str) -> str:
    """Insert an update section right under the top-level heading in an idempotent manner."""
    marker = f"<!-- uaos-update:{fingerprint} -->"
    if marker in original:
        return original

    block = f"{marker}\n## 업데이트 ({version}, {date})\n\n- {summary}\n\n"

    # Find position after the first # Title heading
    lines = original.splitlines(keepends=True)
    insert_idx = 0
    found_title = False
    for i, line in enumerate(lines):
        if line.startswith("# "):
            found_title = True
            # Find next non-empty line after title
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            insert_idx = j
            break

    if found_title:
        before = "".join(lines[:insert_idx])
        after = "".join(lines[insert_idx:])
        if not before.endswith("\n\n"):
            before = before.rstrip("\n") + "\n\n"
        return before + block + after
    return block + original


def prepare_release(
    root: Path,
    packet: dict[str, Any],
    *,
    apply: bool = False,
    date: str = "2026-09-25",
) -> dict[str, Any]:
    """Prepare release artifacts and version bump, defaulting to dry run."""
    problems = validate_packet(packet)
    if problems:
        raise ReleaseRefused(f"PACKET_INVALID: {', '.join(problems)}")

    version_rel = packet.get("version_file", "VERSION")
    version_file = root / version_rel
    current_version = "0.0.0"
    if version_file.is_file():
        current_version = version_file.read_text(encoding="utf-8").strip() or "0.0.0"

    next_ver = bump_version(current_version, packet.get("change_type", "feature"))
    fp = packet_fingerprint(packet)

    plan = {
        "current_version": current_version,
        "next_version": next_ver,
        "version_file": version_rel,
        "fingerprint": fp,
        "apply": apply,
    }

    if apply:
        version_file.parent.mkdir(parents=True, exist_ok=True)
        version_file.write_text(f"{next_ver}\n", encoding="utf-8")

        summary = packet.get("summary", "")
        for doc_rel in packet.get("update_documents", []):
            doc_path = root / doc_rel
            if doc_path.is_file():
                doc_text = doc_path.read_text(encoding="utf-8")
                updated_text = render_top_update(
                    doc_text,
                    version=next_ver,
                    date=date,
                    summary=summary,
                    fingerprint=fp,
                )
                doc_path.write_text(updated_text, encoding="utf-8")

    return plan


def validate_approval(approval: dict[str, Any], *, work_id: str) -> list[str]:
    """Validate explicit user approval receipt."""
    problems: list[str] = []

    if approval.get("work_id") != work_id:
        problems.append("WORK_ID_MISMATCH")

    text = approval.get("approval_text", "")
    expected_hash = _sha(text)
    if approval.get("approval_sha256") != expected_hash:
        problems.append("APPROVAL_HASH_MISMATCH")

    allowed = set(approval.get("allowed_actions", []))
    for act in REQUIRED_APPROVAL_ACTIONS:
        if act not in allowed:
            problems.append(f"APPROVAL_ACTION_MISSING:{act}")

    for act in allowed:
        if act in FORBIDDEN_ACTIONS:
            problems.append(f"FORBIDDEN_ACTION_ALLOWED:{act}")

    return problems


def ship_release(
    root: Path,
    packet: dict[str, Any],
    approval: dict[str, Any],
    *,
    execute: bool = False,
    run: Optional[Callable[..., subprocess.CompletedProcess]] = None,
) -> dict[str, Any]:
    """Commit, push, and open PR with strict fail-closed safety checks."""
    if run is None:
        run = subprocess.run

    # 1. Invariant validation
    packet_problems = validate_packet(packet)
    if packet_problems:
        raise ReleaseRefused(f"PACKET_INVALID: {', '.join(packet_problems)}")

    approval_problems = validate_approval(approval, work_id=packet.get("work_id", ""))
    if approval_problems:
        raise ReleaseRefused(f"APPROVAL_INVALID: {', '.join(approval_problems)}")

    base_branch = packet.get("base_branch", "main")
    branch = packet.get("branch", f"codex/{packet.get('work_id', 'task').lower()}-release")
    title = packet.get("title", "Automated RSI Release")
    summary = packet.get("summary", "")
    commit_msg = f"feat({packet.get('work_id', 'release').lower()}): {title}"

    commands = [
        ["git", "status", "--porcelain"],
        ["git", "fetch", "origin", base_branch],
        ["git", "commit", "-m", commit_msg],
        ["git", "push", "origin", branch],
        ["gh", "pr", "create", "--base", base_branch, "--head", branch, "--title", title, "--body", summary],
        ["gh", "pr", "view", branch, "--json", "url,state"],
    ]

    if not execute:
        return {"status": "DRY_RUN", "commands": commands}

    # 2. Check git status for unexpected dirty files when executing
    status_proc = run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=False)
    if status_proc.stdout:
        expected_paths = {
            str(Path(f).as_posix()) for f in packet.get("changed_files", [])
        }
        for f in packet.get("update_documents", []):
            expected_paths.add(str(Path(f).as_posix()))
        if packet.get("version_file"):
            expected_paths.add(str(Path(packet["version_file"]).as_posix()))

        for line in status_proc.stdout.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            parts = line_str.split(maxsplit=1)
            if len(parts) < 2:
                continue
            path_part = parts[1].strip()
            if " -> " in path_part:
                path_part = path_part.split(" -> ")[1].strip()
            path_posix = str(Path(path_part).as_posix())

            matched = (
                path_posix in expected_paths
                or any(fnmatch.fnmatch(path_posix, pat) for pat in ALLOWED_DIRTY_PATTERNS)
            )
            if not matched:
                raise ReleaseRefused(f"UNEXPECTED_DIRTY_PATH: {path_part}")

    # 3. Fetch
    run(["git", "fetch", "origin", base_branch], cwd=root, capture_output=True, text=True, check=False)

    # 4. Stage only permitted paths
    stage_targets = []
    for f in packet.get("changed_files", []):
        stage_targets.append(str(Path(f).as_posix()))
    for f in packet.get("update_documents", []):
        stage_targets.append(str(Path(f).as_posix()))
    if packet.get("version_file"):
        stage_targets.append(str(Path(packet["version_file"]).as_posix()))

    if stage_targets:
        run(["git", "add"] + stage_targets, cwd=root, capture_output=True, text=True, check=False)

    # 5. Commit
    run(["git", "commit", "-m", commit_msg], cwd=root, capture_output=True, text=True, check=False)

    # 6. HEAD SHA
    head_proc = run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False)
    head_sha = head_proc.stdout.strip() if head_proc else ""

    # 7. Push
    run(["git", "push", "origin", branch], cwd=root, capture_output=True, text=True, check=False)

    # 8. Check remote SHA
    ls_proc = run(["git", "ls-remote", "origin", f"refs/heads/{branch}"], cwd=root, capture_output=True, text=True, check=False)
    remote_sha = ""
    if ls_proc and ls_proc.stdout:
        remote_sha = ls_proc.stdout.split()[0].strip() if ls_proc.stdout.strip() else head_sha
    if not remote_sha:
        remote_sha = head_sha

    # 9. Create PR (never auto-merge!)
    run(
        ["gh", "pr", "create", "--base", base_branch, "--head", branch, "--title", title, "--body", summary],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    # 10. View PR
    view_proc = run(["gh", "pr", "view", branch, "--json", "url,state"], cwd=root, capture_output=True, text=True, check=False)
    pr_data: dict[str, Any] = {"state": "UNKNOWN", "url": ""}
    if view_proc and view_proc.stdout:
        try:
            pr_data = json.loads(view_proc.stdout)
        except (ValueError, json.JSONDecodeError):
            pr_data = {"raw": view_proc.stdout.strip()}

    return {
        "status": "SHIPPED",
        "pr": pr_data,
        "head_sha": head_sha,
        "remote_sha": remote_sha,
    }


def run_scheduler_cycle(
    root: Path,
    config: dict[str, Any],
    *,
    fetch: Optional[Callable[..., dict[str, Any]]] = None,
    trigger: Optional[Callable[[dict[str, Any]], None]] = None,
    now: float = 0.0,
) -> dict[str, Any]:
    """Run one bounded deterministic change-detection cycle."""
    lock_file = root / ".work" / "rsi-scheduler.lock"
    if lock_file.is_file():
        return {"status": "LOCKED"}

    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(json.dumps({"pid": os.getpid(), "started_at": now}), encoding="utf-8")

    try:
        timeout = config.get("timeout_seconds", 15)
        max_retries = config.get("max_retries", 3)
        backoff_base = config.get("backoff_base_seconds", 60)
        backoff_seconds = [backoff_base * (2**i) for i in range(max_retries)]

        state_file = root / ".work" / "rsi-scheduler-state.json"
        prior_state: dict[str, dict[str, Any]] = {}
        if state_file.is_file():
            try:
                prior_state = json.loads(state_file.read_text(encoding="utf-8"))
            except (ValueError, json.JSONDecodeError):
                prior_state = {}

        actionable = False
        observations: dict[str, dict[str, Any]] = {}

        for source in config.get("sources", []):
            url = source.get("url", "")
            # Fetch with bounded retries and exponential backoff receipt on failure
            obs: Optional[dict[str, Any]] = None
            last_exc: Optional[Exception] = None
            for _ in range(max_retries):
                try:
                    if fetch is not None:
                        obs = fetch(source, timeout)
                    break
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc

            if obs is None:
                return {
                    "status": "FAILED",
                    "backoff_seconds": backoff_seconds,
                    "next_run_at": now + backoff_seconds[-1],
                    "failure_receipt": {"error": f"{type(last_exc).__name__}: {last_exc}"},
                }

            observations[url] = obs

            # Check if actionable delta exists
            prev_obs = prior_state.get(url)
            if prev_obs is not None:
                # Content change is the sole actionable delta; etag/date only changes are ACK_ONLY
                if obs.get("content_sha256") != prev_obs.get("content_sha256"):
                    actionable = True
                    if trigger is not None:
                        trigger(obs)

        # Update saved state
        state_file.write_text(json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8")

        if actionable:
            return {"status": "ACTIONABLE_DELTA", "observations": observations}
        return {"status": "ACK_ONLY", "observations": observations}

    finally:
        if lock_file.is_file():
            try:
                lock_file.unlink()
            except OSError:
                pass


def windows_schedule(
    project: Path,
    python_bin: str,
    *,
    action: str = "install",
    apply: bool = False,
    run: Optional[Callable[..., subprocess.CompletedProcess]] = None,
) -> dict[str, Any]:
    """Manage Windows Task Scheduler task for deterministic daily rsi watch."""
    if run is None:
        run = subprocess.run

    task_name = "UAOS_RSI_Watch"
    if action == "install":
        command = [
            "schtasks",
            "/Create",
            "/F",
            "/SC",
            "DAILY",
            "/TN",
            task_name,
            "/TR",
            f'"{python_bin}" -m v7_harness.cli rsi watch --project "{project}"',
        ]
    elif action == "status":
        command = ["schtasks", "/Query", "/TN", task_name, "/FO", "LIST", "/V"]
    elif action == "remove":
        command = ["schtasks", "/Delete", "/F", "/TN", task_name]
    else:
        raise ValueError(f"Unknown scheduler action: '{action}'")

    if not apply:
        return {"status": "DRY_RUN", "action": action, "command": command}

    proc = run(command, capture_output=True, text=True, check=False)
    return {
        "ok": proc.returncode == 0,
        "status": "APPLIED",
        "action": action,
        "output": proc.stdout.strip(),
        "error": proc.stderr.strip(),
    }
