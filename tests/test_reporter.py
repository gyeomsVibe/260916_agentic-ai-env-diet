"""
Tests for Concise Reporter (Acceptance #7).
"""

import unittest

from v7_harness.reporter import generate_report


class TestReporter(unittest.TestCase):

    def test_concise_report_format(self):
        rep = generate_report(
            result="v7 최소 자동화 구현 완료",
            changed=["v7_harness/*", "tests/*"],
            checks=[("unittest", 0), ("cli smoke", 0)],
            risks="None",
            next_action="U08 진입 준비 권고",
            user_action_required=False,
        )
        md = rep.to_concise_markdown()
        lines = md.splitlines()

        # Check that it has exactly 5 bullet lines (<= 7 lines)
        self.assertEqual(len(lines), 5)
        self.assertTrue(lines[0].startswith("- 결과:"))
        self.assertTrue(lines[1].startswith("- 변경:"))
        self.assertTrue(lines[2].startswith("- 검증:"))
        self.assertTrue(lines[3].startswith("- 잔여 위험:"))
        self.assertTrue(lines[4].startswith("- 다음 자동 행동:"))
        self.assertIn("사용자 할 일 없음", lines[4])

    def test_user_action_required_flag(self):
        rep = generate_report(
            result="승인 필요 작업 감지",
            changed=[],
            checks=[],
            risks="High",
            next_action="사용자 승인 대기",
            user_action_required=True,
        )
        md = rep.to_concise_markdown()
        self.assertIn("[사용자 조치 필요]", md)

    def test_explicit_verification_string(self):
        rep = generate_report(
            result="기능 구현 완료",
            changed=["file.py"],
            risks="None",
            next_action="검토 대기",
            verification="35 tests passed (exit 0)",
        )
        md = rep.to_concise_markdown()
        lines = md.splitlines()
        self.assertEqual(len(lines), 5)
        self.assertEqual(lines[2], "- 검증: 35 tests passed (exit 0)")

    def test_explicit_verification_sequence(self):
        rep = generate_report(
            result="기능 구현 완료",
            changed=["file.py"],
            risks="None",
            next_action="검토 대기",
            verification=["test1(exit 0)", "test2(exit 0)"],
        )
        md = rep.to_concise_markdown()
        lines = md.splitlines()
        self.assertEqual(len(lines), 5)
        self.assertEqual(lines[2], "- 검증: test1(exit 0), test2(exit 0)")


if __name__ == "__main__":
    unittest.main()
