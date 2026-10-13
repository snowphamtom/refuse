#!/usr/bin/env python3
"""Simulated Alexa+ experience (not a real Echo device).

Serves a single-page UI and a small JSON backend. Every utterance is sent to
PRIM3's real MCP server over Streamable HTTP (mcp_server.py --http).

    python3 mcp_server.py --http --port 8770
    python3 demo/alexa_sim/server.py --port 8771 --mcp-url http://127.0.0.1:8770/mcp
    open http://127.0.0.1:8771/
"""
import argparse, asyncio, json, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp_server import ATTACKS

MCP_URL = "http://127.0.0.1:8770/mcp"


async def _evaluate(queries):
    async with streamablehttp_client(MCP_URL) as (r, w, _):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            out = []
            for q in queries:
                res = await s.call_tool("evaluate", {"query": q, "domain": "alexa_sim"})
                out.append(json.loads(res.content[0].text))
            return init.protocolVersion, out


def reply_text(v):
    if v["verdict"] == "ADMIT":
        return "Request admitted. It fits inside validated headroom."
    return "I won't do that. That request was refused and logged."


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        self._send(404, {"error": "not found"})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n) or b"{}")
            if self.path == "/api/ask":
                text = str(data.get("text", "")).strip()
                if not text:
                    return self._send(400, {"error": "empty utterance"})
                pv, [v] = asyncio.run(_evaluate([text]))
                return self._send(200, {"protocol": pv, "result": v, "reply": reply_text(v)})
            if self.path == "/api/battery":
                pv, vs = asyncio.run(_evaluate(ATTACKS))
                blocked = sum(v["verdict"] == "REFUSE" for v in vs)
                return self._send(200, {"protocol": pv, "results": vs,
                                        "blocked": blocked, "total": len(vs)})
            self._send(404, {"error": "not found"})
        except Exception as e:  # surface MCP connection errors to the UI
            self._send(502, {"error": f"{type(e).__name__}: {e}"})

    def log_message(self, *a):
        pass


def main():
    global MCP_URL
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8771)
    ap.add_argument("--mcp-url", default=MCP_URL)
    a = ap.parse_args()
    MCP_URL = a.mcp_url
    print(f"Simulated Alexa+ UI: http://{a.host}:{a.port}/  (MCP: {MCP_URL})", flush=True)
    ThreadingHTTPServer((a.host, a.port), H).serve_forever()


if __name__ == "__main__":
    main()
