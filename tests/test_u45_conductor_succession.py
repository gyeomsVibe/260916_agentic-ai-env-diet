"""U45 G1/G3: who conducts is decided from the three tools' desk states only (ACTIVE/LIMITED/ABSENT/UNKNOWN), never
from a remaining-quota figure turned into tokens (docs/27 §1, §4). Codex conducts; while Codex is LIMITED or ABSENT,
Claude acts; only while both are, Antigravity acts. An expired heartbeat (UNKNOWN) is not absence, so it stops the
succession instead of skipping the tool."""

import argparse
import contextlib
import inspect
import io
import json
import tempfile
import unittest
from pathlib import Path

from v7_harness import cli
from v7_harness.coord import presence


def desk(codex, claude, antigravity):
    return {"codex": {"state": codex}, "claude": {"state": claude}, "antigravity": {"state": antigravity}}


class ConductorSuccessionTest(unittest.TestCase):
    def test_succession_table(self):
        cases = [
            (("ACTIVE", "ACTIVE", "ACTIVE"), ("codex", False)),
            (("ACTIVE", "LIMITED", "ABSENT"), ("codex", False)),
            (("LIMITED", "ACTIVE", "ACTIVE"), ("claude", True)),
            (("ABSENT", "ACTIVE", "LIMITED"), ("claude", True)),
            (("LIMITED", "LIMITED", "ACTIVE"), ("antigravity", True)),
            (("ABSENT", "LIMITED", "ACTIVE"), ("antigravity", True)),
            (("LIMITED", "ABSENT", "LIMITED"), ("none", False)),
            (("UNKNOWN", "ACTIVE", "ACTIVE"), ("UNKNOWN", False)),
            (("LIMITED", "UNKNOWN", "ACTIVE"), ("UNKNOWN", False)),
            (("LIMITED", "LIMITED", "UNKNOWN"), ("UNKNOWN", False)),
        ]
        for states, (who, acting) in cases:
            with self.subTest(states=states):
                result = presence.conductor(desk(*states))
                self.assertEqual((result["conductor"], result["acting"]), (who, acting))
                self.assertTrue(result["reason"])

    def test_decision_takes_only_desk_states(self):
        self.assertEqual(list(inspect.signature(presence.conductor).parameters), ["desk"])
        # A quota figure next to the state changes nothing.
        with_quota = desk("LIMITED", "ACTIVE", "ACTIVE")
        with_quota["codex"]["remaining_percent"] = 90
        with_quota["claude"]["remaining_tokens"] = 1
        self.assertEqual(presence.conductor(with_quota)["conductor"], "claude")

    def test_coord_presence_reports_conductor(self):
        with tempfile.TemporaryDirectory() as tmp:
            presence.mark(Path(tmp), "codex", "LIMITED")
            presence.mark(Path(tmp), "claude", "ACTIVE")
            out = io.StringIO()
            args = argparse.Namespace(project=tmp, tool=None, state=None, ttl=3600, say="json",
                                      from_hook=False, if_uaos=False)
            with contextlib.redirect_stdout(out):
                self.assertEqual(cli.cmd_coord_presence(args), 0)
            data = json.loads(out.getvalue())
            self.assertEqual(data["conductor"]["conductor"], "claude")
            self.assertTrue(data["conductor"]["acting"])


if __name__ == "__main__":
    unittest.main()
