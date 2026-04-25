# Plan: Migrate Cascade AI from Azure OpenAI → HF Llama 3.1

**Objective:** Replace `AzureOpenAI` client with `OpenAI` client pointed at HF's OpenAI-compatible router, across all 5 LLM agent files, without breaking the working system.

**Approach:** HF exposes `https://router.huggingface.co/v1` — an OpenAI-compatible endpoint. We keep the `openai` package already installed, change only the client init per file, and all `.chat.completions.create()` calls stay **identical**. Smallest possible diff, lowest possible risk.

**Model:** `meta-llama/Llama-3.1-8B-Instruct` via HF Inference Providers router
**Critical constraint:** `temperature=0.0` everywhere — clinical data must never be paraphrased
**Speech layer:** Azure Speech (intake) + Deepgram (update) — UNTOUCHED
**Fallback:** Azure credentials remain in `.env` as commented reference, not deleted

**Repo:** `sageofninetale/microsoft-ai-dev-days-2026`
**Branch strategy:** Feature branch per step, merged to `main` after verification

## Verified Facts

- `coordinator_agent.py` has **zero LLM calls** — pure orchestrator, no migration needed.
- `api.py` has zero Azure OpenAI imports — only a static Azure URL for hosting. Not touched.
- `response_format={"type": "json_object"}`, `temperature=0.0`, `max_tokens` — all work identically on the HF OpenAI-compatible router.
- `openai` package stays in `requirements.txt` — no new package needed.
- **Free-tier rate limit:** HF free tier ~1 req/second. `draft_generator.py` currently fires 3 concurrent threads — Step 6 serialises these. Re-enable concurrency when upgrading to HF Pro.
- **max_tokens:** Bumped to 4096 for `draft_generator` and `protocol_agent` to avoid mid-JSON truncation on multi-resident notes.

---

## Prerequisites (complete before Step 1)

- [ ] **Accept Meta Llama 3.1 license:** Visit `huggingface.co/meta-llama/Llama-3.1-8B-Instruct` → "Expand to review and access" → fill in details → Agree. Without this, every call returns HTTP 403. (Your request is pending — wait for approval email.)
- [ ] **HF token ready:** `hf_` token from huggingface.co → Settings → Access Tokens. You already have this.
- [ ] **Paste token into `.env`:** Add `HF_TOKEN=hf_your_token_here` before starting Step 1.

---

## Dependency Graph

```
Step 1 (shared helper)
    └── Step 2 (intake_agent)
    └── Step 3 (verification_agent)      ← Steps 2, 3, 4 are PARALLEL (no shared files)
    └── Step 4 (protocol_agent)
            └── Step 5 (update_agent)
            └── Step 6 (draft_generator)  ← Steps 5, 6 are PARALLEL
                    └── Step 7 (integration test + cleanup)
```

---

## Step 1 — Shared client helper

**Branch:** `feat/hf-migration-shared-client`
**Risk:** Low — additive only, no existing code touched

### What changes
Create `backend/hf_client.py` — a thin helper that returns a configured `OpenAI` client pointing at HF's router. All 5 agent files will import this instead of building their own client.

### Tasks
- [ ] Create `backend/hf_client.py`:
  ```python
  import os
  from openai import OpenAI

  HF_MODEL = "meta-llama/Llama-3.1-8B-Instruct"
  HF_BASE_URL = "https://router.huggingface.co/v1"

  def get_hf_client() -> OpenAI:
      token = os.getenv("HF_TOKEN")
      if not token:
          raise RuntimeError("HF_TOKEN environment variable must be set.")
      return OpenAI(base_url=HF_BASE_URL, api_key=token)
  ```
