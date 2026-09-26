# U46-J3: Antigravity Verdict Integration & Zero-Relay Design Consult

## Recommendation
- **Primary Architecture**: Direct execution of **Option A (`pilot judge --judge agy`)** triggered synchronously by Claude Code upon dry-run pass, backed by **Option D (`UAOS Sentinel 30m`)** as the asynchronous 0-token fallback for unattended mailbox requests.
- **Why**:
  1. **Zero human relay**: Removes the manual IDE copy-paste bottleneck entirely.
  2. **Non-destructive & safe**: `agy` runs headlessly in read-only mode (`plan` mode or no write permissions), never requiring `--dangerously-skip-permissions` on source.
  3. **Attributable & binding**: The harness calls `agy` with `--json-schema`, captures `conversation_id` and sha256 of the verdict JSON, and deterministically executes `--approve` only when `verdict == APPROVE` and `bundle_id` matches.
  4. **Strict cost control**: Budget set to 100,000 tokens (measured baseline is ~71k tokens). Single call per task; no retry loops.
- **First Smallest Step**: Implement `pilot judge --judge agy` command and test schema validation with a mock/dry-run harness test before wiring to live pilot approval.

## Options
- **Option A (`pilot judge --judge agy`)**:
  - *Feasibility*: HIGH. Pilot harness runs acceptance tests locally, formats a single prompt with contract manual + diff + test outcome, and invokes `agy -p ... --output-format json --json-schema <schema>` in read-only mode. Deterministic code performs the actual promotion upon valid JSON `APPROVE`.
  - *Token Cost*: ~70,000–90,000 tokens per invocation (basis: live U46-J1 run measured 71,299 tokens [60,045 input + 11,254 output]). Budget cap must be set at 100,000 tokens under B85.
  - *Failure Modes*: Token budget exhaustion if full repo context is indexed (mitigate by isolating `--add-dir` to staged run folder); transient 503/429 provider errors; schema mismatch if verdict is unparseable.
- **Option B (`agy headless executes approve command directly`)**:
  - *Feasibility*: UNFEASIBLE / VIOLATES SAFETY. `agy` headless (`-p`) has no per-command allowlist flag. Executing shell commands (`pilot run --approve`) requires `--dangerously-skip-permissions`, which UAOS rules strictly forbid on source workspaces.
  - *Token Cost*: ~75,000–95,000 tokens.
  - *Failure Modes*: Hangs waiting for interactive confirmation; security policy violation if forced; permission denied in sandboxed runs.
- **Option C (`agy remote-control daemon / IDE agent mailbox watcher`)**:
  - *Feasibility*: UNFEASIBLE / VIOLATES UAOS CORE INVARIANTS. An active IDE agent or polling remote-control daemon violates "no paid polling; waiting belongs to 0-token sentinel/mailbox".
  - *Token Cost*: Continuous drain if LLM-driven; uncontrolled process lifecycle.
  - *Failure Modes*: Background socket disconnection, IDE sleep/hang, memory leaks, unmonitored background state drift.
- **Option D (`0-token Sentinel launches Option A upon detecting JUDGE_REQUEST`)**:
  - *Feasibility*: HIGH. `UAOS Sentinel 30m` (Task Scheduler) runs at 0 token cost, inspects `.coord/mailbox/inbox/*_judge_*.json`, and triggers `pilot judge --judge agy` exactly once per request.
  - *Token Cost*: 0 tokens while idle; ~70k–90k tokens on one-shot trigger.
  - *Failure Modes*: Schedule latency (up to 30 min unless triggered immediately); duplicate triggering if mailbox ACK is not atomic.

## Facts about agy
- **CLI Commands & Flags**: `agy -p` (print/headless), `--output-format json`, `--json-schema <file>`, `--conversation <id>`, `--add-dir <dir>`, and `--print-timeout <sec>` are verified working flags (v1.x / 1.2.4).
- **Execution Modes**: `--mode plan` enforces read-only planning without code generation or file writing.
- **Permission Model**: There is NO flag for a fine-grained, per-command shell execution whitelist in headless mode. The only bypass is `--dangerously-skip-permissions`, which is strictly banned on source trees.
- **Context Overhead**: `agy` indexes workspace files in `--add-dir`, producing a baseline context load of ~50,000–60,000 tokens before prompt evaluation. Passing the repository root blows token budgets; passing a staged subfolder is required.
- **Envelope Semantics**: `agy` returns a JSON envelope containing `status`, `conversation_id`, `usage`, and `structured_output`. An exit code of 0 can accompany `status=ERROR` (e.g. 503); the JSON envelope and stderr hash are the true sources of truth.
- **Daemon / Remote Control**: `agy remote-control start|status|stop` exists, but is designed for external IDE attachment, not autonomous headless polling. Other claimed scheduling features are UNKNOWN or absent.

## Risks
- **Forgery Risk**: Because OS accounts are shared (B83), an actor name `antigravity` in a CLI flag is not proof. Mitigated by storing `judge_conversation_id`, the full stdout envelope, and the sha256 hash of the structured verdict in the pilot receipt.
- **Runaway Cost Risk**: Calling `agy` with broad directory scope or without a strict token cap can consume 100k+ tokens per call. Mitigated by setting `--print-timeout 600s`, enforcing `--budget 100000`, single-call semantics (zero retries), and scoping `--add-dir` to the run directory.
- **Scope Creep / Unintended Edits**: Running `agy` without read-only restrictions could allow unintended modifications. Mitigated by keeping `agy` strictly in `--mode plan` with structured output only, leaving filesystem writes to the deterministic harness.

## Daemon claim
- **Status**: **NOT_FOUND**.
- **Evidence**: Inspection of Windows Task Scheduler (`schtasks`) and active system processes shows no recurring `*/10` Antigravity task or daemon. The only registered Antigravity task is `Antigravity Daily Update` (an application updater). Other scheduled tasks are `UAOS Sentinel 30m`, `UAOS Claude Monitor 30m`, and `UAOS_RSI_Watch_39b238e0`.
- **Conclusion**: The autonomous `*/10 * * * *` daemon referenced in earlier process maps does not exist in the operating system. It was an unverified specification or paper design. Autonomous scheduled work relies entirely on the 0-token `UAOS Sentinel` task.
