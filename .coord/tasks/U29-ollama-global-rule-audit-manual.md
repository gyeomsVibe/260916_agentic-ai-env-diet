# U29 Ollama global-rule audit call contract

- Work ID: U29_OLLA_RULE_AUDIT. Goal: copy three exact source facts; do not infer intent or recommend deployment.
- Input: this manual and `.work/u29_global_rule_evidence.md`, supplied with `-f` in this order. Caller records SHA-256 before invocation.
- Output: exactly one JSON object with keys `version_quote`, `live_quote`, `title_quote`. Each value must be an exact, contiguous quotation from the evidence file; no path, URL, explanation, or markdown outside JSON.
- Allowed writes: none. Forbidden: inventing files, changing rules, deciding ownership or PASS, contacting a service.
- Limit: local `qwen2.5-coder:7b`, one call, 60-second timeout. Stop if the output is malformed or any value is not a substring of the evidence file.
- Acceptance: caller parses JSON and checks all three strings are nonempty substrings of the input bytes decoded as UTF-8. Codex alone decides the deployment.

This narrow copy-only operation is intentional: the previous U28 extraction invented filenames twice even after receiving a manual. Failed output is discarded and recorded; no automatic retry or escalation of authority.
