# reed-mcp

**Give your AI assistant your private documents — without a single byte leaving your machine.**

`reed-mcp` is an [MCP](https://modelcontextprotocol.io) server for
[reed](https://github.com/Ulzuhan/reed), the local-first RAG service with audited
citations. It exposes reed's retrieval to any MCP host (Claude Desktop, Claude
Code, …) over stdio: the host's model gets ranked, citable evidence from your
own index, and everything — documents, queries, retrieval — stays local.

> Status: pre-release. The full case study (architecture, measurements) lands
> with v0.1.0.

## Tools

| Tool | What it does |
|---|---|
| `reed_search` | Ranked evidence with filenames, pages and scores — **the host's model writes the answer** and cites it. Reports reed's evidence-threshold verdict (`sufficient_evidence`) without withholding results. |
| `reed_ask` | reed's own local LLM answers, with evidence-aware abstention and audited `[n]` citations. |
| `reed_list_documents` | What the index contains, with ingestion status. |
| `reed_get_document` | Status and metadata of one document. |

All four tools are read-only.

## Requirements

- A running reed instance, **v0.5.0 or newer** (`/v1/search` is required; 0.5.1+ recommended)
- [uv](https://docs.astral.sh/uv/) on the machine that runs the MCP host

## Use it with Claude Code

```bash
claude mcp add reed -- uvx reed-mcp
```

## Use it with Claude Desktop

```json
{
  "mcpServers": {
    "reed": {
      "command": "uvx",
      "args": ["reed-mcp"]
    }
  }
}
```

## Configuration

Everything is environment variables — never tool arguments:

| Variable | Default | Meaning |
|---|---|---|
| `REED_MCP_URL` | `http://localhost:8000` | Where `reed serve` listens |
| `REED_MCP_API_KEY` | empty | Sent as `X-API-Key`; set it to the server's `REED_API_KEY` when reed requires one |
| `REED_MCP_TIMEOUT_SECONDS` | `120` | Per-request timeout |
| `REED_MCP_MAX_EXCERPT_CHARS` | `2000` | Excerpts longer than this are truncated (`excerpt_truncated: true`) |

## Security model

- Retrieved excerpts are **quoted document content, not instructions**. The tool
  descriptions say so to the model, and reed itself audits citations — but no
  server can semantically sanitize your documents. Index what you trust.
- Credentials travel only via environment variables, never through the tool
  channel, and are never logged.
- The server is read-only: it cannot upload, replace or delete documents.

## Development

```bash
git clone https://github.com/Ulzuhan/reed-mcp.git
cd reed-mcp
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

## License

Apache-2.0.
