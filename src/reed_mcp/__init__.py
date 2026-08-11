"""MCP server for reed: cited evidence from your local documents."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("reed-mcp")
except PackageNotFoundError:  # Source tree imported without being installed.
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
