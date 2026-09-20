"""B38: acceptance must not run a staging-planted python.exe; B52: checkpoint refusal must be visible."""

import inspect
import unittest

import v7_harness.pilot as pilot_mod


class B38AcceptanceInterpreterTest(unittest.TestCase):
    def test_python_token_is_resolved_to_the_harness_interpreter(self) -> None:
        resolve = getattr(pilot_mod, "_resolve_accept_tokens", None)
        self.assertIsNotNone(resolve, "pilot must expose _resolve_accept_tokens(cmd) -> list[str]")
        import sys
        tokens = resolve("python -m unittest -q")
        self.assertEqual(sys.executable, tokens[0])
        self.assertEqual(["-m", "unittest", "-q"], tokens[1:])
        tokens = resolve("python.exe tests/x.py")
        self.assertEqual(sys.executable, tokens[0])

    def test_non_python_commands_are_left_alone(self) -> None:
        tokens = pilot_mod._resolve_accept_tokens("pytest -q")
        self.assertEqual(["pytest", "-q"], tokens)


class B52VisibleCheckpointRefusalTest(unittest.TestCase):
    def test_runtime_error_is_not_silently_swallowed(self) -> None:
        src = inspect.getsource(pilot_mod.run_pilot)
        self.assertNotIn("except RuntimeError:\n                        pass", src)
        self.assertNotIn("except RuntimeError:\n                pass", src)
        self.assertIn("CHECKPOINT_REFUSED", src)


if __name__ == "__main__":
    unittest.main()
