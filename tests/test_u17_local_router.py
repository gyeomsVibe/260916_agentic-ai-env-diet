import json
import unittest

from v7_harness import local_router as r


def body(model="local-qwen", system="You are a Claude agent", tools=(), messages=None):
    return {"model": model, "system": [{"type": "text", "text": "x-anthropic-billing-header: cc"},
                                       {"type": "text", "text": system}],
            "tools": [{"name": n, "input_schema": {}} for n in tools], "messages": messages or [], "max_tokens": 10,
            "thinking": {"type": "enabled"}, "context_management": {}}


class DecideTest(unittest.TestCase):
    def test_main_model_always_upstream(self):
        self.assertEqual(r.decide(body(model="claude-opus-5"), 10, mode="route"), ("upstream", "main-model"))

    def test_marker_goes_local_only_in_route_mode(self):
        self.assertEqual(r.decide(body(), 10, mode="route")[0], "local")
        self.assertEqual(r.decide(body(), 10, mode="observe"), ("upstream", "observe"))

    def test_guard_like_prompts_stay_upstream(self):
        b = body(system="Classify whether this bash command has command injection")
        self.assertEqual(r.decide(b, 10, mode="route"), ("upstream", "guard-request"))

    def test_gpu_busy_and_too_big_stay_upstream(self):
        self.assertEqual(r.decide(body(), 10, mode="route", gpu_busy=True)[1], "gpu-busy")
        big = body(messages=[{"role": "user", "content": "x" * 200_000}])
        self.assertEqual(r.decide(big, 1, mode="route")[1], "too-big")

    def test_billing_header_is_skipped_in_head(self):
        self.assertEqual(r.system_head(body(system="A user kicked off")), "A user kicked off")


class BodyTest(unittest.TestCase):
    def test_local_body_prunes_tools_and_unknown_keys(self):
        out = json.loads(r.local_body(body(tools=["Read", "Grep", "WebSearch", "mcp__x"])))
        self.assertEqual(out["model"], r.LOCAL_MODEL)
        self.assertEqual([t["name"] for t in out["tools"]], ["Read", "Grep"])
        self.assertNotIn("thinking", out)
        self.assertNotIn("context_management", out)

    def test_upstream_fallback_replaces_marker_model(self):
        b = body()
        self.assertEqual(json.loads(r.upstream_body(b, b"{}"))["model"], r.FALLBACK_MODEL)
        main = body(model="claude-opus-5")
        self.assertEqual(r.upstream_body(main, b"RAW"), b"RAW")


if __name__ == "__main__":
    unittest.main()
