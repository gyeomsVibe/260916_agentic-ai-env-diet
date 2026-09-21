"""U15: 스트림 잠금이 여러 프로세스 경합에서 예외 없이 직렬화되는가.

Windows 는 삭제 대기 중인 잠금 파일을 열면 PermissionError 를 낸다. 한때 이것이 잠금 밖으로 새어
사건 기록이 실패했다(8프로세스 × 300회에서 프로세스당 3~11건, 2026-09-22 실측). 스레드는 한 프로세스
안 잠금으로 직렬화되므로 별도 프로세스로 재현한다.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = (
    "import sys, json, collections\n"
    "from pathlib import Path\n"
    "from v7_harness.coord.stream import _exclusive\n"
    "lock, out, w = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]\n"
    "errors = collections.Counter()\n"
    "for i in range(150):\n"
    "    try:\n"
    "        with _exclusive(lock):\n"
    "            with out.open('a', encoding='utf-8') as h:\n"
    "                h.write(f'{w}:{i}\\n')\n"
    "    except Exception as exc:\n"
    "        errors[type(exc).__name__] += 1\n"
    "print(json.dumps(errors))\n"
)


class StreamLockContentionTests(unittest.TestCase):
    def test_six_processes_never_escape_the_lock_or_lose_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock, out = Path(tmp) / "s.lock", Path(tmp) / "out.txt"
            env = dict(os.environ, PYTHONPATH=str(ROOT))
            procs = [
                subprocess.Popen([sys.executable, "-c", WORKER, str(lock), str(out), str(w)],
                                 env=env, cwd=ROOT, stdout=subprocess.PIPE, text=True)
                for w in range(6)
            ]
            errors = [json.loads(p.communicate(timeout=120)[0]) for p in procs]
            self.assertEqual([{}] * 6, errors)
            lines = out.read_text(encoding="utf-8").splitlines()
            self.assertEqual(900, len(lines))
            self.assertEqual(900, len(set(lines)))


if __name__ == "__main__":
    unittest.main()
