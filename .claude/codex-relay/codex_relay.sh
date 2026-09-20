#!/usr/bin/env bash
# Claude -> Codex relay.  Usage: codex_relay.sh check | send <session_id> <note-file-in-docs/claude-assist>
P="D:/D_Workspace_NB/-agentic-ai-workspace/260916_agentic-ai-env-diet"
DIR="$P/.work/codex-relay"; mkdir -p "$DIR"; SENT="$DIR/sent.log"; [ -f "$SENT" ] || : > "$SENT"
sess_file() { ls -t ~/.codex/sessions/*/*/*/*"$1"*.jsonl 2>/dev/null | head -1; }
case "$1" in
  check)
    for f in $(ls -t ~/.codex/sessions/*/*/*/*.jsonl 2>/dev/null | head -8); do
      grep -q '260916_agentic-ai-env-diet' <(head -c 600 "$f") || continue
      id=$(head -c 400 "$f" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
      echo "session=$id idle_s=$(( $(date +%s) - $(stat -c %Y "$f") ))"
    done | sort -u
    for n in "$P"/docs/claude-assist/*.md; do grep -qxF "$(basename "$n")" "$SENT" || echo "pending=$(basename "$n")"; done
    ;;
  send)
    f=$(sess_file "$2"); age=$(( $(date +%s) - $(stat -c %Y "$f") ))
    [ "$age" -lt 300 ] && { echo "BUSY idle_s=$age"; exit 3; }
    msg="[Claude 지원] docs/claude-assist/$3 를 읽고 현재 단계에 반영할 항목만 반영해줘. 사용자 제안 전제는 유지하고 구현 보강만 해. 7줄 이내로 보고해."
    cd "$P" && codex exec resume --skip-git-repo-check "$2" "$msg" -o "$DIR/last_$3.txt" > "$DIR/run_$3.log" 2>&1
    rc=$?; [ $rc -eq 0 ] && echo "$3" >> "$SENT"; grep -q "active writer" "$DIR/run_$3.log" && echo "LOCKED_BY_APP"
    echo "exit=$rc"; cat "$DIR/last_$3.txt" 2>/dev/null
    ;;
esac
