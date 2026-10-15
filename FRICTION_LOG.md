# Friction Log: REFUSE / PRIM3

Entries come from this repo's commit history and the project's task reports (Oct 9–14, 2026).

## 1. mcp 2.x broke the server import
- **Task:** Run `mcp_server.demo_attack()` from a fresh clone.
- **Steps:** Created a Python 3.13 venv and installed `mcp` with no version pin.
- **Expected vs actual:** Expected the FastMCP server to import. With mcp 2.x the import failed; it worked with mcp<2.
- **Severity:** High. Fresh installs could not run at all.
- **Workaround:** Pinned `mcp<2` (commit 49c77c3), later `mcp>=1.30,<2` for Streamable HTTP and spec 2025-11-25 (commit 6635b9b).
- **Suggestion:** Publish a 1.x → 2.x migration note for FastMCP users, and make breaking import changes fail with a clear message.

## 2. Alexa+ add-on tools are not available to hackathon entrants
- **Task:** Connect the self-hosted MCP server to Alexa+.
- **Steps:** Read the Alexa+ add-on docs and the hackathon FAQ.
- **Expected vs actual:** Expected a path to test on Alexa+ or a developer console. The Category SDK, MCP Toolkit, CLI and Web Simulator are preview, select-partners only.
- **Severity:** Medium. A real device demo is not possible.
- **Workaround:** Built a simulated Alexa+ web experience that sends every utterance to the real MCP server over Streamable HTTP (commit 8817387). It is labelled as simulated on screen.
- **Suggestion:** Give hackathon entrants a public MCP test harness or simulator, or state the restriction on the add-on setup page itself.

## 3. MCP stdio-only default vs the track's Streamable HTTP requirement
- **Task:** Meet the Alexa+ track requirement (MCP spec 2025-11-25 over Streamable HTTP).
- **Steps:** The first server used the FastMCP default (`mcp.run()`, stdio).
- **Expected vs actual:** stdio does not meet the requirement. Streamable HTTP had to be added explicitly (`transport="streamable-http"`).
- **Severity:** Medium.
- **Workaround:** Added an `--http` mode, an HTTP battery client and tests that start real servers on free ports (commit 6635b9b).
- **Suggestion:** Add a minimal "Streamable HTTP + version-negotiation check" example to the hackathon resources.

## 4. Hash-derived scoring made the measured results unstable
- **Task:** Reproduce the adversarial battery result.
- **Steps:** Re-ran `demo_attack()` across days.
- **Expected vs actual:** An Oct 11 run recorded 5/9; Oct 13 runs measured 8/9 on unchanged engine files. The 5/9 figure could not be reproduced (commit 49c77c3). The sha256-derived residual also refused benign queries (e.g. "What's the weather tomorrow?", r_H 0.1841), and a keyword shortcut auto-admitted anything containing "safety".
- **Severity:** High (our own defect, not an Amazon tool).
- **Workaround:** Removed the keyword shortcut (30cafd9), added a persona pre-gate (23a1223), and replaced the hash with a content-grounded residual calibrated on 9 attacks + 26 benign queries (720c45b). Measured: 9/9 refused, 26/26 admitted in-sample; held-out results are in the README.
- **Suggestion (to ourselves):** Measure on held-out data from day one.

## 5. Video review blocked by YouTube bot check
- **Task:** Have a second reviewer audit the uploaded demo video.
- **Expected vs actual:** Direct download was blocked by YouTube's bot check, so the review had to run against the live page instead.
- **Severity:** Low.
- **Workaround:** Reviewed against the source cut and narration script kept alongside the upload.

## 6. Bedrock path not executed
- **Task:** AWS Builder integration.
- **Actual:** `bedrock_gate.py` implements a boto3 `invoke_model` gate (commit 4a8a2fc) but has never been run. The hackathon's AWS credit codes ran out on Oct 7.
- **Severity:** Medium.
- **Status:** Documented as untested in the README; no AWS calls have been made from this repo.
