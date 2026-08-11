# Changelog

All notable changes to reed-mcp are documented here. The project follows Semantic Versioning while
it is pre-1.0: minor releases may change behavior, and patch releases contain compatible fixes.

## [Unreleased]

## [0.1.0] - 2026-08-11

First release. Four read-only tools over a local [reed](https://github.com/Ulzuhan/reed) instance,
spoken over stdio to any MCP host.

### Added

- `reed_search`: ranked evidence with no generation — filename, page, section, score and excerpt,
  for the host's own model to write a cited answer from. reed's evidence threshold is *reported*
  (`sufficient_evidence`, `min_evidence_score`) rather than applied, so the caller decides when to
  abstain instead of having rows withheld from it.
- `reed_ask`: reed's own local model answers, with `[n]` markers and the result of reed's citation
  audit, for when a fully local generation is the requirement.
- `reed_list_documents` and `reed_get_document`: what the index holds and how ingestion went.
- Excerpts are bounded by `REED_MCP_MAX_EXCERPT_CHARS` (default 2000) and marked
  `excerpt_truncated` when cut, so one call cannot flood the host's context.
- Optional authentication: `REED_MCP_API_KEY` is sent as `X-API-Key`, through the process
  environment only — never as a tool argument, and never logged.
- Startup probes reed's `/health` and warns, without refusing to start, when reed is unreachable,
  hides its version, or predates 0.5.0 — the release where `POST /v1/search` first shipped.
- Every reed failure is translated into a message that names the remedy: which process to start,
  which variable to set, which tool to call instead.

### Notes

Requires reed 0.5.0 or newer; 0.5.1 or newer is recommended. Installation is from the repository
rather than from a package index, matching how reed itself is distributed.
