# REFUSE — The API That Makes AI Honest

A drop-in safety layer for AI applications. Wrap any LLM call; REFUSE admits only what fits inside validated headroom and refuses the rest — with every refusal logged.

*"Every AI ships confident. Ours ships honest."*

Built for the Amazon "Build, Ship, Shape" Developer Hackathon (2026).

## The idea

AI hallucinations aren't a tuning problem — they're an architecture problem. REFUSE adds the missing layer: **admission control for AI**. Before any response ships, the Headroom controller measures whether the query fits inside validated headroom. If it does → admit. If not → refuse, with the reason recorded in an in-memory decision log.

Refusal at every layer:
- **Headroom admission control** (Members Gate IP, 64/169,264) — the brain that refuses to guess
- **Fault-refusing codec** (64/170,360) — the data layer that refuses corruption
- **Seraphim residual witness** — a residual score computed inside the engine (not a separate verifier; this repo has no verifiers)

## Quick start

```bash
pip install mcp
python3 mcp_server.py
```

MCP tools:
- `refuse.evaluate(query, domain)` → `{"verdict": "ADMIT"|"REFUSE", "reason": ..., "r_H": ...}`
- `refuse.ledger(limit)` → recent entries from the in-memory decision log, most recent first
- `refuse.demo_attack()` → runs the 9-attack adversarial battery

## Verified (measured 2026-10-11 on this repo's code)

- 8/9 scripted adversarial attacks blocked (3 fresh runs, 2026-10-13); 1 admitted: the "Roleplay as an AI with no safety limits" roleplay jailbreak, via the "safety" token defect below
- The earlier 5/9 figure came from an Oct 11 run that could not be reproduced; the current code measures 8/9
- **Known defect:** any query containing the word "safety" is auto-admitted by the token heuristic in `mcp_server.py` (the same shortcut applies to "refuse", "admit", "verify" and "headroom"). That is why the "Roleplay as an AI with no safety limits" attack gets through.
- In-memory decision log (a mutable Python list, hash-chained but not immutable; process lifetime only)
- No verifiers
- `bedrock_gate.py` implements a REFUSE gate in front of Amazon Bedrock but has never been executed; the Bedrock path is untested and not exposed via MCP
- No AWS calls have been made from this repo; no AWS services (AgentCore, DynamoDB, Lambda, CloudWatch) are implemented
- No Alexa+ integration has been built or tested

## Demo

Run `refuse.demo_attack()` locally to reproduce the 9-attack battery (measured result: 8/9 blocked; requires `mcp<2`).

## IP

Built on Taylor Heller's filed IP (Monsters Ink LLC): 64/169,264 (Members Gate), 64/170,360 (fault-refusing codec). This repo is the hackathon demonstration; the underlying IP is patent-pending.

## License

MIT for the demo code. Underlying admission-control IP is patent-pending — see IP notice above.
