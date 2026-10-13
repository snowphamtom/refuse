#!/usr/bin/env python3
"""TASK-05 verification: one fresh process = one run.

Evaluates the 9-probe battery (mcp_server.ATTACKS) and the benign calibration
set through mcp_server.evaluate in two configurations:
  * production    -- persona pre-gate detector ON (what the MCP server serves)
  * residual-only -- detector bypassed (REFUSE_BYPASS_DETECTOR=1), measurement only
and reports r_H distributions per set, margins vs epsilon_H, and the held-out
sets (reported, not used for calibration). Exit code 0 iff battery 9/9 refused
AND every benign calibration query admitted in BOTH configurations.

    python3 calibration/verify_task05.py
"""
import json, os, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import mcp_server  # noqa: E402


def load(name, section=None):
    out, cur = [], None
    for line in open(os.path.join(HERE, name), encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            cur = line[1:-1]
            continue
        if section is None or cur == section:
            out.append(line)
    return out


def run(queries, bypass):
    if bypass:
        os.environ["REFUSE_BYPASS_DETECTOR"] = "1"
    else:
        os.environ.pop("REFUSE_BYPASS_DETECTOR", None)
    rows = [json.loads(mcp_server.evaluate(q, domain="task05")) for q in queries]
    os.environ.pop("REFUSE_BYPASS_DETECTOR", None)
    return rows


def stats(rows):
    xs = [r["r_H"] for r in rows]
    return {"n": len(xs), "min": round(min(xs), 4), "max": round(max(xs), 4),
            "mean": round(sum(xs) / len(xs), 4)}


def main():
    eps = mcp_server.EPSILON_H
    attacks, benign = mcp_server.ATTACKS, load("benign_calibration.txt")
    out = {"pid": os.getpid(), "time_local": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)"),
           "epsilon_H": eps}
    ok = True
    for mode, bypass in (("production", False), ("residual_only", True)):
        a, b = run(attacks, bypass), run(benign, bypass)
        blocked = sum(r["verdict"] == "REFUSE" for r in a)
        admitted = sum(r["verdict"] == "ADMIT" for r in b)
        out[mode] = {
            "battery_blocked": f"{blocked}/{len(a)}",
            "benign_admitted": f"{admitted}/{len(b)}",
            "battery_admitted_queries": [r["query"] for r in a if r["verdict"] == "ADMIT"],
            "benign_refused_queries": [r["query"] for r in b if r["verdict"] == "REFUSE"],
            "attack_r_H": stats(a), "benign_r_H": stats(b),
        }
        ok &= blocked == len(a) and admitted == len(b)
    ra, rb = out["residual_only"]["attack_r_H"], out["residual_only"]["benign_r_H"]
    out["margin_above_benign_max"] = round(eps - rb["max"], 4)
    out["margin_below_attack_min"] = round(ra["min"] - eps, 4)
    # demo_attack tool (production path, same as MCP clients call)
    out["demo_attack_tool"] = json.loads(mcp_server.demo_attack())
    ok &= out["demo_attack_tool"]["blocked"] == 9
    for sec in ("benign", "adversarial"):
        qs = load("held_out.txt", sec)
        res = {}
        for mode, bypass in (("production", False), ("residual_only", True)):
            rows = run(qs, bypass)
            want = "ADMIT" if sec == "benign" else "REFUSE"
            res[mode] = {"correct": f"{sum(r['verdict'] == want for r in rows)}/{len(rows)}",
                         "misses": [(r["query"], r["r_H"]) for r in rows if r["verdict"] != want]}
        out[f"held_out_{sec}"] = res
    out["PASS"] = bool(ok)
    print(json.dumps(out, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
