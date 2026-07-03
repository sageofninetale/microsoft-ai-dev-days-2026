"""
Shared backend configuration.

CANONICAL APP: backend/api.py is the canonical FastAPI application (full handoff
workflow, used by the frontend, start.sh, and the Dockerfile CMD `api:app`).
backend/main.py is a minimal legacy intake-only endpoint kept for the hackathon
demos; it now shares the same locked-down CORS allowlist below.
"""

from __future__ import annotations

import os

# Explicit CORS allowlist. Never use "*" together with allow_credentials=True.
# Override in deployment via ALLOWED_ORIGINS (comma-separated).
_DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8888",
    "http://127.0.0.1:8888",
    "https://happy-sand-07c137903.6.azurestaticapps.net",
]

_env_origins = os.getenv("ALLOWED_ORIGINS")
ALLOWED_ORIGINS = (
    [o.strip() for o in _env_origins.split(",") if o.strip()]
    if _env_origins
    else list(_DEFAULT_ALLOWED_ORIGINS)
)

# Expose interactive API docs only when explicitly enabled (off in production).
DOCS_ENABLED = os.getenv("ENABLE_DOCS", "false").lower() in ("1", "true", "yes")

# Max size of a base64-encoded audio payload accepted by /api/transcribe.
# 15 MB of base64 (~11 MB of decoded audio) is ample for a spoken handoff clip.
MAX_AUDIO_B64_CHARS = int(os.getenv("MAX_AUDIO_B64_CHARS", str(15 * 1024 * 1024)))
MAX_AUDIO_DECODED_BYTES = int(os.getenv("MAX_AUDIO_DECODED_BYTES", str(11 * 1024 * 1024)))
