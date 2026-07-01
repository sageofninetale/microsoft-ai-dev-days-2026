"""
LLM Client - Single adapter for every LLM call in the backend.

Every other module (draft_generator, update_agent, intake_agent, protocol_agent,
verification_agent) calls ask_llm() and never touches a provider SDK directly.
That means the next provider/model swap is a one-file change instead of a
five-file hunt through chat.completions.create(...) call sites.

Currently backed by Anthropic's Messages API.

NOTE: claude-3-5-haiku-20241022 (the model originally specified for this
migration) returned HTTP 404 "not_found_error" against this ANTHROPIC_API_KEY
— it does not appear in client.models.list() for this account, i.e. it has
been fully retired, not just renamed. Swapped to claude-haiku-4-5-20251001
(current-generation Haiku, same cost/speed tier) so the migration could be
verified end-to-end. Flagged for coordinator confirmation — change the one
line below if a different model is preferred.
"""

from __future__ import annotations
import os
import json

from anthropic import Anthropic

HF_MODEL = "claude-haiku-4-5-20251001"                                        # model name — change here only, on future swap

_client: Anthropic | None = None                                              # lazily-constructed singleton client


def _get_client() -> Anthropic:
    """Build (once) and return the Anthropic client. Raises if the key is missing."""
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")                              # loaded from project-root .env via load_dotenv() in callers
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY environment variable must be set.")
        _client = Anthropic(api_key=api_key)
    return _client


def _strip_code_fences(text: str) -> str:
    """Strip a ```json ... ``` or ``` ... ``` wrapper if the model added one anyway."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped[3:]
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
        stripped = stripped.strip()
    return stripped


def ask_llm(system_prompt: str, user_prompt: str) -> dict:
    """
    Send a system+user prompt to the configured model, return parsed JSON.
    Raises on failure — callers must not silently swallow errors.
    """
    client = _get_client()

    json_only_system = (
        system_prompt.rstrip()
        + "\n\nReturn valid JSON only. No markdown, no explanation, no code fences."
    )

    response = client.messages.create(                                        # any APIError/RateLimitError/etc. propagates — no catch here
        model=HF_MODEL,
        max_tokens=4096,
        temperature=0.0,
        system=json_only_system,
        messages=[{"role": "user", "content": user_prompt}],
    )

    content = response.content[0].text                                        # Anthropic response shape, not OpenAI's .choices[0].message.content
    content = _strip_code_fences(content)                                      # some models wrap JSON in ```json fences despite the instruction not to
    return json.loads(content)                                                 # malformed JSON raises json.JSONDecodeError — also propagates
