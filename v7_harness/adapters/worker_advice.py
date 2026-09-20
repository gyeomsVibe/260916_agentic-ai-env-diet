"""할 일 문서를 보고 어느 작업자에게 맡길지 조언한다.

근거는 벤치 실측이다(`docs/16` 벤치 v2, 모델 3종 × 과제 6종).
로컬 모델이 실패한 축은 파일 크기도 파일 수도 아니었다. **지시의 모호함** 하나였고,
3b 모델은 같은 모호한 과제에서 3회 모두 실패했다.

그래서 여기서 재는 것은 난이도가 아니라 **구체성**이다.
- 고칠 파일을 이름으로 지목했는가
- 바꿀 값·이름을 문서에 적었는가
- "적절히", "개선", "튼튼하게" 같이 판단을 넘기는 말에 기대고 있지 않은가

조언일 뿐 강제가 아니다. 판정은 어느 작업자를 쓰든 동일한 인수 게이트가 한다.

한계(측정된 범위 밖은 모른다):
- 재는 것은 **문장의 구체성**이지 과제의 개념적 난이도가 아니다. 구체적으로 적힌 어려운
  설계 과제도 높은 점수를 받는다. 실제로 R2 위임 문서(제어층 반영 관찰)는 95점이 나오지만
  그 과제를 로컬 모델로 돌려 본 적은 없다(`UNKNOWN`).
- 기준선은 벤치 6과제뿐이다. 점수 60이라는 경계선은 그 표본에서 두 무리를 가르는 값이며,
  더 많은 실행이 쌓이면 조정해야 한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 판단을 작업자에게 떠넘기는 표현. 한국어와 영어를 함께 본다.
VAGUE_TERMS = (
    "적절히", "적당히", "알아서", "개선", "최적화", "튼튼",
    "improve", "better", "robust", "cleaner", "optimize", "refactor as needed",
    "appropriately", "as you see fit", "make it nicer",
)
# 무엇을 할지 못 박는 표현.
CONCRETE_VERBS = (
    "rename", "replace", "change", "add", "remove", "set", "delete",
    "교체", "변경", "추가", "삭제", "이름을", "바꾼다", "바꿔",
)
FILE_RE = re.compile(r"[`'\"]?([\w./\\-]+\.(?:py|md|txt|json|toml|yml|yaml|ps1|sh))[`'\"]?")
VALUE_RE = re.compile(r"(?:from|→|->|to)\s+[`'\"]?[\w.\-]+[`'\"]?", re.I)
CODE_BLOCK_RE = re.compile(r"```")
EXPECTATION_RE = re.compile(r"\b(must|should|instead of|instead)\b|대신|반드시|해야", re.I)
REQUIREMENT_LIST_RE = re.compile(r"(?m)^\s*(?:[0-9]+[.)]|[-*])\s+\S")


@dataclass(frozen=True)
class Advice:
    worker: str
    specificity: int  # 0~100
    reasons: tuple[str, ...]

    def as_dict(self) -> dict:
        return {"worker": self.worker, "specificity": self.specificity, "reasons": list(self.reasons)}


def advise(prompt: str) -> Advice:
    """구체성 점수와 추천 작업자를 돌려준다. 60점 미만이면 원격을 권한다."""
    text = (prompt or "").strip()
    if not text:
        return Advice("agy", 0, ("빈 지시문",))

    reasons: list[str] = []
    score = 30  # 출발점. 아무 근거도 없으면 원격이 안전하다.

    files = set(FILE_RE.findall(text))
    if files:
        score += 25
        reasons.append(f"대상 파일을 {len(files)}개 지목함")
    else:
        reasons.append("고칠 파일을 이름으로 지목하지 않음")

    if VALUE_RE.search(text):
        score += 15
        reasons.append("바꿀 값·이름을 명시함")

    if any(verb in text.lower() for verb in CONCRETE_VERBS):
        score += 15
        reasons.append("수행할 동작이 구체적임")
    elif EXPECTATION_RE.search(text):
        # "must raise ValueError('empty') instead" 처럼 동사 대신 기대 결과를 못 박는 형태.
        # 벤치 hard 과제가 이 형태였고 로컬 모델이 통과했다.
        score += 15
        reasons.append("기대 결과를 못 박음")
    else:
        reasons.append("무엇을 할지가 동사로 드러나지 않음")

    if REQUIREMENT_LIST_RE.search(text):
        score += 10
        reasons.append("요구사항을 번호로 나눠 적음")

    if CODE_BLOCK_RE.search(text):
        score += 10
        reasons.append("코드·예시 블록이 있음")

    vague_hits = [term for term in VAGUE_TERMS if term in text.lower()]
    if vague_hits:
        # 판단을 넘기는 말은 로컬 모델이 실패한 유일한 축이다. 가장 무겁게 깎는다.
        score -= 25 * len(vague_hits)
        reasons.append(f"판단을 넘기는 표현 {len(vague_hits)}개: {', '.join(vague_hits[:3])}")

    score = max(0, min(100, score))
    worker = "local" if score >= 60 else "agy"
    return Advice(worker, score, tuple(reasons))
