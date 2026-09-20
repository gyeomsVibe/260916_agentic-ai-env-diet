"""
Concise reporter module for v7 harness.

Formats execution outputs into a compact (<= 7 lines) 5-point report:
1. Result (결과)
2. Changed (무엇이 바뀌었는지)
3. Verification (검증 결과 및 종료 코드)
4. Remaining risks (남은 위험)
5. Next auto action (다음 자동 행동 또는 '할 일 없음')
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence


@dataclass
class ExecutionReport:
    result: str
    changed: list[str]
    checks: list[tuple[str, int]]  # (check_description, exit_code)
    risks: str
    next_action: str
    user_action_required: bool = False
    verification: Optional[str] = None

    def to_concise_markdown(self) -> str:
        """Format the report into a clean, concise markdown representation."""
        if self.verification is not None:
            verification_str = self.verification if self.verification else "None"
        elif self.checks:
            verification_str = ", ".join(f"{desc}(exit {code})" for desc, code in self.checks)
        else:
            verification_str = "None"

        changed_str = ", ".join(self.changed) if self.changed else "None"
        user_notice = " [사용자 조치 필요]" if self.user_action_required else " (사용자 할 일 없음)"

        lines = [
            f"- 결과: {self.result}",
            f"- 변경: {changed_str}",
            f"- 검증: {verification_str}",
            f"- 잔여 위험: {self.risks}",
            f"- 다음 자동 행동: {self.next_action}{user_notice}",
        ]
        return "\n".join(lines)


def generate_report(
    result: str,
    changed: Sequence[str],
    checks: Sequence[tuple[str, int]] = (),
    risks: str = "None",
    next_action: str = "Proceed to review",
    user_action_required: bool = False,
    verification: Optional[str | Sequence[str]] = None,
) -> ExecutionReport:
    ver_str: Optional[str] = None
    if verification is not None:
        if isinstance(verification, (list, tuple)):
            ver_str = ", ".join(str(v) for v in verification)
        else:
            ver_str = str(verification)

    return ExecutionReport(
        result=result,
        changed=list(changed),
        checks=list(checks),
        risks=risks,
        next_action=next_action,
        user_action_required=user_action_required,
        verification=ver_str,
    )
