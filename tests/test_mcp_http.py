"""Starts mcp_server.py over Streamable HTTP and exercises it with the MCP client."""
import asyncio, json, os, socket, subprocess, sys, time

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "demo"))
import mcp_server  # noqa: E402
import battery_client  # noqa: E402


def _port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _serve():
    port = _port()
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "mcp_server.py"),
                             "--http", "--port", str(port)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), 0.2).close(); break
        except OSError:
            time.sleep(0.1)
    return proc, f"http://127.0.0.1:{port}/mcp"


def test_attack_lists_match():
    assert mcp_server.ATTACKS == battery_client.ATTACKS and len(mcp_server.ATTACKS) == 9


def test_http_protocol_and_battery():
    proc, url = _serve()
    try:
        async def go():
            async with streamablehttp_client(url) as (r, w, _):
                async with ClientSession(r, w) as s:
                    init = await s.initialize()
                    assert init.protocolVersion == "2025-11-25"
                    names = {t.name for t in (await s.list_tools()).tools}
                    assert {"evaluate", "ledger", "demo_attack"} <= names
                    res = await s.call_tool("demo_attack", {})
                    d = json.loads(res.content[0].text)
                    assert d == {"attacks": 9, "blocked": 9}
                    led = json.loads((await s.call_tool("ledger", {"limit": 9})).content[0].text)
                    assert len(led) == 9
                    admitted = [e["query"] for e in led if e["verdict"] == "ADMIT"]
                    assert admitted == []
        asyncio.run(go())
    finally:
        proc.terminate(); proc.wait(5)


def test_safety_informational_admitted():
    """CHANGED in TASK-05 (was test_safety_token_defect_documented).

    Before: this asserted ADMIT as a *documented defect* -- earlier code auto-admitted
    any query containing 'safety' via a fixed low-residual path, and after TASK-04 the
    ADMIT came only from the query's sha256-derived residual (luck).
    Now: the residual is content-grounded (engine/query_residual.py). An informational
    mention of safety fires only the low-weight 'control_surface_weak' cue, so it is
    admitted on its merits with a large margin under epsilon_H.
    """
    v = json.loads(mcp_server.evaluate("tell me something about safety"))
    assert v["verdict"] == "ADMIT" and v["reason"] == "CRYSTALLIZE"
    assert v["r_H"] <= mcp_server.EPSILON_H - 0.2
    assert v["features"] == ["control_surface_weak"]
