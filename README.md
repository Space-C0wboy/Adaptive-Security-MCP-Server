# Adaptive Security Awareness Training MCP Server

[![PyPI version](https://img.shields.io/pypi/v/adaptive-mcp.svg)](https://pypi.org/project/adaptive-mcp/)
[![Python versions](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://pypi.org/project/adaptive-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/Space-C0wboy/Adaptive-Security-MCP-Server/actions/workflows/ci.yml/badge.svg)](https://github.com/Space-C0wboy/Adaptive-Security-MCP-Server/actions/workflows/ci.yml)
[![status: beta](https://img.shields.io/badge/status-beta-orange.svg)](#)
[![read-only API](https://img.shields.io/badge/API-read--only-brightgreen.svg)](#read-only-by-design)

A [Model Context Protocol](https://modelcontextprotocol.io) server that exposes the
**Adaptive Security Awareness Training API (v2)** (REST) to AI assistants. It provides
**15 tools across 5 API domains** — Audit Logs, Groups, Phishing, Training, and Users —
plus a generic `adaptive_request` escape hatch for anything not covered by a dedicated
tool. The tool set is **generated directly from the Adaptive OpenAPI specification**, so it
stays faithful to the real API surface, and the generated output is deterministic and
committed.

> [!IMPORTANT]
> **Unofficial project.** This is an independent, internally-built MCP server developed
> against Adaptive Security's published API documentation. It is **not** an official
> Adaptive Security product and is not affiliated with, endorsed by, or supported by
> Adaptive Security. "Adaptive Security" is a trademark of its respective owner. For
> official support of the Adaptive platform or the API itself, contact Adaptive directly.

> [!NOTE]
> **Read-only by design.** Every Adaptive API endpoint this server exposes is an HTTP
> `GET`, and the client only ever issues `GET` requests — including the `adaptive_request`
> escape hatch. **This server cannot create, modify, or delete anything in your Adaptive
> tenant.** There is no write surface and therefore no `READ_ONLY` switch to manage: it is
> always safe to point at production for analyst-assistant, reporting, and dashboard use.

> [!WARNING]
> **Beta software — not yet recommended for unattended production use.** This project is
> under active development; the tool surface may still change between versions, and not
> every endpoint has been exercised against every tenant/entitlement configuration.
>
> - Treat your `ADAPTIVE_API_KEY` with the same care as portal admin credentials. Scope it
>   to the minimum your use case requires.
> - The HTTP transport binds to `127.0.0.1` by default. Do not expose it to the public
>   internet without adding authentication.
> - Keep Claude Desktop's tool-call approval enabled so you can see each request before it runs.

## Tools

**15 tools across 5 domains** (all read-only), plus the `adaptive_request` escape hatch —
**16 total**. The table below groups them by domain.

| Domain | Tools | What it covers |
|--------|-------|----------------|
| **Users** | `list_users`, `get_user` | The org's people directory and per-user detail |
| **Groups** | `list_groups`, `get_group`, `get_group_members` | User groups and their membership |
| **Phishing** | `list_phishing_campaigns`, `get_phishing_campaign`, `list_campaign_simulations`, `get_simulation`, `get_phishing_enrollments` | Phishing simulation campaigns, the individual simulations within them, and per-user enrollment/results |
| **Training** | `list_training_campaigns`, `get_training_campaign`, `get_training_campaign_enrollments` | Security-awareness training campaigns and per-user enrollment/completion |
| **Audit Logs** | `list_audit_logs`, `get_audit_log` | Administrative audit trail, filterable by action type and date range |

See [`docs/ENDPOINTS.md`](docs/ENDPOINTS.md) for the **full tool ↔ method ↔ path mapping** (all
15 tools).

**Highlights:**

- **List tools** (`list_users`, `list_phishing_campaigns`, …) are **cursor-paginated** —
  pass `page_size` and a `page_after` cursor; the response carries the next `page_after`.
  See [Pagination & responses](#pagination--responses).
- **Filter tools** (`get_phishing_enrollments`, `get_training_campaign_enrollments`) narrow
  enrollment data by `user_id` / `campaign_id` / `simulation_id`.
- **`list_audit_logs`** filters the admin audit trail by `start_date`, `end_date`, and a list
  of `actions` (e.g. `CREATED_TRAINING_CAMPAIGN`, `SCHEDULED_TRAINING_CAMPAIGN`, `ADDED_ADMIN`).
- **`adaptive_request` escape hatch** issues a raw `GET` against any path for endpoints
  without a dedicated tool. It is GET-only by construction — it cannot mutate.

## Quick start

### Install

```bash
# with uv (recommended)
uv tool install adaptive-mcp

# or with pip
pip install adaptive-mcp
```

This installs the `adaptive-mcp` console script.

> [!NOTE]
> PyPI publishing is pending the first tagged release — until then, install from source
> (below). A push of a `v*` tag publishes to PyPI via GitHub Actions trusted publishing.

For development from source:

```bash
git clone https://github.com/Space-C0wboy/Adaptive-Security-MCP-Server
cd Adaptive-Security-MCP-Server
uv venv && uv pip install -e ".[dev]"
```

### Getting an API token

1. In the Adaptive Admin portal, go to **Settings → API Tokens**.
2. Create a token and copy it — this is your `ADAPTIVE_API_KEY`.

Requests authenticate with the **`Authorization: Bearer <token>`** header; this server sets
it for you on every request.

### Configuration

Copy `.env.example` to `.env` and set:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ADAPTIVE_API_KEY` | **yes** | — | Your Adaptive API token (Settings → API Tokens) |
| `ADAPTIVE_BASE_URL` | no | `https://api.adaptivesecurity.com` | API root |
| `ADAPTIVE_TIMEOUT` | no | `60` | Request timeout in seconds |
| `LOG_LEVEL` | no | `INFO` | Logging level (logs go to stderr) |
| `MCP_HTTP_HOST` / `MCP_HTTP_PORT` | no | `127.0.0.1:8765` | HTTP transport bind |

### Run

- **stdio** (default, for Claude Desktop/Code): `adaptive-mcp` (or `uv run adaptive-mcp` from source)
- **HTTP**: `adaptive-mcp --transport http --port 8765`

## Pagination & responses

Adaptive list/filter endpoints use **opaque cursor pagination** via two query parameters:

| Parameter | Type | Meaning |
|-----------|------|---------|
| `page_size` | integer | Max records per page. Default **50** for `list_groups`, `list_phishing_campaigns`, `list_campaign_simulations`, and `get_phishing_enrollments`; **100** for every other list/filter tool. |
| `page_after` | string | Opaque cursor for the next page. Omit on the first call; pass the value returned by the previous response. |

**Response envelope:** a list response is an object with the records under a domain-named key
plus the next cursor, e.g.:

```json
{
  "users": [ { "id": "...", "email": "..." } ],
  "page_after": "eyJpZCI6..."
}
```

To page through everything, keep calling the same tool with `page_after` set to the value
from the previous response until `page_after` comes back empty/absent.

Filter parameters on specific tools:

| Tool | Filters |
|------|---------|
| `get_phishing_enrollments` | `user_id`, `campaign_id`, `simulation_id` |
| `get_training_campaign_enrollments` | `user_id`, `campaign_id` |
| `list_audit_logs` | `start_date`, `end_date`, `actions` (list of action types) |

## Editor integration

### Claude Code

```bash
claude mcp add adaptive \
  --env ADAPTIVE_API_KEY=your-token-here \
  -- adaptive-mcp
```

From source (not yet installed as a tool):

```bash
claude mcp add adaptive \
  --env ADAPTIVE_API_KEY=your-token-here \
  -- uv run --directory /absolute/path/to/Adaptive-Security-MCP-Server adaptive-mcp
```

### Claude Desktop

Edit `claude_desktop_config.json`:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "adaptive": {
      "command": "adaptive-mcp",
      "env": {
        "ADAPTIVE_API_KEY": "your-token-here"
      }
    }
  }
}
```

If running from source instead of an installed tool, use `uv` with `--directory`:

```json
{
  "mcpServers": {
    "adaptive": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/Adaptive-Security-MCP-Server", "adaptive-mcp"],
      "env": { "ADAPTIVE_API_KEY": "your-token-here" }
    }
  }
}
```

Restart Claude Desktop, then confirm `adaptive` appears in the tools menu.

## Example prompts

- *"List the first 25 users."* → `list_users` (`page_size=25`).
- *"Get the details for user `<id>`."* → `get_user` (`userId=<id>`).
- *"What groups do we have, and who's in the Finance group?"* → `list_groups` → `get_group_members` (`groupId=<id>`).
- *"Show our phishing campaigns and the simulations in campaign `<id>`."* →
  `list_phishing_campaigns` → `list_campaign_simulations` (`campaignId=<id>`).
- *"How did user `<id>` do on the phishing simulations?"* → `get_phishing_enrollments` (`user_id=<id>`).
- *"Which users haven't completed training campaign `<id>`?"* →
  `get_training_campaign_enrollments` (`campaign_id=<id>`).
- *"Show admin actions in the last week."* → `list_audit_logs`
  (`start_date`, `end_date`, `actions=["ADDED_ADMIN", "CREATED_TRAINING_CAMPAIGN"]`).
- *"Call an endpoint I don't have a dedicated tool for."* → `adaptive_request` (`path`, optional `params`).

## How tools are generated

The tool modules are generated from the Adaptive OpenAPI specification:

```bash
uv run python scripts/generate_from_openapi.py
```

This regenerates the modules under `src/adaptive_mcp/tools/_generated/` and the catalog at
[`docs/ENDPOINTS.md`](docs/ENDPOINTS.md). The generated files are **not hand-edited** — to
change a tool, edit the generator (its `OVERRIDES` map) and regenerate. Generation is
deterministic, so re-running it produces a byte-identical, reviewable diff.

The OpenAPI spec and other Adaptive reference material live in the **`Source Material/`**
directory, which is **gitignored** (vendor reference material, not redistributed). CI installs
from the committed `_generated/` modules and does not regenerate.

Key generator behavior:
- Operations are grouped by OpenAPI tag into one module per domain.
- Only `GET` operations are generated (the API is read-only); path parameters are interpolated
  into the URL and query parameters are forwarded with their spec defaults.
- Tool names are the snake_case form of each `operationId`.

## Development

```bash
uv run pytest        # full suite (httpx fully mocked; no live calls)
uv run ruff check .  # lint
uv run python scripts/generate_from_openapi.py  # regenerate tools + ENDPOINTS.md
```

CI runs ruff + pytest on Python 3.10 / 3.11 / 3.12 (see `.github/workflows/ci.yml`). A pushed
`v*` tag builds and publishes to PyPI via trusted publishing (see `.github/workflows/release.yml`).

## License

[MIT](LICENSE)

## Support

This is an unofficial, internal project. For Adaptive platform or API questions, contact
Adaptive Security directly. For issues with this MCP server, open an issue on the
[GitHub repository](https://github.com/Space-C0wboy/Adaptive-Security-MCP-Server/issues).
