# RAG + MCP Drug Interaction Search — Build Log

**Status:** Complete. All 6 phases (0-5) done — Phases 0-2 on 2026-07-10,
Phases 3-5 on 2026-07-11. Verified live; not yet part of production deploy
(guideline server is started by `start.sh` for local dev, no cloud deploy
target exists for the backend yet).

## Why

`backend/draft_generator.py` (lines 358-363) has a `MANDATORY DRUG INTERACTION
CHECKS` block — 5 hand-typed drug pairs hardcoded into the LLM prompt. Anything
outside those 5 pairs is never flagged in the Safety Alerts section of a
generated report. Goal: replace it with a real search tool that checks any
medication combination against real NHS/BNF guideline documents, built as a
standalone custom MCP server.

Full plan: `~/.claude/plans/quirky-toasting-badger.md`
New project folder (separate from this repo, deliberately standalone):
`~/Documents/nhs-guideline-mcp/`

## Phases

- [x] **Phase 0 — Orientation.** Walked through `wiki_mcp.py`'s three-part shape
      (FastMCP instance, one `@mcp.tool()` function, `mcp.run()`) and
      `draft_generator.py` lines 267-478, confirming scope: no 4th LLM call, no
      agentic tool loop, `update_agent.py`/`verification_agent.py`/
      `protocol_agent.py`/`coordinator_agent.py` untouched.
- [x] **Phase 1 — Document sourcing.** Sourced 8 real passages (the original 5
      hardcoded pairs + 3 new: Clarithromycin+Statin, SSRI+NSAID/Warfarin,
      Methotrexate+NSAID/Trimethoprim), primarily from NHS Specialist Pharmacy
      Service (sps.nhs.uk — free, publicly accessible, official NHS reference).
      Saved as `nhs-guideline-mcp/corpus/*.md`, each with source URL + retrieval
      date. Checked NICE's Syndication API as an alternative — ruled out: it
      excludes BNF interaction data entirely (separate licensed product via
      Pharmaceutical Press) and requires organisational cyber-security
      certification to access, not viable for this project.
- [x] **Phase 2 — Supabase pgvector ingestion.** Enabled the `vector` extension
      on the existing Supabase project (`vpjshqezssfzgpzagqvk`, previously
      available but off). Created `guideline_chunks` table (source_name,
      source_url, drug_terms, content, embedding vector(384)) + an
      `match_guideline_chunks` RPC function for cosine-similarity search.
      Embedded all 8 corpus passages locally via `sentence-transformers`
      (`all-MiniLM-L6-v2`, free, no API key) and loaded them in —
      `nhs-guideline-mcp/ingest.py`. Verified 8 rows live with 384-dim
      embeddings via direct SQL query.
- [x] **Phase 3 — MCP server.** Built `nhs-guideline-mcp/server.py`, one tool
      `search_guideline(query: str)`, mirrors `wiki_mcp.py`'s shape, real vector
      search against Supabase instead of a hardcoded dict. Bug found and fixed
      during standalone testing: with only 8 documents, an unrelated made-up
      question still returned a confident answer (no real "no match" zone).
      Raised the similarity threshold (0.35 → 0.45), re-verified against a
      known-negative case.
- [x] **Phase 4 — Integration.** Decision made: true MCP client call, not a
      shared module — new `backend/guideline_client.py` (mirrors `llm_client.py`'s
      one-adapter-file convention) connects to `server.py` over streamable-http.
      Removed the 5-pair block from `draft_generator.py`; added a pre-fetch
      step (concurrent `asyncio.gather` over every EMR medication pair) before
      the existing clinical-status `ask_llm()` call; injected retrieved
      guideline passages into `user_prompt` as `RETRIEVED GUIDELINE CONTEXT`;
      added an optional `source` field to the safety_alerts schema (`extra="allow"`
      needed no schema change). Fails soft on an unreachable guideline server
      (unlike `ask_llm()`, which must raise) — a missing citation degrades
      gracefully, it doesn't break report generation. Added `mcp>=1.2.0` to
      `requirements.txt`.
- [x] **Phase 5 — Verification.** Ran the actual pre-change code (pulled from
      git) side by side with the new code on identical patient data — a real
      before/after, not simulated. Honest finding: the plan expected
      Clarithromycin+Simvastatin to prove "catches what the old system
      missed" — it didn't; the old system caught it too via Claude's own
      training. The real, proven value: every new alert now carries a real,
      checkable NHS source instead of an unsourced AI claim. Regression-checked
      the original 5 pairs (still flagged, now sourced). Ran
      `test_report_quality.py`: 27/28, the 1 miss unrelated (BP severity,
      code this change never touches). `start.sh` updated to auto-start
      `server.py` alongside backend/frontend for local dev.
