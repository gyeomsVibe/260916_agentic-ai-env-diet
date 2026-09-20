"""U16: 작업자 조언.

기준선은 벤치 v2의 실제 과제다. 로컬이 통과한 과제는 local 을, 로컬이 실패한 과제는
agy 를 추천해야 한다. 조언이 실측과 어긋나면 그 조언은 쓸모가 없다.
"""

from __future__ import annotations

import unittest

from v7_harness.adapters.worker_advice import advise

# 벤치 v2에서 로컬 모델이 통과한 과제 문구 (docs/16)
PASSED_LOCALLY = {
    "easy": "In `config.py`, change TIMEOUT_S from 30 to 90. Change nothing else.",
    "medium": (
        "Two files use `open()` without an encoding.\n"
        "In `reader.py` and `writer.py`, add `encoding=\"utf-8\"` to every `open()` call."
    ),
    "hard": (
        "`stats.py` has two defects:\n"
        "1. mean([]) raises ZeroDivisionError. It must raise ValueError('empty') instead.\n"
        "2. median() is wrong for an even number of values; average the two middle values."
    ),
    "large_file": "In `big.py`, change TIMEOUT_S from 30 to 90. Every other line must stay exactly as it is.",
    "multi_file_refactor": (
        "Rename `fetch_data` to `load_record` everywhere: its definition in `util.py` and every "
        "import and call in `api.py` and `job.py`."
    ),
}

# 3b 모델이 3회 모두 실패한 과제 (재현 확인됨)
FAILED_LOCALLY = "Make `cache.py` more robust. Missing keys should not crash the caller."


class WorkerAdviceTests(unittest.TestCase):
    def test_tasks_the_local_model_passed_are_recommended_local(self) -> None:
        for name, prompt in PASSED_LOCALLY.items():
            with self.subTest(case=name):
                result = advise(prompt)
                self.assertEqual("local", result.worker, f"{name}: {result.reasons}")
                self.assertGreaterEqual(result.specificity, 60)

    def test_the_task_the_local_model_failed_is_recommended_remote(self) -> None:
        result = advise(FAILED_LOCALLY)
        self.assertEqual("agy", result.worker)
        self.assertTrue(any("판단을 넘기는" in reason for reason in result.reasons))

    def test_vague_korean_instruction_goes_remote(self) -> None:
        result = advise("`cache.py`를 알아서 적절히 개선해줘.")
        self.assertEqual("agy", result.worker)

    def test_empty_prompt_goes_remote(self) -> None:
        result = advise("   ")
        self.assertEqual("agy", result.worker)
        self.assertEqual(0, result.specificity)

    def test_reasons_explain_the_verdict(self) -> None:
        result = advise("In `config.py`, change TIMEOUT_S from 30 to 90.")
        self.assertTrue(result.reasons)
        self.assertTrue(any("파일" in reason for reason in result.reasons))

    def test_score_stays_in_range(self) -> None:
        worst = advise("적절히 개선하고 최적화하고 알아서 튼튼하게 해줘")
        best = advise(
            "Rename `a` to `b` in `x.py`, change TIMEOUT from 1 to 2, add `encoding=\"utf-8\"`.\n```py\nTIMEOUT = 2\n```"
        )
        self.assertGreaterEqual(worst.specificity, 0)
        self.assertLessEqual(best.specificity, 100)
        self.assertEqual("agy", worst.worker)
        self.assertEqual("local", best.worker)


if __name__ == "__main__":
    unittest.main()
