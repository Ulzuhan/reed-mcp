import logging
from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from reed_mcp import server
from reed_mcp.config import Settings

BASE = "http://reed.test"

EXPECTED_TOOLS = {"reed_search", "reed_ask", "reed_list_documents", "reed_get_document"}


@pytest.fixture(autouse=True)
async def configured() -> AsyncIterator[None]:
    client = server.configure(Settings(url=BASE, max_excerpt_chars=50))
    yield
    await client.aclose()


def _search_response(excerpt: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "sources": [
                {
                    "n": 1,
                    "doc_id": "d-1",
                    "filename": "handbook.pdf",
                    "page": 3,
                    "section": None,
                    "location": "p. 3",
                    "score": 0.91,
                    "snippet": "short",
                    "excerpt": excerpt,
                }
            ],
            "latency_ms": 20,
            "sufficient_evidence": True,
            "min_evidence_score": 0.62,
        },
    )


async def test_all_four_tools_are_registered_read_only() -> None:
    tools = await server.mcp.list_tools()
    by_name = {tool.name: tool for tool in tools}
    assert set(by_name) == EXPECTED_TOOLS
    for tool in by_name.values():
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False


async def test_tool_descriptions_frame_excerpts_as_data() -> None:
    tools = await server.mcp.list_tools()
    for name in ("reed_search", "reed_ask"):
        description = next(t.description for t in tools if t.name == name)
        assert description is not None
        assert "not instructions" in description


@respx.mock
async def test_search_truncates_long_excerpts() -> None:
    respx.post(f"{BASE}/v1/search").mock(return_value=_search_response("x" * 200))
    payload = await server.reed_search("query")
    source = payload["sources"][0]
    assert len(source["excerpt"]) == 50
    assert source["excerpt_truncated"] is True
    assert payload["sufficient_evidence"] is True


@respx.mock
async def test_search_leaves_short_excerpts_alone() -> None:
    respx.post(f"{BASE}/v1/search").mock(return_value=_search_response("short enough"))
    payload = await server.reed_search("query")
    source = payload["sources"][0]
    assert source["excerpt"] == "short enough"
    assert "excerpt_truncated" not in source


@respx.mock
async def test_client_errors_surface_as_tool_errors() -> None:
    respx.post(f"{BASE}/v1/search").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(ToolError, match="not reachable"):
        await server.reed_search("query")


@respx.mock
async def test_get_document_passes_id_through() -> None:
    route = respx.get(f"{BASE}/v1/documents/d-abc").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "d-abc",
                "logical_id": "l-1",
                "name": "handbook",
                "version": 2,
                "filename": "handbook.pdf",
                "status": "ready",
                "chunks": 12,
                "pages": 30,
                "size_bytes": 1024,
                "created_at": "2026-08-01T00:00:00Z",
                "error": None,
            },
        )
    )
    payload = await server.reed_get_document("d-abc")
    assert payload["status"] == "ready"
    assert route.called


@respx.mock
async def test_check_reed_warns_on_old_version(caplog: pytest.LogCaptureFixture) -> None:
    respx.get(f"{BASE}/health").mock(
        return_value=httpx.Response(200, json={"status": "ok", "version": "0.4.1"})
    )
    with caplog.at_level(logging.WARNING, logger="reed_mcp"):
        await server.check_reed(server._get_client())
    assert "older than the minimum" in caplog.text


@respx.mock
async def test_check_reed_warns_when_version_hidden(caplog: pytest.LogCaptureFixture) -> None:
    respx.get(f"{BASE}/health").mock(
        return_value=httpx.Response(200, json={"status": "ok", "version": None})
    )
    with caplog.at_level(logging.WARNING, logger="reed_mcp"):
        await server.check_reed(server._get_client())
    assert "hides its version" in caplog.text


@respx.mock
async def test_check_reed_survives_unreachable_reed(caplog: pytest.LogCaptureFixture) -> None:
    respx.get(f"{BASE}/health").mock(side_effect=httpx.ConnectError("refused"))
    with caplog.at_level(logging.WARNING, logger="reed_mcp"):
        await server.check_reed(server._get_client())
    assert "health check failed" in caplog.text


@respx.mock
async def test_check_reed_accepts_current_version(caplog: pytest.LogCaptureFixture) -> None:
    respx.get(f"{BASE}/health").mock(
        return_value=httpx.Response(200, json={"status": "ok", "version": "0.5.1"})
    )
    with caplog.at_level(logging.WARNING, logger="reed_mcp"):
        await server.check_reed(server._get_client())
    assert "older than" not in caplog.text
    assert "hides its version" not in caplog.text
