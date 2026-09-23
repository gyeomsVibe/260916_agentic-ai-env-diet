from v7_harness.gemini_shim import to_gemini, to_ollama


def test_request_maps_roles_tools_and_options():
    req = {
        "systemInstruction": {"parts": [{"text": "sys"}]},
        "contents": [
            {"role": "user", "parts": [{"text": "fix it"}]},
            {"role": "model", "parts": [{"thought": True, "text": "hmm"},
                                        {"functionCall": {"name": "view_file", "args": {"p": "a.py"}}}]},
            {"role": "user", "parts": [{"functionResponse": {"name": "view_file", "response": {"out": "x"}}}]},
        ],
        "tools": [{"functionDeclarations": [{"name": "view_file", "parameters": {
            "type": "OBJECT", "properties": {"p": {"type": "STRING", "nullable": True}}}}]}],
        "generationConfig": {"maxOutputTokens": 99, "temperature": 0.4},
    }
    out = to_ollama(req)
    assert [m["role"] for m in out["messages"]] == ["system", "user", "assistant", "tool"]
    assert out["messages"][2]["content"] == ""  # thought part dropped
    assert out["messages"][2]["tool_calls"][0]["function"]["name"] == "view_file"
    params = out["tools"][0]["function"]["parameters"]
    assert params["type"] == "object" and params["properties"]["p"] == {"type": "string"}
    assert out["options"] == {"temperature": 0.4, "num_predict": 99}


def test_response_maps_tool_calls_and_usage():
    ans = to_gemini({"message": {"content": "ok", "tool_calls": [
        {"function": {"name": "write_file", "arguments": '{"a": 1}'}}]}, "prompt_eval_count": 5, "eval_count": 2})
    parts = ans["candidates"][0]["content"]["parts"]
    assert parts == [{"text": "ok"}, {"functionCall": {"name": "write_file", "args": {"a": 1}}}]
    assert ans["usageMetadata"]["totalTokenCount"] == 7


def test_empty_response_still_has_a_part():
    assert to_gemini({"message": {}})["candidates"][0]["content"]["parts"] == [{"text": ""}]
