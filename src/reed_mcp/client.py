"""HTTP client for a reed instance, with errors written for the model that reads them."""

from __future__ import annotations

from typing import Any

import httpx

from reed_mcp.config import Settings


class ReedClientError(Exception):
    """An actionable failure talking to reed; the message is shown to the MCP host."""


class ReedClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        headers = {"X-API-Key": settings.api_key} if settings.api_key else {}
        self._http = httpx.AsyncClient(
            base_url=settings.url,
            headers=headers,
            timeout=settings.timeout_seconds,
        )

    @property
    def url(self) -> str:
        return self._settings.url

    async def aclose(self) -> None:
        await self._http.aclose()

    async def search(self, query: str, top_k: int | None) -> dict[str, Any]:
        body: dict[str, Any] = {"query": query}
        if top_k is not None:
            body["top_k"] = top_k
        return await self._request("POST", "/v1/search", json=body)

    async def ask(self, question: str, top_k: int | None) -> dict[str, Any]:
        body: dict[str, Any] = {"question": question, "stream": False}
        if top_k is not None:
            body["top_k"] = top_k
        return await self._request("POST", "/v1/ask", json=body)

    async def list_documents(self, limit: int, offset: int) -> dict[str, Any]:
        return await self._request(
            "GET", "/v1/documents", params={"limit": limit, "offset": offset}
        )

    async def get_document(self, document_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/v1/documents/{document_id}")

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/health")

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._http.request(method, path, json=json, params=params)
        except httpx.TimeoutException as exc:
            raise ReedClientError(
                f"reed did not answer within {self._settings.timeout_seconds:g}s. "
                "The server may be loading a model or under load; try again, or raise "
                "REED_MCP_TIMEOUT_SECONDS."
            ) from exc
        except httpx.TransportError as exc:
            raise ReedClientError(
                f"reed is not reachable at {self._settings.url}: {exc}. "
                "Is `reed serve` running? If it listens elsewhere, set REED_MCP_URL."
            ) from exc
        if response.status_code >= 400:
            raise ReedClientError(self._describe_failure(response))
        payload: dict[str, Any] = response.json()
        return payload

    def _describe_failure(self, response: httpx.Response) -> str:
        status = response.status_code
        detail = _detail_from(response)
        if status in (401, 403):
            hint = (
                "reed requires an API key and the one supplied was missing or wrong. "
                "Set REED_MCP_API_KEY to the value of the server's REED_API_KEY."
            )
        elif status == 404:
            hint = "Nothing at this id or path. reed_list_documents shows what exists."
        elif status == 429:
            hint = "reed rate-limited the request; wait a moment and retry."
        elif status >= 500:
            hint = "reed reported a server-side failure; check the reed logs."
        else:
            hint = "reed rejected the request."
        suffix = f" reed said: {detail}" if detail else ""
        return f"{hint} (HTTP {status}.){suffix}"


def _detail_from(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    if isinstance(body, dict):
        detail = body.get("detail")
        if isinstance(detail, str):
            return detail
        if detail is not None:
            return str(detail)
    return ""
