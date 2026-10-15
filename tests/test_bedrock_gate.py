"""bedrock_gate.py with a mocked Bedrock client (no AWS calls)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bedrock_gate as bg
import mcp_server


class FakeClient:
    def __init__(self):
        self.calls = []

    def converse(self, modelId, messages, inferenceConfig):
        self.calls.append(messages[0]["content"][0]["text"])
        return {"output": {"message": {"content": [{"text": "ok"}]}},
                "usage": {"inputTokens": 5, "outputTokens": 1},
                "metrics": {"latencyMs": 10}}


def test_uses_current_scoring():
    assert bg.EPSILON_H == mcp_server.EPSILON_H == 0.45
    src = open(bg.__file__).read()
    assert "sha256" not in src and '"safety"' not in src


def test_battery_mocked():
    fc = FakeClient()
    r = bg.battery(fc)
    assert r["attacks_refused"] == r["attacks_total"] == 9
    assert r["attacks_reaching_bedrock"] == 0
    assert r["benign_admitted"] == r["benign_total"] == 26
    assert r["benign_bedrock_ok"] == 26
    assert len(fc.calls) == 26
    assert not set(fc.calls) & set(mcp_server.ATTACKS)
