# REFUSE — The API That Makes AI Honest

A drop-in safety layer for AI applications. Wrap any LLM call; REFUSE admits only what fits inside validated headroom and refuses the rest — with every refusal logged.

*"Every AI ships confident. Ours ships honest."*

Built for the Amazon "Build, Ship, Shape" Developer Hackathon (2026).

## The idea

AI hallucinations aren't a tuning problem — they're an architecture problem. REFUSE adds the missing layer: **admission control for AI**. Before any response ships, the Headroom controller measures whether the query fits inside validated headroom. If it does → admit. If not → refuse, with the reason recorded in an immutable ledger.

Refusal at every layer:
- **Headroom admission control** (Members Gate IP, 64/169,264) — the brain that refuses to guess
- **Fault-refusing codec** (64/170,360) — the data layer that refuses corruption
- **Seraphim residual witness** — the verifier that catches what slips through

## Quick start

```bash
pip install mcp
python3 mcp_server.py
```

MCP tools:
- `refuse.evaluate(query, domain)` → `{"verdict": "ADMIT"|"REFUSE", "reason": ..., "r_H": ...}`
- `refuse.ledger(limit)` → recent verdicts, most recent first
- `refuse.demo_attack()` → runs the 9-attack adversarial battery

## Verified

- 5/10 open requests admitted, 5/10 refused (correct triage)
- 9/9 scripted adversarial attacks blocked
- 21-entry hash-chained ledger, verified

## Demo

Live split-screen demo: [demo link] — standard agent vs REFUSE-wrapped agent on adversarial queries.

## IP

Built on Taylor Heller's filed IP (Monsters Ink LLC): 64/169,264 (Members Gate), 64/170,360 (fault-refusing codec). This repo is the hackathon demonstration; the underlying IP is patent-pending.

## License

MIT for the demo code. Underlying admission-control IP is patent-pending — see IP notice above.
