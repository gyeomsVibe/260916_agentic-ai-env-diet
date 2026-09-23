# Rethink: how the three tools should use Ollama (2026-09-23)

## Why the old logic failed
Old logic = "a paid agent chooses to hand work to a local tool" (hints, MCP, hooks). Measured result: 0 MCP calls in
Biz sessions, net value negative, retired (see mia_strategic_20260923.md). Any design that needs the paid agent's
choice repeats that failure.

## Inverted logic
The paid agent never delegates. The local model runs the whole tool loop itself, and a machine check decides:
1. Local lane: the same agent harness (Claude Code) runs on the local model. The tool loop (read, edit,
   run tests) is Claude Code's own, not a single-shot patch writer.
2. Test decides, not the agent: every lane task carries an acceptance command; the test file is write-protected.
   Pass = done at 0 paid tokens. Fail = escalate to a paid tool with the diff and log (cascade, FrugalGPT pattern).
3. Who routes: the pilot (`pilot run --worker local`), already the sanctioned delegation path in AGENTS.md, and
   the user directly when paid quota is exhausted (9/22-9/24 situation).

## Experiments (all local, 0 paid tokens)
- E1 Ollama Anthropic endpoint (/v1/messages, Ollama 0.34.2) with one tool:
  qwen2.5-coder:7b and :3b emit the call as plain text (no tool_use) -> unusable for an agent loop.
  qwen3.5:4b emits a real tool_use block (14.5 s).
- E2 Full Claude Code on qwen3.5:4b, default context: prompt truncated at 4,098 tokens, no work done.
- E3 Same with num_ctx 32768 (model qwen3.5-32k, 3.5 GB, fully in 6 GB VRAM): prompt is 34,475 tokens
  (system prompt + tools + global rules) > 32k -> truncated, wrong action, 164 s.
- E4 `claude -p --bare --tools Read,Edit,Bash --strict-mcp-config --disable-slash-commands --system-prompt <1 line>`:
  prompt ~2k tokens; bug fixed and test passed in 27 s.
- E5 Bench, 3 tasks (fix bug, add function, rename across 3 files):
  - unprotected tests, 1 run each: 1/3. Failures: overwrote a file (dropped `upper`); renamed correctly but also
    edited the test file (test tampering).
  - test file protected (`--disallowedTools "Edit(test_t.py)"`), 2 runs each: 5/6 pass, 17-43 s per task.
  Raw rows: bench_qwen3.5-32k.json. Script: .work/olla_rethink_20260923/lane_bench.py (disposable).

## What this means
- The local model can do small, well-specified coding tasks end to end when (a) the harness prompt is cut to ~2k
  tokens (bare mode), (b) the model supports native tool_use (qwen3.5:4b yes, qwen2.5-coder no), and (c) tests are
  write-protected. Pass rate 5/6 on toy tasks; on real repo tasks: UNMEASURED.
- Paid-token saving per Biz session stays small: Biz work is screen reading and judgment (~2% delegable, measured).
  The lane's value is mechanical coding tasks and quota outages, not judgment-heavy sessions.
- Codex `--oss` / local profile and Antigravity custom models: UNKNOWN (codex exec is not launched from here;
  Antigravity returns 9/24).

## Next (proposed, not done)
1. Replace the pilot's local worker (single-shot, qwen2.5-coder:7b) with the lane (bare Claude Code, qwen3.5-32k,
   protected acceptance files, one retry), then A/B both on the existing pilot tasks (P01-P04, B22).
2. Gate: lane pass rate >= the old worker's and wall time <= 3x, on at least 10 real tasks.
