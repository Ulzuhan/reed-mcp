import pytest

from reed_mcp.config import (
    DEFAULT_MAX_EXCERPT_CHARS,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_URL,
    Settings,
)


def test_defaults_from_empty_env() -> None:
    settings = Settings.from_env({})
    assert settings.url == DEFAULT_URL
    assert settings.api_key == ""
    assert settings.timeout_seconds == DEFAULT_TIMEOUT_SECONDS
    assert settings.max_excerpt_chars == DEFAULT_MAX_EXCERPT_CHARS


def test_env_overrides() -> None:
    settings = Settings.from_env(
        {
            "REED_MCP_URL": "http://reed.internal:9000/",
            "REED_MCP_API_KEY": "sekrit",
            "REED_MCP_TIMEOUT_SECONDS": "30",
            "REED_MCP_MAX_EXCERPT_CHARS": "500",
        }
    )
    assert settings.url == "http://reed.internal:9000"
    assert settings.api_key == "sekrit"
    assert settings.timeout_seconds == 30.0
    assert settings.max_excerpt_chars == 500


def test_blank_values_fall_back_to_defaults() -> None:
    settings = Settings.from_env(
        {"REED_MCP_TIMEOUT_SECONDS": " ", "REED_MCP_MAX_EXCERPT_CHARS": ""}
    )
    assert settings.timeout_seconds == DEFAULT_TIMEOUT_SECONDS
    assert settings.max_excerpt_chars == DEFAULT_MAX_EXCERPT_CHARS


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("REED_MCP_TIMEOUT_SECONDS", "abc"),
        ("REED_MCP_TIMEOUT_SECONDS", "0"),
        ("REED_MCP_TIMEOUT_SECONDS", "-1"),
        ("REED_MCP_MAX_EXCERPT_CHARS", "abc"),
        ("REED_MCP_MAX_EXCERPT_CHARS", "0"),
        ("REED_MCP_MAX_EXCERPT_CHARS", "2.5"),
    ],
)
def test_invalid_numbers_name_the_variable(name: str, value: str) -> None:
    with pytest.raises(ValueError, match=name):
        Settings.from_env({name: value})
