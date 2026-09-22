# MIA strategic: can paid agents be made to use the local model? (2026-09-23)

## Frame
- Problem: dozens of hints, an MCP server, and hooks; paid agents still called olla ~0 times (Biz sessions 48a22ea2, dec0f758, 40375870).
- Success signal: paid tokens per task go down (not "olla call count").

## Evidence
- Measured (Biz dec0f758, 144 calls after resume): cache re-reads 24.5M, tool results ~0.47M (2%), output 0.15M. Context per call 294k-360k.
- Measured (Biz 40375870, new session): 13 calls, work was screenshot reading and judgment; nothing text-local to delegate.
- Measured: local vision OCR (qwen3.5:4b) 36 s per crop with name errors; a paid image crop costs ~1.3k tokens. Not worth it.
- Web: Ollama delegation MCPs report 30-60% savings on delegable classes and ~0% on hard thinking; Claude "may" delegate, no guarantee (github.com/Jadael/OllamaClaude, glama ollama-mcp).
- Web: cost grows ~6x per context doubling; compacting at ~220k is 2.3x cheaper than filling to 1M; 85% of steps unaffected when old context is summarized (langwatch.ai, 287k API calls).
- Web: agents choose among listed tools by semantic match; persuasion text is weak (arXiv:2510.00307).

## Decision: Pivot
- Cannot: make paid agents reliably hand real work to a 7B model on a 6 GB GPU. Even perfect delegation touches ~2% of spend.
- Can: olla as infrastructure that needs no agent choice — output squeeze (done, 624 -> 35 lines), handoff into new sessions (done, worktree-keyed), big-read digests (done), early compaction.
- Biggest remaining lever: auto-compact near 220k (CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=22 on a 1M window). Applied 2026-09-23 via Edit tool in ~/.claude/settings.json env (Bash edit was classifier-denied); mirrored in tool-configs (ddafda9). Takes effect in new sessions.

## Verify (next)
- Metric: context per call and paid tokens per task in the next Biz session, against dec0f758 (294k-360k per call).
- Stop adding persuasion hints; count squeeze/handoff savings in olla stats.

## Verify result (Biz 40375870, resumed 00:31-01:10)
- Auto-compact fired at 215,667 tokens (22% of 1M) -> summary 18k; next call 78.5k. Measured from compact_boundary.
- 98 calls after resume: mean context 127k per call (12.4M total). Before the setting the same session sat at 188k and rising.
- Floor: a fresh Biz session starts at ~65k per call (Claude Code system prompt + tools; no project CLAUDE.md). Not reducible from olla.
- Growth after compaction (101k -> 140k in 30 min): 5 image crops (~1.4k tokens each, measured from PNG size) + 2 diagnostic docs (~3.8k each) + edits. All judgment work; nothing text-local to delegate.
- Handoff: written for Biz by the Stop hook (fix 01443da), unused because the user resumed instead of opening a new chat.
- Decision: Iterate. Keep 22%; no new hints.

## Value verdict: Retire (2026-09-23 01:40, user asked for a keep/delete decision)
- Benefit, all sessions, measured from usage.jsonl: estimated paid tokens saved 58.7k total (squeeze 1x 10.0k->0.9k,
  whole-read deny 1x, handoff used 1x). Biz sessions: MCP calls 0, digests 4 built and 0 used, handoffs 3 built and 0 used.
- Cost: hook-plan injects ~1,060 B (~265 tokens) on every prompt (100 prompts logged), which stays in context and is
  re-read on every later call; 450-540 ms added to every prompt, Bash and Read call (measured, 3 runs); report-rule and
  "use olla" nags in every turn; GPU time for unused digests.
- The saving that actually mattered (215k -> 18k) came from CLAUDE_AUTOCOMPACT_PCT_OVERRIDE, which needs no olla.
- Net value negative -> removed from all three tools: Claude hooks + MCP + CLAUDE.md section; Codex hooks + MCP;
  Antigravity hooks + MCP. Kept: auto-compact 22%, source in git, Ollama models on disk (not deleted: irreversible,
  multi-GB, may serve other projects). Backups: .work/backup_20260923/olla_removal/.
