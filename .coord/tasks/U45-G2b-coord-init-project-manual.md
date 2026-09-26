```contract
work_id: U45-G2b
worker: apply
goal: coord init writes a big-picture project manual template and names the contract manual path
inputs:
- v7_harness/cli.py sha256=01090c77ae2cf0cb09a9055713feb97532cf4bc65477fa49196740d869023def
allow:
- v7_harness/cli.py
- tests/test_u45_coord_init_manual.py
acceptance: python -m unittest tests.test_u45_coord_init_manual tests.test_u42_rsi_release tests.test_u44_claude_contract
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: antigravity
timeout_s: 300
remote_budget_tokens: 0
```

## Instructions for the worker

## Instructions for the worker

U45 G2 (2026-09-26, Claude acting conductor): every UAOS project must start with a big-picture project manual, and
each delegation with a small contract manual that is passed as the call input. `coord init` created only PLAN.md, so a
new project had no place for the big picture. The new test is red on the current code (1 failure, 1 error).
===FILE: tests/test_u45_coord_init_manual.py===
"""U45 G2: a new UAOS project starts with a big-picture project manual template next to the plan, and `coord init`
tells the conductor where the small per-delegation contract manuals go. Idempotent: an edited manual is never overwritten."""

import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from v7_harness import cli


def run_init(project: Path) -> dict:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.cmd_coord_init(argparse.Namespace(project=str(project)))
    assert code == 0
    return json.loads(out.getvalue())


class CoordInitProjectManualTest(unittest.TestCase):
    def test_init_creates_project_manual_template_with_required_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_init(Path(tmp))
            manual = Path(tmp) / ".coord" / "PROJECT_MANUAL.md"
            self.assertTrue(manual.is_file())
            self.assertIn(".coord/PROJECT_MANUAL.md", result["created"])
            text = manual.read_text(encoding="utf-8")
            for section in ("## Goal", "## Scope", "## Forbidden", "## Gates", "## Workers", "## Judge"):
                self.assertIn(section, text)

    def test_init_points_to_contract_manual_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_init(Path(tmp))
            self.assertEqual(result["contract_manuals"], ".coord/tasks/<work_id>-manual.md")
            self.assertTrue(any("PROJECT_MANUAL.md" in step for step in result["next"]))

    def test_init_never_overwrites_an_edited_project_manual(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_init(Path(tmp))
            manual = Path(tmp) / ".coord" / "PROJECT_MANUAL.md"
            manual.write_text("edited by the conductor\n", encoding="utf-8")
            result = run_init(Path(tmp))
            self.assertEqual(manual.read_text(encoding="utf-8"), "edited by the conductor\n")
            self.assertNotIn(".coord/PROJECT_MANUAL.md", result["created"])


if __name__ == "__main__":
    unittest.main()


===EDIT: v7_harness/cli.py===
<<<<<<< SEARCH
도구 상태(시각이 지나면 UNKNOWN): `python -m v7_harness.cli coord presence`로 확인한다.
"""
=======
도구 상태(시각이 지나면 UNKNOWN): `python -m v7_harness.cli coord presence`로 확인한다.
"""

# U45 G2: the big picture is written once per project, before any delegation. Each delegation then gets its own small
# contract manual in .coord/tasks/<work_id>-manual.md (pilot manual new), whose full text is the worker's input.
PROJECT_MANUAL_TEMPLATE = """# Project manual (big picture)

Write this before the first delegation. Each delegation also gets a small contract manual:
`.coord/tasks/<work_id>-manual.md` via `pilot manual new`, and its full text is the call input.

## Goal
One sentence: what is done when this project is done.

## Scope
Files and folders the tools may change.

## Forbidden
Actions that always need the user: deletion, push/deploy/publish, payment, account/permission/credential changes.

## Gates
The commands that decide done (tests, checks). A step without a gate is unmeasured.

## Workers
Who does what: apply (0 tokens) when the code is known, Ollama for narrow mechanical work, Antigravity or
`worker: claude` with a token and dollar cap for judgment work.

## Judge
The tool that approves, never the author of the same change.
"""
>>>>>>> REPLACE

===EDIT: v7_harness/cli.py===
<<<<<<< SEARCH
        created.append(".coord/PLAN.md")
    for folder in (".coord/tasks", ".coord/mailbox", ".work"):
=======
        created.append(".coord/PLAN.md")
    project_manual = project / ".coord" / "PROJECT_MANUAL.md"
    if not project_manual.is_file():
        project_manual.write_text(PROJECT_MANUAL_TEMPLATE, encoding="utf-8")
        created.append(".coord/PROJECT_MANUAL.md")
    for folder in (".coord/tasks", ".coord/mailbox", ".work"):
>>>>>>> REPLACE

===EDIT: v7_harness/cli.py===
<<<<<<< SEARCH
    print(json.dumps({"ok": True, "created": created, "gitignore_added": missing,
                      "next": ["coord presence --tool <codex|claude|antigravity> --state ACTIVE",
                               "pilot manual new ... then pilot manual lint ... then pilot run --manual ..."]},
                     ensure_ascii=False))
=======
    print(json.dumps({"ok": True, "created": created, "gitignore_added": missing,
                      "contract_manuals": ".coord/tasks/<work_id>-manual.md",
                      "next": ["coord presence --tool <codex|claude|antigravity> --state ACTIVE",
                               "fill .coord/PROJECT_MANUAL.md (big picture) before the first delegation",
                               "pilot manual new ... then pilot manual lint ... then pilot run --manual ..."]},
                     ensure_ascii=False))
>>>>>>> REPLACE



## Output

- Reply with ===FILE / ===EDIT blocks only. No explanations. Do not claim success; the acceptance command decides.
