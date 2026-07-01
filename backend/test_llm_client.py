"""
Tests for backend/llm_client.py — the single adapter every LLM call site
goes through. Replaces test_hf_client.py (tested the now-deleted hf_client.py
against Groq-specific behavior; broken since the Anthropic migration).

No live API calls here — client construction and JSON parsing are tested
against mocks so this suite runs without ANTHROPIC_API_KEY / network access.
"""

import os
import json
import importlib
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest


def test_raises_when_api_key_missing():
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        import llm_client
        importlib.reload(llm_client)
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            llm_client._get_client()


def test_client_is_anthropic_instance():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        import llm_client
        importlib.reload(llm_client)
        client = llm_client._get_client()
        from anthropic import Anthropic
        assert isinstance(client, Anthropic)


def test_client_is_cached_singleton():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        import llm_client
        importlib.reload(llm_client)
        first = llm_client._get_client()
        second = llm_client._get_client()
        assert first is second


def _mock_response(text: str):
    """Build a fake anthropic Messages response with a single text content block."""
    return SimpleNamespace(content=[SimpleNamespace(text=text)])


def test_ask_llm_parses_plain_json():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        import llm_client
        importlib.reload(llm_client)

        fake_client = MagicMock()
        fake_client.messages.create.return_value = _mock_response('{"ok": true}')
        llm_client._client = fake_client

        result = llm_client.ask_llm("system prompt", "user prompt")
        assert result == {"ok": True}

        # model/temperature/max_tokens contract — callers rely on these being fixed
        _, kwargs = fake_client.messages.create.call_args
        assert kwargs["model"] == llm_client.HF_MODEL
        assert kwargs["temperature"] == 0.0
        assert kwargs["max_tokens"] == 4096
        assert "Return valid JSON only" in kwargs["system"]


def test_ask_llm_strips_markdown_code_fences():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        import llm_client
        importlib.reload(llm_client)

        fake_client = MagicMock()
        fake_client.messages.create.return_value = _mock_response(
            '```json\n{"ok": true}\n```'
        )
        llm_client._client = fake_client

        result = llm_client.ask_llm("system prompt", "user prompt")
        assert result == {"ok": True}


def test_ask_llm_raises_on_malformed_json():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        import llm_client
        importlib.reload(llm_client)

        fake_client = MagicMock()
        fake_client.messages.create.return_value = _mock_response("not json at all")
        llm_client._client = fake_client

        with pytest.raises(json.JSONDecodeError):
            llm_client.ask_llm("system prompt", "user prompt")


def test_ask_llm_does_not_catch_api_errors():
    """ask_llm() must never swallow a failure into a fallback dict — this is
    the exact bug the Anthropic migration fixed. Confirm it stays fixed."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        import llm_client
        importlib.reload(llm_client)

        fake_client = MagicMock()
        fake_client.messages.create.side_effect = RuntimeError("simulated 429")
        llm_client._client = fake_client

        with pytest.raises(RuntimeError, match="simulated 429"):
            llm_client.ask_llm("system prompt", "user prompt")