- [ ] Add `HF_TOKEN=` placeholder to `.env` (with comment: `# Get from huggingface.co → Settings → Access Tokens`)
- [ ] Add comment block above Azure vars in `.env`: `# Azure OpenAI — kept as backup reference, not active`
- [ ] Create `backend/test_hf_client.py`:
  ```python
  import os, pytest
  from unittest.mock import patch

  def test_raises_when_token_missing():
      with patch.dict(os.environ, {}, clear=True):
          os.environ.pop("HF_TOKEN", None)
          import importlib, hf_client
          importlib.reload(hf_client)
          with pytest.raises(RuntimeError, match="HF_TOKEN"):
              hf_client.get_hf_client()

  def test_client_uses_correct_base_url():
      with patch.dict(os.environ, {"HF_TOKEN": "test-token"}):
          from hf_client import get_hf_client, HF_BASE_URL
          client = get_hf_client()
          assert str(client.base_url).rstrip("/") == HF_BASE_URL.rstrip("/")
  ```

### Verification
```bash
cd backend
python -c "from hf_client import get_hf_client; print('import OK')"
python -m pytest test_hf_client.py -v
```

### Exit Criteria
- `hf_client.py` imports without error
- `test_hf_client.py` passes (missing token raises RuntimeError, base_url is correct)
- Zero existing tests broken

---

## Step 2 — Migrate `intake_agent.py`

**Branch:** `feat/hf-migration-intake`
**Depends on:** Step 1 merged
**Parallel with:** Steps 3, 4
**Risk:** Medium — first in the handover chain

### What changes
`intake_agent.py` uses `_require_module` to lazy-load `AzureOpenAI`. Replace the client init block with `get_hf_client()`. The single `.chat.completions.create()` call in `extract()` stays **identical** — only add `model=HF_MODEL`. Azure Speech transcription is untouched.

### Tasks
- [ ] Import `get_hf_client, HF_MODEL` from `hf_client`
- [ ] In `__init__`, remove the `_aoai_client` init block (the `_require_module("openai")` lines that build `AzureOpenAI`)
- [ ] In `__init__`, add: `self._hf_client = get_hf_client()`
- [ ] Remove `azure_openai_*` parameters from `__init__` signature (keep `speech_key`, `speech_region`)
- [ ] Remove `_env("AZURE_OPENAI_*")` calls
- [ ] In `extract()`, replace `self._aoai_client.chat.completions.create(...)` with:
  ```python
  response = self._hf_client.chat.completions.create(
      model=HF_MODEL,
      messages=messages,
      temperature=0.0,
      max_tokens=1024,
      response_format={"type": "json_object"},
  )
  ```
- [ ] Update error messages: `"Azure OpenAI returned..."` → `"LLM returned..."`

### Verification
```bash
cd backend
python -m pytest test_intake_api.py -v
python -c "from intake_agent import PatientIntakeAgent; print('import OK')"
```

### Exit Criteria
- `test_intake_api.py` passes
- No `AzureOpenAI` imports remain in this file
- Speech/transcription path unchanged

---

## Step 3 — Migrate `verification_agent.py`

**Branch:** `feat/hf-migration-verification`
**Depends on:** Step 1 merged
**Parallel with:** Steps 2, 4
**Risk:** Low — 1 LLM call, same pattern as intake

### What changes
Same `_require_module` pattern as `intake_agent.py`. One `.chat.completions.create()` call in `verify()`. Supabase EMR query logic untouched.

### Tasks
- [ ] Import `get_hf_client, HF_MODEL` from `hf_client`
- [ ] In `__init__`, remove Azure OpenAI client init, add `self._hf_client = get_hf_client()`
- [ ] Remove `azure_openai_*` parameters from `__init__` signature
- [ ] Replace the single `.chat.completions.create(...)` call — add `model=HF_MODEL`, keep everything else identical
- [ ] Update error messages to remove "Azure OpenAI" references

### Verification
```bash
cd backend
python -m pytest test_verification.py -v
python -c "from verification_agent import VerificationAgent; print('import OK')"
```

### Exit Criteria
- `test_verification.py` passes
- No `AzureOpenAI` imports remain in this file

---

## Step 4 — Migrate `protocol_agent.py`

**Branch:** `feat/hf-migration-protocol`
**Depends on:** Step 1 merged
**Parallel with:** Steps 2, 3
**Risk:** Medium — 2 LLM calls (check both call sites)

