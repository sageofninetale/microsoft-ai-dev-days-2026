"""Guideline MCP Client - the only place draft_generator talks to the standalone
nhs-guideline-mcp server (~/Documents/nhs-guideline-mcp/server.py).

Retrieval fails soft: if the guideline server is unreachable or errors, callers get
None back and proceed with no retrieved passage for that pair — the same behaviour
the app had before this feature existed. Unlike llm_client.ask_llm() (which must
raise on failure so a broken clinical-status call is never mistaken for a clean
report), a missing literature citation is a degraded-but-honest result, not a
silently-faked one, so it is safe to fail soft here.
"""
from __future__ import annotations

import logging
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

log = logging.getLogger("cascadeai.guideline_client")

GUIDELINE_MCP_URL = os.getenv("GUIDELINE_MCP_URL", "http://127.0.0.1:8420/mcp")


async def search_guideline(query: str) -> str | None:
    """Call the standalone guideline MCP server's search_guideline tool.

    Returns the matched, sourced guideline passage, or None if there was no
    confident match or the server could not be reached.
    """
    try:
        async with streamablehttp_client(GUIDELINE_MCP_URL) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("search_guideline", {"query": query})
                text = result.content[0].text if result.content else ""
                if text.startswith("No matching guideline found"):
                    return None
                return text
    except Exception as exc:
        log.warning("Guideline MCP lookup failed for %r: %s", query, exc)
        return None
