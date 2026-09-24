```contract
work_id: U35-O2
worker: local
goal: In `docs/24_ollama_working_manual.md`, replace the text `(Ollama 기반 교환원)` with `(규칙 기반 교환원·모델 호출 없음)`.
inputs:
- docs/24_ollama_working_manual.md sha256=07c08ff87d114781b1a06dc427ba6b90a3fa7ffa01af9ef8fb8177e18027b8f0
allow:
- docs/24_ollama_working_manual.md
acceptance: python -c "import pathlib;t=pathlib.Path('docs/24_ollama_working_manual.md').read_text(encoding='utf-8');assert '(규칙 기반 교환원·모델 호출 없음)' in t and '(Ollama 기반 교환원)' not in t and len(t.splitlines())==169"
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: codex
timeout_s: 300
remote_budget_tokens: 0
```

## Windows input byte adaptation

The original U35-O2 manual pins the LF Git blob (`d94f61af...`), but this Windows checkout uses CRLF (`core.autocrlf=true`). This manual pins the verified checkout bytes without weakening the allowed file or acceptance test. The exact replacement and independent judge are unchanged.

## Worker instructions

One exact text replacement only. SEARCH must be the line below, including its spaces and box characters:

             │  (Ollama 기반 교환원)   │

REPLACE must preserve the line except for `(규칙 기반 교환원·모델 호출 없음)`. Output one ===EDIT block, no explanation or success claim. Keep 169 lines.