### What changes
Same pattern as Steps 2 and 3. Two `.chat.completions.create()` calls (~lines 128 and 157). Both get `model=HF_MODEL` added; everything else stays identical. `max_tokens` bumped to 4096 on both calls to avoid truncation on multi-resident notes.

### Tasks
- [ ] Import `get_hf_client, HF_MODEL` from `hf_client`
- [ ] In `__init__`, remove Azure OpenAI client init, add `self._hf_client = get_hf_client()`
- [ ] Remove `azure_openai_*` parameters from `__init__` signature
- [ ] Replace **both** `.chat.completions.create(...)` calls — add `model=HF_MODEL`, set `max_tokens=4096`, keep `temperature=0.0` and `response_format={"type": "json_object"}` identical
- [ ] Update error messages

### Verification
```bash
cd backend
python -m pytest test_protocol.py -v
python -c "from protocol_agent import ProtocolAgent; print('import OK')"
```

### Exit Criteria
- `test_protocol.py` passes
- Both LLM call sites updated
- No `AzureOpenAI` imports remain

---

## Step 5 — Migrate `update_agent.py`

**Branch:** `feat/hf-migration-update`
**Depends on:** Steps 2, 3, 4 merged
**Parallel with:** Step 6
**Risk:** Medium — direct `from openai import AzureOpenAI` import style, Deepgram untouched

### What changes
`update_agent.py` uses a direct `from openai import AzureOpenAI` import (not `_require_module`). One `.chat.completions.create()` call in `_extract_update_data()` (~line 184). Deepgram speech transcription block is completely untouched.

### Tasks
- [ ] Replace `from openai import AzureOpenAI` with `from hf_client import get_hf_client, HF_MODEL`
- [ ] In `__init__`, remove the `AzureOpenAI(...)` client block (~lines 43–54)
- [ ] In `__init__`, add: `self.hf_client = get_hf_client()`
- [ ] Remove Azure credential env var checks (`openai_endpoint`, `openai_key`, `deployment`)
- [ ] Replace `self.openai_client.chat.completions.create(...)` with:
  ```python
  self.hf_client.chat.completions.create(
      model=HF_MODEL,
      messages=messages,
      temperature=0.0,
      max_tokens=1024,
      response_format={"type": "json_object"},
  )
  ```
- [ ] Update print statement: `"✅ UpdateAgent initialized with HF Llama 3.1"`
- [ ] Deepgram block (`self.deepgram_api_key`, `_transcribe_audio`) — **do not touch**

### Verification
```bash
cd backend
python -m pytest test_update_agent.py -v
python -c "from update_agent import UpdateAgent; print('import OK')"
```

### Exit Criteria
- `test_update_agent.py` passes
- Deepgram transcription path unchanged
- No `AzureOpenAI` imports remain

---

## Step 6 — Migrate `draft_generator.py`

**Branch:** `feat/hf-migration-draft`
**Depends on:** Steps 2, 3, 4 merged
**Parallel with:** Step 5
**Risk:** High — 3 LLM calls, threading (`concurrent.futures`), most complex file

### What changes
`draft_generator.py` uses direct `from openai import AzureOpenAI`. Three `.chat.completions.create()` calls wrapped in lambdas passed to a `concurrent.futures` thread pool (~lines 150, 279, 366).

**Free-tier change:** Replace the thread pool with sequential calls to avoid HTTP 429 on HF free tier. When you upgrade to HF Pro, revert to concurrent pattern.

### Tasks
- [ ] Replace `from openai import AzureOpenAI` with `from hf_client import get_hf_client, HF_MODEL`
- [ ] In `__init__`, remove `AzureOpenAI(...)` block, add `self.hf_client = get_hf_client()`
- [ ] Replace **all 3** lambda-wrapped `self.openai_client.chat.completions.create(...)` calls with direct sequential calls using `self.hf_client.chat.completions.create(model=HF_MODEL, ..., temperature=0.0, max_tokens=4096, response_format={"type": "json_object"})`
- [ ] **Serialise the 3 calls** (remove `concurrent.futures` thread pool — call each one directly in sequence) to stay within HF free-tier rate limits
- [ ] Update error messages to remove "Azure OpenAI" references
- [ ] Add a comment above the sequential calls: `# Sequential for HF free-tier rate limits — restore concurrent.futures when on Pro`

