# Adaptive Security MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io) server that exposes the
**Adaptive Security Awareness Training API (v2)** to AI assistants. It provides **15
tools across 5 domains** — Audit Logs, Groups, Phishing, Training, and Users — plus a
generic `adaptive_request` GET escape hatch for anything not covered by a dedicated
tool. Tools are generated from the published OpenAPI spec, so they stay faithful to the
real API surface.

> **Unofficial project.** Independent, community-built MCP server developed against
> Adaptive Security's published API documentation. Not affiliated with or endorsed by
> Adaptive Security. The Adaptive API is **read-only** (all endpoints are `GET`), so this
> server cannot modify your tenant.

## Tools

15 generated tools + the `adaptive_request` escape hatch.

| Domain | Tools |
|--------|-------|
| Audit Logs | `list_audit_logs`, `get_audit_log` |
| Groups | `list_groups`, `get_group`, `get_group_members` |
| Phishing | `list_phishing_campaigns`, `get_phishing_campaign`, `list_campaign_simulations`, `get_simulation`, `get_phishing_enrollments` |
| Training | `list_training_campaigns`, `get_training_campaign`, `get_training_campaign_enrollments` |
| Users | `list_users`, `get_user` |

List tools are cursor-paginated (`page_after` / `page_size`). See
[`docs/ENDPOINTS.md`](docs/ENDPOINTS.md) for the full tool ↔ endpoint mapping.

## Quick start

```bash
git clone <repo-url>
cd adaptive-mcp-server
uv venv && uv pip install -e ".[dev]"
```

### Getting an API token

Generate a token in the Adaptive Admin portal: **Settings → API Tokens**. Requests
authenticate with `Authorization: Bearer <token>`.

### Configuration

Copy `.env.example` to `.env` and set:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ADAPTIVE_API_KEY` | **yes** | — | Your Adaptive API token |
| `ADAPTIVE_BASE_URL` | no | `https://api.adaptivesecurity.com` | API root |
| `ADAPTIVE_TIMEOUT` | no | `60` | Request timeout in seconds |
| `LOG_LEVEL` | no | `INFO` | Logging level |
| `MCP_HTTP_HOST` / `MCP_HTTP_PORT` | no | `127.0.0.1:8765` | HTTP transport bind |

### Run

- stdio (default): `uv run adaptive-mcp`
- HTTP: `uv run adaptive-mcp --transport http --port 8765`

## Editor integration

### Claude Desktop

Edit `claude_desktop_config.json` (Windows: `%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "adaptive": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/adaptive-mcp-server", "adaptive-mcp"],
      "env": { "ADAPTIVE_API_KEY": "your-token-here" }
    }
  }
}
```

### Claude Code

```bash
claude mcp add adaptive --env ADAPTIVE_API_KEY=your-token-here -- uv run --directory /absolute/path/to/adaptive-mcp-server adaptive-mcp
```

## Example prompts

- *"List the 25 most recent users."* → `list_users` (`page_size: 25`).
- *"Show phishing campaigns and their simulations."* → `list_phishing_campaigns` → `list_campaign_simulations`.
- *"Which users haven't completed training campaign X?"* → `get_training_campaign_enrollments` (`campaign_id: X`).
- *"Show audit log actions in the last week."* → `list_audit_logs` (`start_date`, `end_date`, `actions`).

## How tools are generated

```bash
uv run python scripts/generate_from_openapi.py
```

Regenerates `src/adaptive_mcp/tools/_generated/` and `docs/ENDPOINTS.md` from
`Source Material/openapi.json`. Generated files are **not hand-edited** — change the
generator and regenerate.

## Development

```bash
uv run pytest        # full suite (HTTP fully mocked; no live calls)
uv run ruff check .  # lint
```

## License

[MIT](LICENSE)
