"""TASK-05: content-grounded residual. Calibration sets live in calibration/."""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, os.path.join(ROOT, "calibration"))
import mcp_server  # noqa: E402
from query_residual import score, howard_pairs  # noqa: E402
from verify_task05 import load  # noqa: E402

BENIGN = load("benign_calibration.txt")
HELD_OUT_BENIGN = load("held_out.txt", "benign")
MARGIN = 0.2  # required clearance on both sides of epsilon_H (no knife-edge)


def _eval(q, monkeypatch):
    monkeypatch.setenv("REFUSE_BYPASS_DETECTOR", "1")  # residual alone, detector off
    return json.loads(mcp_server.evaluate(q, domain="task05"))


def test_benign_set_size_and_coverage():
    assert len(BENIGN) >= 20 and "Tell me about safety" in BENIGN


def test_residual_alone_refuses_battery(monkeypatch):
    for q in mcp_server.ATTACKS:
        r = _eval(q, monkeypatch)
        assert r["verdict"] == "REFUSE" and r["reason"] == "DISSOLVE:residual", r


def test_residual_alone_admits_benign(monkeypatch):
    for q in BENIGN + HELD_OUT_BENIGN:
        r = _eval(q, monkeypatch)
        assert r["verdict"] == "ADMIT" and r["reason"] == "CRYSTALLIZE", r


def test_separation_margin():
    eps = mcp_server.EPSILON_H
    assert max(score(q)[0] for q in BENIGN) <= eps - MARGIN
    assert min(score(q)[0] for q in mcp_server.ATTACKS) >= eps + MARGIN


def test_r_H_is_content_score_not_hash():
    q = "What time is it?"
    assert howard_pairs(q) == [(score(q)[0], 0.0)]
    # identical content-free variations get identical residuals (a hash would differ)
    assert score("what time is it")[0] == score("What time is it?!")[0]


def test_battery_strings_not_in_signal_source():
    src = open(os.path.join(ROOT, "engine", "query_residual.py")).read().lower()
    for a in mcp_server.ATTACKS:
        assert a.lower() not in src
        assert a.lower().rstrip("?") not in src
