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

## A/B result (2026-09-23, step 2; commit 985b8bf adds --worker lane)
10 tasks, hidden acceptance written only after the worker exits, 1 run each, same prompt and pilot protocol.
Script and rows: .work/lane_ab_20260923/ab.py, ab_rows_*.json (disposable). First local arm was void (bench
lacked PYTHONPATH, which the pilot sets in control.py:85); rerun with it.
- local (one-shot qwen2.5-coder:7b): 6/10, 51.8 s total.
- lane (tool loop qwen3.5-32k): 9/10, 218.4 s total (4.2x). Failed fix_off_by_one.
- Gate (pass >= local AND wall <= 3x): pass yes, wall NO -> lane as a replacement FAILS the gate.
- Cascade local -> lane on failure, computed from the same rows (not run end to end): 10/10, 141.5 s (2.7x).
  The 4 local failures (add_default_arg, rename_across, const_extract, fix_import_bug) all passed on lane.
- Limits: toy-size tasks written by me, n=1 per cell, order effect (lane ran first). Real repo tasks: UNMEASURED.

## Step 3: cascade end to end through the real pilot (2026-09-23)
`pilot run --worker cascade`: local first, lane (task `<ID>-lane`) only on REWORK. Script .work/lane_ab_20260923/e2e.py,
hidden acceptance outside the source. Bugs found on the way (all fixed, regression tests added):
- `--worker local` was BLOCKED on every pilot run: the adapter is started by path without PYTHONPATH (ModuleNotFoundError).
- lane BLOCKED/VALIDATION: fractional `elapsed_s` in usage fails the pilot's validate_usage; empty response too.
- EXTERNAL_WRITE on `ntuser.dat.LOG2` (Windows hive log at home root, flushed by the OS): now excluded; ntuser.dat stays.
Result, 10 tasks:
- local: 6/10 PASS, 693 s (includes one 601 s timeout on const_extract while other GPU work ran; ~91 s without it).
- cascade: 9/10 PASS, 224 s; 4 tasks escalated to lane, 3 of them passed. The 10th was BLOCKED by EXTERNAL_WRITE on
  ~/.claude/settings.json, written by the desktop app at 14:40 (not the worker; the guard is right to stop it).
- Gate (pass >= local, wall <= 3x): PASS. Wall ratio 0.32x against the measured local total, 2.5x against local
  without its timeout outlier. Real repo tasks: still UNMEASURED.

## Local router (anytime delegation without the agent choosing), 2026-09-23
v7_harness/local_router.py: a proxy on ANTHROPIC_BASE_URL. Main-model requests pass through (OAuth header untouched);
requests for a marker model (`local-qwen`, set via CLAUDE_CODE_SUBAGENT_MODEL / ANTHROPIC_DEFAULT_HAIKU_MODEL /
ANTHROPIC_SMALL_FAST_MODEL) go to Ollama with the tool list pruned to Read/Grep/Glob/Bash/Edit/Write.
- Observe run without markers: 0 haiku requests; subagents and side calls all used the main model.
- With markers: Explore subagent turns went local (2 local, answer correct: cli.py:481), 39-64 s per local turn vs
  ~5 s upstream. Others fell back upstream because the pilot bench held the GPU. 4 early fallbacks returned 400
  (cause not logged then; error head now logged).
- Not enabled globally: that needs ANTHROPIC_BASE_URL in ~/.claude/settings.json (user approval: settings change).

## Next (proposed, not done)
0. Done above: cascade implemented and gated. Remaining: real repo tasks.
1. Implement the cascade in the pilot (local first, lane on REWORK) and run it end to end on the same 10 tasks
   plus real repo tasks; gate unchanged.
1. Replace the pilot's local worker (single-shot, qwen2.5-coder:7b) with the lane (bare Claude Code, qwen3.5-32k,
   protected acceptance files, one retry), then A/B both on the existing pilot tasks (P01-P04, B22).
2. Gate: lane pass rate >= the old worker's and wall time <= 3x, on at least 10 real tasks.
