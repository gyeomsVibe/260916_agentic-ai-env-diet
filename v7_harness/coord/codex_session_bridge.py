"""U24 / docs/24: Codex 대화창 브릿지 (Codex Session Bridge).

Antigravity와 Claude Code의 수행 프로세스 대화를 Codex 데스크톱 앱의 프로젝트 대화(Thread) 목록에
직접 하나의 독립 세션으로 편입·동기화한다.

사용자 명명 규칙:
- Antigravity: `[agy-<작업명>]`
- Claude Code: `[claude-<작업명>]`

구현 원리:
1. `~/.codex/sessions/<YYYY>/<MM>/<DD>/rollout-<ts>-<thread_id>.jsonl` 세션 롤아웃 파일 생성
2. `~/.codex/state_5.sqlite`의 `threads` 테이블에 메타데이터 등록 (UUIDv7, title/preview, project_id 매핑)
3. `~/.codex/session_index.jsonl`에 스레드 색인 추가
4. `~/.codex/.codex-global-state.json`의 `thread-project-assignments` 및 `sidebar-project-thread-orders`에
   현재 프로젝트와 스레드 ID를 실시간 등록하여 Electron 데스크톱 앱 사이드바에 즉각 노출 보장.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

ALLOWED_ACTORS = ("agy", "claude", "antigravity")


def generate_uuidv7() -> str:
    """Codex 데스크톱 앱과 호환되는 타임스탬프 기반 UUIDv7을 생성한다."""
    ms = int(time.time() * 1000)
    rand = os.urandom(10)
    raw = (
        ms.to_bytes(6, "big")
        + bytes([0x70 | (rand[0] & 0x0F), rand[1]])
        + bytes([0x80 | (rand[2] & 0x3F)])
        + rand[3:10]
    )
    return str(uuid.UUID(bytes=raw))


def get_codex_home() -> Path:
    override = os.environ.get("CODEX_HOME")
    if override:
        return Path(override)
    userprofile = os.environ.get("USERPROFILE")
    if userprofile and (Path(userprofile) / ".codex" / "state_5.sqlite").exists():
        return Path(userprofile) / ".codex"
    cand = Path.home() / ".codex"
    if (cand / "state_5.sqlite").exists():
        return cand
    return cand


def format_thread_name(actor: str, task_name: str) -> str:
    norm_actor = "agy" if actor.lower() in ("agy", "antigravity") else "claude"
    clean_task = task_name.strip().lstrip("[").rstrip("]")
    if clean_task.startswith(f"{norm_actor}-"):
        clean_task = clean_task[len(norm_actor) + 1 :]
    return f"[{norm_actor}-{clean_task}]"


def parse_transcript_to_turns(transcript_path: Path) -> list[tuple[str, str]]:
    """Antigravity 세션 transcript.jsonl 등을 파싱하여 (prompt, response) 튜플 목록으로 변환한다."""
    if not transcript_path.is_file():
        return []
    turns: list[tuple[str, str]] = []
    current_user_prompt: str | None = None
    current_assistant_resp: list[str] = []

    for line in transcript_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue

        step_type = item.get("type")
        content = item.get("content")

        if step_type == "USER_INPUT" and isinstance(content, str):
            if current_user_prompt is not None:
                asst_text = "\n\n".join(current_assistant_resp).strip() or "(작업 진행 중)"
                turns.append((current_user_prompt, asst_text))
                current_assistant_resp = []

            u_text = content
            if "<USER_REQUEST>" in u_text and "</USER_REQUEST>" in u_text:
                start = u_text.find("<USER_REQUEST>") + len("<USER_REQUEST>")
                end = u_text.find("</USER_REQUEST>")
                u_text = u_text[start:end].strip()
            current_user_prompt = u_text

        elif step_type == "PLANNER_RESPONSE" and isinstance(content, str) and content.strip():
            current_assistant_resp.append(content.strip())

    if current_user_prompt is not None:
        asst_text = "\n\n".join(current_assistant_resp).strip()
        if not asst_text:
            asst_text = "(수행 완료 및 보고 진행 중)"
        turns.append((current_user_prompt, asst_text))

    return turns


def get_project_mappings(project_dir: Path) -> tuple[str | None, str | None]:
    """현재 project_dir에 대응하는 (electron_project_id, sqlite_project_id)를 찾는다."""
    codex_home = get_codex_home()
    norm_proj = project_dir.resolve()
    electron_pid = None
    sqlite_pid = None

    # 1. Electron Global State에서 projectId 탐색
    gs_path = codex_home / ".codex-global-state.json"
    if gs_path.is_file():
        try:
            gs = json.loads(gs_path.read_text(encoding="utf-8"))
            for pid, pdata in gs.get("local-projects", {}).items():
                roots = [Path(r).resolve() for r in pdata.get("rootPaths", [])]
                if norm_proj in roots:
                    electron_pid = pid
                    break
        except Exception:
            pass

    # 2. SQLite project_roots에서 project_id 탐색
    db_path = codex_home / "state_5.sqlite"
    if db_path.is_file():
        try:
            conn = sqlite3.connect(db_path, timeout=5.0)
            try:
                cur = conn.cursor()
                cur.execute("SELECT project_id, path FROM project_roots")
                for pid, path_str in cur.fetchall():
                    if Path(path_str).resolve() == norm_proj:
                        sqlite_pid = pid
                        break
            finally:
                conn.close()
        except Exception:
            pass

    return electron_pid, sqlite_pid


def create_or_update_rollout(
    rollout_path: Path,
    *,
    thread_id: str,
    project_dir: Path,
    actor: str,
    turns: Sequence[tuple[str, str]],  # [(user_prompt, assistant_response), ...]
    now: datetime | None = None,
) -> None:
    rollout_path.parent.mkdir(parents=True, exist_ok=True)
    moment = now or datetime.now(timezone.utc)
    ts_iso = moment.isoformat().replace("+00:00", "Z")
    clean_cwd = str(project_dir.resolve())

    lines: list[dict[str, Any]] = []

    # 0. Session Meta (Codex Desktop 네이티브 포맷과 100% 일치)
    lines.append({
        "timestamp": ts_iso,
        "ordinal": 0,
        "type": "session_meta",
        "payload": {
            "session_id": thread_id,
            "id": thread_id,
            "timestamp": ts_iso,
            "cwd": clean_cwd,
            "originator": "Codex Desktop",
            "cli_version": "0.155.0-alpha.16.3",
            "source": "vscode",
            "thread_source": "user",
            "model_provider": "openai",
            "base_instructions": None,
            "history_mode": "paginated",
            "context_window": {"window_id": generate_uuidv7()},
        },
    })

    ordinal = 1
    for turn_idx, (user_prompt, assistant_resp) in enumerate(turns):
        turn_uuid = generate_uuidv7()
        user_msg_id = f"msg_{uuid.uuid4().hex}"
        asst_msg_id = f"msg_{uuid.uuid4().hex}"

        # 1. task_started
        lines.append({
            "timestamp": ts_iso,
            "ordinal": ordinal,
            "type": "event_msg",
            "payload": {
                "type": "task_started",
                "turn_id": turn_uuid,
                "started_at": int(moment.timestamp()),
                "model_context_window": 258400,
                "collaboration_mode_kind": "default",
            },
        })
        ordinal += 1

        # 2. user message
        lines.append({
            "timestamp": ts_iso,
            "ordinal": ordinal,
            "type": "response_item",
            "payload": {
                "type": "message",
                "id": user_msg_id,
                "role": "user",
                "content": [{"type": "input_text", "text": user_prompt}],
            },
        })
        ordinal += 1

        # 3. item_completed (user)
        lines.append({
            "timestamp": ts_iso,
            "ordinal": ordinal,
            "type": "event_msg",
            "payload": {
                "type": "item_completed",
                "thread_id": thread_id,
                "turn_id": turn_uuid,
                "item": {
                    "type": "UserMessage",
                    "id": f"item-{turn_idx * 2 + 1}",
                    "content": [{"type": "text", "text": user_prompt, "text_elements": []}],
                },
                "completed_at_ms": int(moment.timestamp() * 1000),
            },
        })
        ordinal += 1

        # 4. assistant message
        lines.append({
            "timestamp": ts_iso,
            "ordinal": ordinal,
            "type": "response_item",
            "payload": {
                "type": "message",
                "id": asst_msg_id,
                "role": "assistant",
                "content": [{"type": "output_text", "text": assistant_resp}],
                "phase": "final_answer",
            },
        })
        ordinal += 1

        # 5. item_completed (assistant)
        lines.append({
            "timestamp": ts_iso,
            "ordinal": ordinal,
            "type": "event_msg",
            "payload": {
                "type": "item_completed",
                "thread_id": thread_id,
                "turn_id": turn_uuid,
                "item": {
                    "type": "AgentMessage",
                    "id": f"item-{turn_idx * 2 + 2}",
                    "content": [{"type": "Text", "text": assistant_resp}],
                    "phase": "final_answer",
                },
                "completed_at_ms": int(moment.timestamp() * 1000),
            },
        })
        ordinal += 1

        # 6. task_complete
        lines.append({
            "timestamp": ts_iso,
            "ordinal": ordinal,
            "type": "event_msg",
            "payload": {
                "type": "task_complete",
                "turn_id": turn_uuid,
                "last_agent_message": assistant_resp,
            },
        })
        ordinal += 1

    content = "\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n"
    rollout_path.write_text(content, encoding="utf-8")


def register_thread_in_codex(
    *,
    thread_id: str,
    thread_name: str,
    rollout_path: Path,
    project_dir: Path,
    actor: str,
    preview_text: str = "",
    tokens_used: int = 0,
    now: datetime | None = None,
) -> None:
    codex_home = get_codex_home()
    moment = now or datetime.now(timezone.utc)
    ts_sec = int(moment.timestamp())
    ts_ms = int(moment.timestamp() * 1000)
    cwd_str = f"\\\\?\\{str(project_dir.resolve())}"

    electron_pid, sqlite_pid = get_project_mappings(project_dir)

    # 1. state_5.sqlite 갱신 (Desktop UI와 완전 호환)
    db_path = codex_home / "state_5.sqlite"
    if db_path.is_file():
        conn = sqlite3.connect(db_path, timeout=10.0)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO threads (
                        id, rollout_path, created_at, updated_at, source, model_provider,
                        cwd, title, sandbox_policy, approval_mode, tokens_used, has_user_event,
                        archived, cli_version, first_user_message, memory_mode, created_at_ms,
                        updated_at_ms, thread_source, preview, recency_at, recency_at_ms,
                        history_mode, name, is_pinned, originator, model, project_id, git_branch
                    ) VALUES (
                        :id, :rollout_path, :created_at, :updated_at, 'vscode', 'openai',
                        :cwd, :title, '{"type":"disabled"}', 'never', :tokens_used, 0,
                        0, '0.155.0-alpha.16.3', :first_msg, 'enabled', :created_at_ms,
                        :updated_at_ms, 'user', :preview, :recency_at, :recency_at_ms,
                        'paginated', :name, 0, 'Codex Desktop', 'gpt-5.6-sol', :project_id, 'main'
                    )
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        title = excluded.title,
                        preview = excluded.preview,
                        first_user_message = excluded.first_user_message,
                        updated_at = excluded.updated_at,
                        updated_at_ms = excluded.updated_at_ms,
                        recency_at = excluded.recency_at,
                        recency_at_ms = excluded.recency_at_ms,
                        rollout_path = excluded.rollout_path,
                        tokens_used = excluded.tokens_used,
                        project_id = excluded.project_id
                    """,
                    {
                        "id": thread_id,
                        "rollout_path": str(rollout_path),
                        "created_at": ts_sec,
                        "updated_at": ts_sec,
                        "cwd": cwd_str,
                        "title": thread_name,
                        "first_msg": preview_text[:300],
                        "preview": preview_text[:300],
                        "tokens_used": tokens_used,
                        "created_at_ms": ts_ms,
                        "updated_at_ms": ts_ms,
                        "recency_at": ts_sec,
                        "recency_at_ms": ts_ms,
                        "name": thread_name,
                        "project_id": sqlite_pid,
                    },
                )
        finally:
            conn.close()

    # 2. session_index.jsonl 갱신 (중복 방지 및 최상단 반영)
    idx_path = codex_home / "session_index.jsonl"
    entry = {
        "id": thread_id,
        "thread_name": thread_name,
        "updated_at": moment.isoformat().replace("+00:00", "Z"),
    }
    existing_lines: list[str] = []
    if idx_path.is_file():
        for line in idx_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip():
                try:
                    data = json.loads(line)
                    if data.get("id") != thread_id:
                        existing_lines.append(line)
                except Exception:
                    existing_lines.append(line)
    existing_lines.append(json.dumps(entry, ensure_ascii=False))
    idx_path.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")

    # 3. .codex-global-state.json 갱신 (Electron 데스크톱 사이드바 프로젝트 바인딩 핵심!)
    if electron_pid:
        gs_path = codex_home / ".codex-global-state.json"
        if gs_path.is_file():
            try:
                gs = json.loads(gs_path.read_text(encoding="utf-8"))

                # 3-1. thread-project-assignments 등록
                tpa = gs.setdefault("thread-project-assignments", {})
                tpa[thread_id] = {"projectKind": "local", "projectId": electron_pid}

                # 3-2. sidebar-project-thread-orders 정렬 목록 최상단 삽입
                spto = gs.setdefault("sidebar-project-thread-orders", {})
                proj_order = spto.setdefault(electron_pid, {"threadIds": []})
                tids = proj_order.setdefault("threadIds", [])
                if thread_id in tids:
                    tids.remove(thread_id)
                tids.insert(0, thread_id)

                # 원자적 쓰기
                tmp_gs = gs_path.with_suffix(".tmp")
                tmp_gs.write_text(json.dumps(gs, indent=2, ensure_ascii=False), encoding="utf-8")
                tmp_gs.replace(gs_path)
            except Exception:
                pass

    # 4. thread_history_1.sqlite 갱신 (대화 턴 및 메시지 렌더링용)
    th_path = codex_home / "thread_history_1.sqlite"
    if th_path.is_file():
        try:
            th_conn = sqlite3.connect(th_path, timeout=5.0)
            try:
                turn_uuid = generate_uuidv7()
                user_msg_id = f"msg_{uuid.uuid4().hex}"
                asst_msg_id = f"msg_{uuid.uuid4().hex}"
                with th_conn:
                    # thread_turns
                    th_conn.execute(
                        """
                        INSERT OR REPLACE INTO thread_turns (
                            thread_id, turn_id, rollout_ordinal, status, error_json,
                            started_at, completed_at, duration_ms, first_user_item_id,
                            final_agent_item_id, rollout_byte_offset, rollout_end_ordinal, rollout_end_byte_offset
                        ) VALUES (?, ?, 1, 'completed', NULL, ?, ?, 1000, ?, ?, 0, 10, 10000)
                        """,
                        (thread_id, turn_uuid, ts_sec, ts_sec, user_msg_id, asst_msg_id),
                    )
                    # thread_items (user)
                    user_json = json.dumps({
                        "type": "userMessage",
                        "id": user_msg_id,
                        "content": [{"type": "text", "text": preview_text, "text_elements": []}]
                    }, ensure_ascii=False)
                    th_conn.execute(
                        """
                        INSERT OR REPLACE INTO thread_items (
                            thread_id, turn_id, item_id, rollout_ordinal, created_at_ms, item_json, item_type, updated_at_ordinal
                        ) VALUES (?, ?, ?, 2, ?, ?, 'userMessage', 2)
                        """,
                        (thread_id, turn_uuid, user_msg_id, ts_ms, user_json),
                    )
                    # thread_history_projection_state
                    th_conn.execute(
                        """
                        INSERT OR REPLACE INTO thread_history_projection_state (
                            thread_id, next_rollout_byte_offset, next_rollout_ordinal
                        ) VALUES (?, 10000, 11)
                        """,
                        (thread_id,),
                    )
            finally:
                th_conn.close()
        except Exception:
            pass

    # 5. queue_1.sqlite 갱신 (Codex Desktop 앱 실시간 리비전 감지 트리거)
    q_path = codex_home / "queue_1.sqlite"
    if q_path.is_file():
        try:
            q_conn = sqlite3.connect(q_path, timeout=5.0)
            try:
                with q_conn:
                    q_conn.execute(
                        "INSERT INTO queued_thread_revisions (thread_id) VALUES (?)",
                        (thread_id,),
                    )
            finally:
                q_conn.close()
        except Exception:
            pass


