"""B07: '/login' substring must not over-classify AUTH; B14: Unicode line/paragraph separators are control characters."""

import unittest

from v7_harness.adapters.agy import _classify_provider_error
from v7_harness.adapters.validation import require_no_control_characters


class B07AuthClassificationTest(unittest.TestCase):
    def test_path_containing_login_is_not_auth(self) -> None:
        self.assertEqual("PROVIDER_ERROR", _classify_provider_error("failed to write src/pages/login/index.ts: disk full"))
        self.assertEqual("PROVIDER_ERROR", _classify_provider_error("GET /api/v1/users/login_history returned 500"))

    def test_real_auth_errors_still_classified(self) -> None:
        self.assertEqual("AUTH", _classify_provider_error("Please run /login to authenticate"))
        self.assertEqual("AUTH", _classify_provider_error("UNAUTHENTICATED: token expired"))
        self.assertEqual("AUTH", _classify_provider_error("OAuth consent required"))


class B14UnicodeSeparatorTest(unittest.TestCase):
    def test_line_and_paragraph_separators_rejected(self) -> None:
        for ch in ("\u2028", "\u2029", "\u0085"):
            with self.subTest(ch=repr(ch)):
                with self.assertRaises(ValueError):
                    require_no_control_characters(f"task{ch}id", "task_id", ValueError)

    def test_normal_unicode_allowed(self) -> None:
        self.assertEqual("작업-1", require_no_control_characters("작업-1", "task_id", ValueError))


if __name__ == "__main__":
    unittest.main()
