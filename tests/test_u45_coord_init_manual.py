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
