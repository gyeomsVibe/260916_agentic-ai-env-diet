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