### Verification
```bash
cd backend
python -m pytest test_draft_generator.py -v
python -c "from draft_generator import DraftGenerator; print('import OK')"
```

### Exit Criteria
- `test_draft_generator.py` passes
- All 3 LLM call sites updated
- Calls are sequential (not concurrent) for free-tier compatibility
- No `AzureOpenAI` imports remain

---

## Step 7 — Full integration test + cleanup

**Branch:** `feat/hf-migration-integration`
**Depends on:** Steps 2–6 all merged
**Risk:** Low — verification only, no logic changes

### Tasks
- [ ] Run full coordinator flow: `python -m pytest test_coordinator.py -v`
- [ ] Run edge case tests: `python -m pytest test_edge_cases.py -v`
- [ ] Grep for remaining Azure OpenAI references:
  ```bash
  grep -rn "AzureOpenAI\|azure_openai\|AZURE_OPENAI" backend/ --include="*.py" | grep -v test_ | grep -v ".env"
  ```
  Expected: zero results
- [ ] Check `coordinator_agent.py` and `api.py` — confirm zero Azure OpenAI usage (already verified)
- [ ] Remove `openai>=1.52.0` from `requirements.txt` and add back as plain `openai>=1.52.0` (no version change needed — package stays, just remove Azure-specific note if any)
- [ ] Run `pip install -r requirements.txt` to confirm clean install
- [ ] Delete `test_simple_openai.py` — dead code post-migration: `rm backend/test_simple_openai.py`
- [ ] Update `README.md` model reference from "Azure OpenAI GPT-4" → "Llama 3.1 8B via Hugging Face"
- [ ] **Website copy trigger:** If all tests pass, update `cascadeaicare.com` hero "under two minutes" → "under 20 seconds" (separate task, outside this repo)

### Verification
```bash
cd backend
python -m pytest -v  # full suite
grep -rn "AzureOpenAI" backend/ --include="*.py" | grep -v test_  # must be zero
```

### Exit Criteria
- Full test suite passes
- Zero active Azure OpenAI references in non-test files
- `requirements.txt` reflects actual dependencies
- README updated

---

## Rollback Protocol

If any step produces degraded clinical output quality:

1. Set `HF_TOKEN=` empty in `.env` — agents will raise `RuntimeError` cleanly
2. Re-add Azure vars (already preserved in `.env` as comments — uncomment them)
3. Revert the specific agent file: `git checkout main -- backend/<agent>.py`
4. The speech layer (Azure Speech, Deepgram) is never touched — always recoverable independently

---

## Invariants (verified after every step)

- [ ] `temperature=0.0` in every LLM call
- [ ] `response_format={"type": "json_object"}` in every LLM call
- [ ] `model=HF_MODEL` in every LLM call (never hardcoded string)
- [ ] Speech/transcription code (Azure Speech in intake, Deepgram in update) untouched
- [ ] Supabase/EMR query logic untouched
- [ ] All existing tests pass before moving to next step
- [ ] Azure credentials remain in `.env` as comments (never deleted)

---

## Summary

| Step | File | LLM calls | Parallel? | Risk |
|---|---|---|---|---|
| 1 | `hf_client.py` (new) | — | — | Low |
| 2 | `intake_agent.py` | 1 | With 3, 4 | Medium |
| 3 | `verification_agent.py` | 1 | With 2, 4 | Low |
| 4 | `protocol_agent.py` | 2 | With 2, 3 | Medium |
| 5 | `update_agent.py` | 1 | With 6 | Medium |
| 6 | `draft_generator.py` | 3 | With 5 | High |
| 7 | Integration + cleanup | — | — | Low |

**Total LLM calls migrated: 8**
**Key change per file: swap client init + add `model=HF_MODEL` to each call. Everything else identical.**