def publish_codex_thread(
    *,
    actor: str,
    task_name: str,
    turns: Sequence[tuple[str, str]],  # [(prompt, response), ...]
    project_dir: Path | None = None,
    thread_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Antigravity / Claude Code 세션 대화를 Codex 프로젝트 대화창(Thread)으로 발행한다."""
    proj = project_dir or Path.cwd()
    tid = thread_id or generate_uuidv7()
    norm_actor = "agy" if actor.lower() in ("agy", "antigravity") else "claude"
    tname = format_thread_name(norm_actor, task_name)
    moment = now or datetime.now(timezone.utc)

    # 롤아웃 경로 결정 (~/.codex/sessions/YYYY/MM/DD/rollout-YYYY-MM-DDTHH-MM-SS-<uuid>.jsonl)
    ts_file = moment.strftime("%Y-%m-%dT%H-%M-%S")
    rollout_dir = get_codex_home() / "sessions" / moment.strftime("%Y") / moment.strftime("%m") / moment.strftime("%d")
    rollout_path = rollout_dir / f"rollout-{ts_file}-{tid}.jsonl"

    # 파일 작성
    create_or_update_rollout(
        rollout_path,
        thread_id=tid,
        project_dir=proj,
        actor=norm_actor,
        turns=turns,
        now=moment,
    )

    total_chars = sum(len(p) + len(r) for p, r in turns)
    approx_tokens = total_chars // 4
    first_prompt = turns[0][0] if turns else ""

    # DB 및 색인, Global State 등록
    register_thread_in_codex(
        thread_id=tid,
        thread_name=tname,
        rollout_path=rollout_path,
        project_dir=proj,
        actor=norm_actor,
        preview_text=first_prompt,
        tokens_used=approx_tokens,
        now=moment,
    )

    return {
        "ok": True,
        "thread_id": tid,
        "thread_name": tname,
        "rollout_path": str(rollout_path),
        "actor": norm_actor,
        "turns_count": len(turns),
    }
