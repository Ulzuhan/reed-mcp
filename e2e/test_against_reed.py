"""End to end: a real MCP session, a real reed, a real document.

The unit tests stub reed out with respx, which proves the wiring but not the
contract. This drives the published entry point exactly as an MCP host does —
spawn the process, speak the protocol over stdio — against a reed that has
actually indexed something.

Point ``REED_MCP_E2E_URL`` at that reed and name the document it holds through
``REED_MCP_E2E_FILENAME`` (default ``handbook.md``); without the URL the module
skips, so ``pytest`` over ``tests/`` stays hermetic.
"""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REED_URL = os.environ.get("REED_MCP_E2E_URL", "")
FILENAME = os.environ.get("REED_MCP_E2E_FILENAME", "handbook.md")

pytestmark = pytest.mark.skipif(
    not REED_URL, reason="set REED_MCP_E2E_URL to a running reed to run the e2e suite"
)

EXPECTED_TOOLS = {"reed_search", "reed_ask", "reed_list_documents", "reed_get_document"}


@asynccontextmanager
async def mcp_session() -> AsyncIterator[ClientSession]:
    """A live MCP session against reed-mcp, launched the way a host launches it.

    Deliberately a context manager used inside each test rather than a fixture:
    the stdio client owns anyio cancel scopes that must be entered and exited in
    the same task, which fixture finalisation does not guarantee.
    """
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "reed_mcp.server"],
        env={**os.environ, "REED_MCP_URL": REED_URL},
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
        await client.initialize()
        yield client


async def _call(session: ClientSession, tool: str, **arguments: Any) -> dict[str, Any]:
    result = await session.call_tool(tool, arguments)
    assert result.isError is False, _text(result)
    assert result.structuredContent is not None, "tools must return structured content"
    return result.structuredContent


def _text(result: Any) -> str:
    return "\n".join(block.text for block in result.content if hasattr(block, "text"))


async def test_host_sees_four_read_only_tools() -> None:
    async with mcp_session() as session:
        listing = await session.list_tools()
        assert {tool.name for tool in listing.tools} == EXPECTED_TOOLS
        for tool in listing.tools:
            assert tool.annotations is not None
            assert tool.annotations.readOnlyHint is True


async def test_search_returns_citable_evidence() -> None:
    async with mcp_session() as session:
        payload = await _call(session, "reed_search", query="expense pre-approval threshold")

    assert payload["sources"], "retrieval found nothing in an index that holds the answer"
    top = payload["sources"][0]
    assert top["filename"] == FILENAME
    assert "75" in top["excerpt"], f"the threshold is not in the top excerpt: {top['excerpt']!r}"
    # What the host needs to attribute the claim, and to decide whether to trust it.
    assert {"n", "doc_id", "filename", "score", "excerpt"} <= set(top)
    assert isinstance(payload["sufficient_evidence"], bool)
    assert isinstance(payload["min_evidence_score"], float)


async def test_search_reports_weak_evidence_without_withholding_it() -> None:
    """The threshold is a verdict, not a filter: the rows come back either way.

    The verdict itself is only meaningful where reed has a calibrated threshold
    for the score domain in use. Its stand-in profiles report ``0.0``, meaning
    "no threshold to judge against", and every verdict there is trivially true —
    so the strong assertion is made only when a threshold actually exists,
    rather than asserting something the environment cannot deliver.
    """
    async with mcp_session() as session:
        payload = await _call(
            session, "reed_search", query="the mating habits of the emperor penguin"
        )

    assert isinstance(payload["sources"], list), "rows must come back regardless of the verdict"
    if payload["min_evidence_score"] > 0:
        assert payload["sufficient_evidence"] is False, (
            "a question the corpus cannot answer cleared the evidence threshold"
        )


async def test_top_k_is_honoured() -> None:
    async with mcp_session() as session:
        payload = await _call(session, "reed_search", query="expenses", top_k=1)

    assert len(payload["sources"]) <= 1


async def test_ask_answers_with_a_citation_marker() -> None:
    async with mcp_session() as session:
        payload = await _call(
            session, "reed_ask", question="What is the expense approval threshold?"
        )

    assert "[1]" in payload["answer"], f"answer carries no citation: {payload['answer']!r}"
    assert payload["sources"]
    assert payload["citation_status"]


async def test_documents_round_trip() -> None:
    async with mcp_session() as session:
        listing = await _call(session, "reed_list_documents")
        ready = [doc for doc in listing["documents"] if doc["status"] == "ready"]
        assert ready, f"no ready documents in {listing}"

        one = await _call(session, "reed_get_document", document_id=ready[0]["id"])

    assert one["id"] == ready[0]["id"]
    assert one["filename"] == ready[0]["filename"]


async def test_unknown_document_fails_with_an_actionable_message() -> None:
    async with mcp_session() as session:
        result = await session.call_tool("reed_get_document", {"document_id": "d-does-not-exist"})

    assert result.isError is True
    assert "reed_list_documents" in _text(result)
