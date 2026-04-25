import os
import pytest
from unittest.mock import patch


def test_raises_when_token_missing():
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("HF_TOKEN", None)
        import importlib
        import hf_client
        importlib.reload(hf_client)
        with pytest.raises(RuntimeError, match="HF_TOKEN"):
            hf_client.get_hf_client()


def test_client_uses_correct_base_url():
    with patch.dict(os.environ, {"HF_TOKEN": "test-token"}):
        from hf_client import get_hf_client, HF_BASE_URL
        client = get_hf_client()
        assert str(client.base_url).rstrip("/") == HF_BASE_URL.rstrip("/")
