```contract
work_id: U35-O2
worker: local
goal: In `docs/24_ollama_working_manual.md`, replace the text `(Ollama 기반 교환원)` with `(규칙 기반 교환원·모델 호출 없음)`.
inputs:
- docs/24_ollama_working_manual.md sha256=d94f61af26fc4cdddbce2d295b5eaab32769a000ec8a43d46af18adafe51c25d
allow:
- docs/24_ollama_working_manual.md
acceptance: python -c "import pathlib;t=pathlib.Path('docs/24_ollama_working_manual.md').read_text(encoding='utf-8');assert '(규칙 기반 교환원·모델 호출 없음)' in t and '(Ollama 기반 교환원)' not in t and len(t.splitlines())==169"
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: codex
timeout_s: 300
remote_budget_tokens: 0
```

## Role and reason

- You are a calculator: one exact text replacement, no judgement. Codex judges the result.
- Reason (for the record, not for you to act on): the sentinel runs deterministic rules and never calls a model, so the
  label "(Ollama 기반 교환원)" in the diagram of `docs/24_ollama_working_manual.md` is wrong (docs/36 §2-2).
- Measurement purpose: one sample of the local 7b model under the new harness (manual lint, scope, deletion guard).

## Instructions for the worker

1. The file has 169 lines, so answer with one ===EDIT block (SEARCH/REPLACE), not the whole file.
2. SEARCH must be exactly this one line (copy it byte for byte, including the leading spaces and box characters):

             │  (Ollama 기반 교환원)   │

3. REPLACE with the same line where `(Ollama 기반 교환원)` becomes `(규칙 기반 교환원·모델 호출 없음)`.
4. Do not touch any other line. The line count must stay 169.

## Output

- Reply with ===FILE / ===EDIT blocks only. No explanations. Do not claim success; the acceptance command decides.
