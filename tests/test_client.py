from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from reed_mcp.client import ReedClient, ReedClientError
from reed_mcp.config import Settings

BASE = "http://reed.test"


@pytest.fixture
async def client() -> AsyncIterator[ReedClient]:
    instance = ReedClient(Settings(url=BASE, api_key="k3y", timeout_seconds=5.0))
    yield instance
    await instance.aclose()


@respx.mock
async def test_search_posts_query_and_sends_api_key(client: ReedClient) -> None:
    route = respx.post(f"{BASE}/v1/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "sources": [],
                "latency_ms": 12,
                "sufficient_evidence": False,
                "min_evidence_score": 0.62,
            },
        )
    )
    payload = await client.search("what is the refund policy?", top_k=5)
    assert payload["sufficient_evidence"] is False
    request = route.calls.last.request
    assert request.headers["x-api-key"] == "k3y"
    assert request.read() == b'{"query":"what is the refund policy?","top_k":5}'


@respx.mock
async def test_search_omits_top_k_when_unset(client: ReedClient) -> None:
    route = respx.post(f"{BASE}/v1/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "sources": [],
                "latency_ms": 1,
                "sufficient_evidence": True,
                "min_evidence_score": 0.0,
            },
        )
    )
    await client.search("q", top_k=None)
    assert b"top_k" not in route.calls.last.request.read()


@respx.mock
async def test_no_api_key_header_when_unconfigured() -> None:
    client = ReedClient(Settings(url=BASE))
    route = respx.get(f"{BASE}/health").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    try:
        await client.health()
    finally:
        await client.aclose()
    assert "x-api-key" not in route.calls.last.request.headers


@respx.mock
async def test_ask_disables_streaming(client: ReedClient) -> None:
    route = respx.post(f"{BASE}/v1/ask").mock(
        return_value=httpx.Response(
            200,
            json={
                "answer": "42 [1]",
                "sources": [],
                "latency_ms": 900,
                "citation_status": "ok",
                "citation_warnings": [],
            },
        )
    )
    payload = await client.ask("meaning of life?", top_k=None)
    assert payload["answer"] == "42 [1]"
    assert b'"stream":false' in route.calls.last.request.read()


@respx.mock
async def test_list_documents_passes_paging(client: ReedClient) -> None:
    route = respx.get(f"{BASE}/v1/documents").mock(
        return_value=httpx.Response(
            200, json={"documents": [], "total": 0, "limit": 10, "offset": 20}
        )
    )
    await client.list_documents(limit=10, offset=20)
    assert route.calls.last.request.url.params["limit"] == "10"
    assert route.calls.last.request.url.params["offset"] == "20"


@respx.mock
async def test_unreachable_reed_names_the_url_and_remedy(client: ReedClient) -> None:
    respx.post(f"{BASE}/v1/search").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(ReedClientError, match=r"not reachable at http://reed\.test.*REED_MCP_URL"):
        await client.search("q", top_k=None)


@respx.mock
async def test_timeout_names_the_knob(client: ReedClient) -> None:
    respx.post(f"{BASE}/v1/ask").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(ReedClientError, match="REED_MCP_TIMEOUT_SECONDS"):
        await client.ask("q", top_k=None)


@respx.mock
async def test_401_points_at_the_api_key(client: ReedClient) -> None:
    respx.post(f"{BASE}/v1/search").mock(
        return_value=httpx.Response(401, json={"detail": "Missing or invalid API key"})
    )
    with pytest.raises(ReedClientError, match="REED_MCP_API_KEY") as info:
        await client.search("q", top_k=None)
    assert "Missing or invalid API key" in str(info.value)


@respx.mock
async def test_404_suggests_listing_documents(client: ReedClient) -> None:
    respx.get(f"{BASE}/v1/documents/d-missing").mock(
        return_value=httpx.Response(404, json={"detail": "Document not found"})
    )
    with pytest.raises(ReedClientError, match="reed_list_documents"):
        await client.get_document("d-missing")


@respx.mock
async def test_429_advises_retry(client: ReedClient) -> None:
    respx.post(f"{BASE}/v1/search").mock(
        return_value=httpx.Response(429, json={"detail": "slow down"})
    )
    with pytest.raises(ReedClientError, match="rate-limited"):
        await client.search("q", top_k=None)


@respx.mock
async def test_5xx_mentions_reed_logs_without_json_body(client: ReedClient) -> None:
    respx.post(f"{BASE}/v1/search").mock(return_value=httpx.Response(502, text="Bad Gateway"))
    with pytest.raises(ReedClientError, match="server-side failure"):
        await client.search("q", top_k=None)


def test_construction_does_not_touch_an_event_loop() -> None:
    """The transport must bind to the loop that uses it, not the one that built it.

    A client constructed eagerly outside the serving loop — during a startup
    probe, say — carries a pool tied to a loop that is closed by the time the
    first tool call arrives, and every request then fails with "Event loop is
    closed". Building it on first request is what prevents that.
    """
    instance = ReedClient(Settings(url=BASE))
    assert instance._http is None


async def test_client_works_against_a_real_socket(reed_socket: str) -> None:
    """One test that goes through the actual connection pool, not respx.

    respx answers above the transport, so it cannot show that requests survive
    a real keep-alive connection — which is exactly where the event-loop
    binding that broke every tool call used to hide.
    """
    instance = ReedClient(Settings(url=reed_socket))
    try:
        assert (await instance.health())["version"] == "0.5.1"
        assert (await instance.search("q", top_k=None))["latency_ms"] == 1
    finally:
        await instance.aclose()
