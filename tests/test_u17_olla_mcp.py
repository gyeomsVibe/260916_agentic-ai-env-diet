"""U17: olla MCP 서버 — 로컬 모델을 에이전트 도구 목록에 올린다. 실제 프로세스로 JSON-RPC 를 주고받는다."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from v7_harness import olla, olla_mcp

ROOT = Path(__file__).resolve().parents[1]


class OllaMcpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for name, value in (("USAGE_LOG", Path(self.tmp.name) / "u.jsonl"), ("DIGEST_CACHE_DIR", Path(self.tmp.name) / "c")):
            patch = mock.patch.object(olla, name, value)
            patch.start()
            self.addCleanup(patch.stop)

    def test_handshake_and_tool_list_over_a_real_process(self) -> None:
        env = dict(os.environ, PYTHONPATH=str(ROOT), OLLA_USAGE=str(Path(self.tmp.name) / "u.jsonl"))
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ]
        done = subprocess.run([sys.executable, "-m", "v7_harness.olla_mcp"], cwd=ROOT, env=env, timeout=60,
                              input="".join(json.dumps(m) + "\n" for m in messages).encode("utf-8"), capture_output=True)
        replies = [json.loads(line) for line in done.stdout.decode("utf-8").splitlines()]
        self.assertEqual([1, 2], [r["id"] for r in replies])  # 알림에는 답하지 않음
        self.assertEqual("olla", replies[0]["result"]["serverInfo"]["name"])
        names = [t["name"] for t in replies[1]["result"]["tools"]]
        self.assertEqual(["local_read_map", "local_draft", "local_search"], names)

    def test_mcp_exposes_no_write_tool(self) -> None:
        # 쓰기(수정)는 SQLite 파일럿의 관문(staging·manifest·bundle 승인)으로만 한다. MCP 가 쓰기 도구를
        # 내면 관문을 우회하는 두 번째 경로가 생긴다 — 그 충돌을 구조로 막는다.
        for tool in olla_mcp.TOOLS:
            self.assertNotRegex(tool["name"], r"edit|write|apply|patch|delete")
            self.assertNotIn("path_to_write", json.dumps(tool["inputSchema"]))

    def test_read_map_uses_and_fills_the_cache(self) -> None:
        target = Path(self.tmp.name) / "big.py"
        target.write_text("x = 1\n" * 50, encoding="utf-8")
        with mock.patch.object(olla.worker, "_generate", return_value=("- L1-50: assignments", {})) as gen:
            first = olla_mcp.call_tool("local_read_map", {"path": str(target)})
            second = olla_mcp.call_tool("local_read_map", {"path": str(target)})
        self.assertIn("L1-50", first["content"][0]["text"])
        self.assertEqual(first["content"][0]["text"], second["content"][0]["text"])
        self.assertEqual(1, gen.call_count)

    def test_draft_refuses_empty_input_and_flags_invented_names(self) -> None:
        empty = Path(self.tmp.name) / "e.md"
        empty.write_text("", encoding="utf-8")
        refused = olla_mcp.call_tool("local_draft", {"instruction": "x", "files": [str(empty)]})
        self.assertTrue(refused["isError"])
        with mock.patch.object(olla.worker, "_generate", return_value=("run tests.test_nope", {})):
            flagged = olla_mcp.call_tool("local_draft", {"instruction": "x"})
        self.assertIn("likely invented", flagged["content"][0]["text"])

    def test_unknown_method_and_server_down_are_reported_not_raised(self) -> None:
        self.assertEqual(-32601, olla_mcp.handle({"id": 9, "method": "nope"})["error"]["code"])
        target = Path(self.tmp.name) / "f.py"
        target.write_text("x = 1\n", encoding="utf-8")
        with mock.patch.object(olla.worker, "_generate", side_effect=OSError("refused")):
            down = olla_mcp.call_tool("local_read_map", {"path": str(target)})
        self.assertTrue(down["isError"])


if __name__ == "__main__":
    unittest.main()
