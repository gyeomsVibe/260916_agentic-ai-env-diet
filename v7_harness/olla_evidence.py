"""Source-anchored, fail-closed Ollama extraction entrypoint and validator.

Ensures LLM output is strictly single-object JSON whose string values are
exact contiguous substrings of the verified evidence file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
from pathlib import Path
from typing import Any

from v7_harness.adapters import ollama_worker as worker


def validate_response(raw: str, evidence: str, keys: list[str]) -> dict[str, str]:
    """Validate that raw is a single JSON object containing exact keys with substrings of evidence.

    Rejects markdown fences, duplicate/missing/extra keys, empty/non-string values,
    and any value that is not an exact contiguous substring of evidence.
    Returns a dict ordered exactly as keys; raises ValueError on rejection.
    """
    if not isinstance(raw, str):
        raise ValueError("raw response must be a string")
    if not isinstance(evidence, str):
        raise ValueError("evidence must be a string")
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        raise ValueError("keys must be a list of strings")
    if len(keys) != len(set(keys)):
        raise ValueError("keys list must not contain duplicates")

    raw_trimmed = raw.strip()
    if raw_trimmed.startswith("```") or raw_trimmed.endswith("```") or "```" in raw:
        raise ValueError("Markdown fences are not permitted")
    if not (raw_trimmed.startswith("{") and raw_trimmed.endswith("}")):
        raise ValueError("Response must be a single JSON object")

    def _reject_duplicates(pairs: list[tuple[Any, Any]]) -> dict[str, Any]:
        d: dict[str, Any] = {}
        for k, v in pairs:
            if not isinstance(k, str):
                raise ValueError("JSON object keys must be strings")
            if k in d:
                raise ValueError(f"Duplicate key: {k!r}")
            d[k] = v
        return d

    try:
        data = json.loads(raw, object_pairs_hook=_reject_duplicates)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Response must be a JSON object")

    if set(data.keys()) != set(keys) or len(data) != len(keys):
        raise ValueError(f"Keys mismatch: expected {keys}, got {list(data.keys())}")

    result: dict[str, str] = {}
    for k in keys:
        val = data[k]
        if not isinstance(val, str):
            raise ValueError(f"Value for key {k!r} must be a string, got {type(val).__name__}")
        if not val:
            raise ValueError(f"Value for key {k!r} must not be empty")
        if val not in evidence:
            raise ValueError(f"Value for key {k!r} is not an exact contiguous substring of evidence")
        result[k] = val

    return result


def _read_file(path_str: str, name: str) -> tuple[int, bytes, str]:
    path = Path(path_str)
    if path.is_symlink():
        sys.stderr.write(f"Preflight error: {name} must not be a symlink: {path}\n")
        return 2, b"", ""
    if not path.is_file():
        sys.stderr.write(f"Preflight error: {name} must be a regular file: {path}\n")
        return 2, b"", ""
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        sys.stderr.write(f"Preflight error: failed to read {name} {path}: {exc}\n")
        return 2, b"", ""
    if len(raw_bytes) == 0:
        sys.stderr.write(f"Preflight error: {name} must not be empty: {path}\n")
        return 2, b"", ""
    try:
        content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        sys.stderr.write(f"Preflight error: {name} must be valid UTF-8: {exc}\n")
        return 2, b"", ""
    return 0, raw_bytes, content


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Source-anchored Ollama extraction entrypoint")
    parser.add_argument("--manual", required=True, help="Path to manual file")
    parser.add_argument("--evidence", required=True, help="Path to evidence file")
    parser.add_argument("--sha256", required=True, help="Expected SHA-256 hex digest of evidence")
    parser.add_argument("--keys", required=True, help="Comma-separated list of keys to extract")
    parser.add_argument("--prompt", required=True, help="Task prompt")
    parser.add_argument("--model", default=worker.DEFAULT_MODEL, help="Model name")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout in seconds (1..120)")

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    if not (1 <= args.timeout <= 120):
        sys.stderr.write(f"Preflight error: invalid --timeout {args.timeout} (must be between 1 and 120)\n")
        return 2

    keys = [k.strip() for k in args.keys.split(",") if k.strip()]
    if not keys:
        sys.stderr.write("Preflight error: --keys must contain at least one non-empty key\n")
        return 2
    if len(keys) != len(set(keys)):
        sys.stderr.write("Preflight error: duplicate keys specified in --keys\n")
        return 2

    code, manual_bytes, manual_content = _read_file(args.manual, "manual")
    if code != 0:
        return code

    code, evidence_bytes, evidence_content = _read_file(args.evidence, "evidence")
    if code != 0:
        return code

    pre_sha = hashlib.sha256(evidence_bytes).hexdigest()
    if pre_sha.lower() != args.sha256.strip().lower():
        sys.stderr.write(f"Preflight error: SHA-256 mismatch for {args.evidence}: expected {args.sha256}, got {pre_sha}\n")
        return 2

    combined_prompt = (
        f"=== MANUAL ===\n"
        f"{manual_content}\n\n"
        f"=== EVIDENCE ===\n"
        f"{evidence_content}\n\n"
        f"=== TASK ===\n"
        f"{args.prompt}\n\n"
        f"Respond with a single JSON object containing keys: {json.dumps(keys)}.\n"
        f"Every value must be an exact contiguous substring copied from EVIDENCE.\n"
        f"Do not include markdown fences, comments, or extra text.\n"
    )

    # U34: constrain the shape at generation time (U29 failed on a code fence around correct JSON). The substring
    # check below still decides whether the values are true.
    schema = {
        "type": "object",
        "properties": {key: {"type": "string"} for key in keys},
        "required": keys,
        "additionalProperties": False,
    }
    try:
        raw_response, usage = worker._generate(args.model, combined_prompt, args.timeout, fmt=schema)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        sys.stderr.write(f"Provider/network error calling Ollama worker: {exc}\n")
        return 1

    evidence_path = Path(args.evidence)
    if evidence_path.is_symlink() or not evidence_path.is_file():
        sys.stderr.write(f"Post-call error: evidence file invalid: {evidence_path}\n")
        return 5

    try:
        post_bytes = evidence_path.read_bytes()
    except OSError as exc:
        sys.stderr.write(f"Post-call error: failed to read evidence after model call: {exc}\n")
        return 5

    post_sha = hashlib.sha256(post_bytes).hexdigest()
    if post_sha.lower() != args.sha256.strip().lower():
        sys.stderr.write(f"Post-call error: SHA-256 mismatch for {evidence_path}: expected {args.sha256}, got {post_sha}\n")
        return 5

    try:
        validated = validate_response(raw_response, evidence_content, keys)
    except ValueError as exc:
        sys.stderr.write(f"Validation error: {exc}\n")
        return 5

    sys.stdout.write(json.dumps(validated, separators=(",", ":"), ensure_ascii=False) + "\n")

    usage_dict = usage if isinstance(usage, dict) else {}
    receipt = {
        "status": "PASS",
        "model": args.model,
        "input_tokens": int(usage_dict.get("input_tokens", 0)),
        "output_tokens": int(usage_dict.get("output_tokens", 0)),
        "sha256": pre_sha,
    }
    sys.stderr.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
