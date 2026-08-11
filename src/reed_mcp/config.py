"""Settings read from the environment the MCP host launches this process with."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_URL = "http://localhost:8000"
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_EXCERPT_CHARS = 2000

# The first reed release that ships POST /v1/search.
MIN_REED_VERSION = (0, 5, 0)


@dataclass(frozen=True)
class Settings:
    url: str = DEFAULT_URL
    api_key: str = ""
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_excerpt_chars: int = DEFAULT_MAX_EXCERPT_CHARS

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        source = os.environ if env is None else env
        return cls(
            url=source.get("REED_MCP_URL", DEFAULT_URL).rstrip("/"),
            api_key=source.get("REED_MCP_API_KEY", ""),
            timeout_seconds=_positive_float(
                source, "REED_MCP_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS
            ),
            max_excerpt_chars=_positive_int(
                source, "REED_MCP_MAX_EXCERPT_CHARS", DEFAULT_MAX_EXCERPT_CHARS
            ),
        )


def _positive_float(source: Mapping[str, str], name: str, default: float) -> float:
    raw = source.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {raw!r}")
    return value


def _positive_int(source: Mapping[str, str], name: str, default: int) -> int:
    raw = source.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {raw!r}")
    return value
