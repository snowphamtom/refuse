#!/usr/bin/env python3
"""REFUSE x Amazon Bedrock: the admission gate in front of a Bedrock model.

    User query -> REFUSE (same scoring as the MCP server) -> ADMIT  -> Bedrock -> response
                                                          -> REFUSE -> logged; Bedrock never called

Scoring is identical to the MCP server: it calls mcp_server.evaluate(), i.e. the
content-grounded residual in engine/query_residual.py with epsilon_H = 0.45 and the
persona pre-gate (set REFUSE_BYPASS_DETECTOR=1 to bypass it, measurement only).
The old hash/keyword residual that this file used to carry is gone.

Setup:
    pip install -r requirements.txt boto3
    aws login            # short-term credentials; needs bedrock:InvokeModel and
                         # Bedrock model access for MODEL_ID in AWS_REGION

Usage:
    python3 bedrock_gate.py "What is the capital of Australia?"
    python3 bedrock_gate.py --battery --out calibration/runs/bedrock_run.json
        # 9 battery attacks + 26 benign calibration queries; only admitted queries
        # reach Bedrock. Records verdicts, model id, region, latency, token usage.

Env: BEDROCK_MODEL_ID (default below), AWS_REGION (default us-east-1),
     BEDROCK_MAX_TOKENS (default 120, kept low to minimise cost).
"""
import argparse, json, os, sys, time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mcp_server  # noqa: E402  (same evaluate() the MCP server serves)

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
REGION = os.environ.get("AWS_REGION", "us-east-1")
MAX_TOKENS = int(os.environ.get("BEDROCK_MAX_TOKENS", "120"))
EPSILON_H = mcp_server.EPSILON_H


def make_client():
    import boto3
    return boto3.client("bedrock-runtime", region_name=REGION)


def bedrock_call(client, query: str) -> dict:
    """One Bedrock Converse call. Returns text, latency and token usage."""
    t0 = time.perf_counter()
    r = client.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": query}]}],
        inferenceConfig={"maxTokens": MAX_TOKENS, "temperature": 0.0},
    )
    wall_ms = round((time.perf_counter() - t0) * 1000, 1)
    text = "".join(c.get("text", "") for c in r["output"]["message"]["content"])
    return {"text": text, "wall_ms": wall_ms,
            "bedrock_latency_ms": r.get("metrics", {}).get("latencyMs"),
            "usage": r.get("usage", {}),
            "request_id": r.get("ResponseMetadata", {}).get("RequestId")}


def gated_query(query: str, client=None) -> dict:
    v = json.loads(mcp_server.evaluate(query))
    entry = {"query": query, "verdict": v["verdict"], "reason": v["reason"],
             "r_H": v["r_H"], "features": v.get("features", []),
             "bedrock_invoked": False}
    if v["verdict"] == "ADMIT":
        client = client or make_client()
        try:
            entry.update(bedrock_call(client, query))
            entry["bedrock_invoked"] = True
        except Exception as e:  # noqa: BLE001 - surface AWS errors plainly
            entry["error"] = f"{type(e).__name__}: {e}"
    return entry


def load_benign():
    p = os.path.join(HERE, "calibration", "benign_calibration.txt")
    return [l.strip() for l in open(p, encoding="utf-8")
            if l.strip() and not l.startswith("#")]


def battery(client=None) -> dict:
    client = client or make_client()
    attacks = [gated_query(q, client) for q in mcp_server.ATTACKS]
    benign = [gated_query(q, client) for q in load_benign()]
    ok = [e for e in benign if e["bedrock_invoked"]]
    lat = sorted(e["wall_ms"] for e in ok)
    return {
        "time_local": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)"),
        "model_id": MODEL_ID, "region": REGION, "max_tokens": MAX_TOKENS,
        "epsilon_H": EPSILON_H,
        "attacks_refused": sum(e["verdict"] == "REFUSE" for e in attacks),
        "attacks_total": len(attacks),
        "attacks_reaching_bedrock": sum(e["bedrock_invoked"] for e in attacks),
        "benign_admitted": sum(e["verdict"] == "ADMIT" for e in benign),
        "benign_total": len(benign),
        "benign_bedrock_ok": len(ok),
        "bedrock_errors": [e["error"] for e in attacks + benign if "error" in e],
        "latency_ms": {"min": lat[0], "median": lat[len(lat) // 2], "max": lat[-1]} if lat else None,
        "tokens": {"input": sum(e["usage"].get("inputTokens", 0) for e in ok),
                   "output": sum(e["usage"].get("outputTokens", 0) for e in ok)},
        "attacks": attacks, "benign": benign,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?")
    ap.add_argument("--battery", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.battery:
        res = battery()
        if a.out:
            json.dump(res, open(a.out, "w"), indent=1)
        summary = {k: v for k, v in res.items() if k not in ("attacks", "benign")}
        print(json.dumps(summary, indent=1))
        return 0 if (res["attacks_refused"] == res["attacks_total"]
                     and res["attacks_reaching_bedrock"] == 0
                     and res["benign_bedrock_ok"] == res["benign_total"]) else 1
    if not a.query:
        ap.error("provide a query or --battery")
    print(json.dumps(gated_query(a.query), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
