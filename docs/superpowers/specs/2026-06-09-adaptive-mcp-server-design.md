# Adaptive Security MCP Server — Design

**Date:** 2026-06-09
**Status:** Approved (design); pending implementation plan
**Author:** Kierston Grantham

## Summary

A [Model Context Protocol](https://modelcontextprotocol.io) server that exposes the
**Adaptive Security Awareness Training API (v2)** to AI assistants. It is modeled on the
existing **ReliaQuest GreyMatter MCP Server** so that it reads as a sibling project
(same `config / client / errors / server / tools/_generated` skeleton, same testing and
packaging conventions), but adapted from GraphQL to REST.

The Adaptive API is small and entirely read-only: **15 `GET` endpoints across 5 domains**
(Audit Logs, Groups, Phishing, Training, Users), bearer-token auth, cursor pagination.
The server exposes **15 generated tools + 1 generic escape-hatch tool**.

### Source material

- `Source Material/openapi.json` — Adaptive API OpenAPI 3.1 spec (the generator's input).
- `Source Material/Adaptive API Documentation.pdf` — human-readable API reference.
- `Source Material/Reliaquest-Greymatter-MCP-Server-main/` — the reference implementation
  whose architecture this project mirrors.

## API facts (from `openapi.json`)

- **OpenAPI:** 3.1.0 · **API version:** v2
- **Server:** `https://api.adaptivesecurity.com`
- **Auth:** HTTP bearer (`Authorization: Bearer <token>`). Token from the Adaptive Admin
  portal (Settings → API Tokens).
- **All 15 operations are `GET`** — there are no mutations.
- **Pagination:** cursor-based via `page_after` (string) + `page_size` (integer, with
  per-endpoint defaults).

### Endpoint inventory

| operationId | Method · Path | Tag | Path params | Query params |
|---|---|---|---|---|
| `listAuditLogs` | GET `/v2/audit-logs` | Audit Logs | — | `page_after`, `page_size`, `start_date`, `end_date`, `actions[]` |
| `getAuditLog` | GET `/v2/audit-logs/{auditLogId}` | Audit Logs | `auditLogId`* | — |
| `listGroups` | GET `/v2/groups` | Groups | — | `page_after`, `page_size` |
| `getGroup` | GET `/v2/groups/{groupId}` | Groups | `groupId`* | — |
| `getGroupMembers` | GET `/v2/groups/{groupId}/users` | Groups | `groupId`* | `page_after`, `page_size` |
| `listPhishingCampaigns` | GET `/v2/phishing/campaigns` | Phishing | — | `page_after`, `page_size` (default 50) |
| `getPhishingEnrollments` | GET `/v2/phishing/campaigns/enrollments` | Phishing | — | `user_id`, `campaign_id`, `simulation_id`, `page_after`, `page_size` |
| `getPhishingCampaign` | GET `/v2/phishing/campaigns/{campaignId}` | Phishing | `campaignId`* | — |
| `listCampaignSimulations` | GET `/v2/phishing/campaigns/{campaignId}/simulations` | Phishing | `campaignId`* | `page_after`, `page_size` |
| `getSimulation` | GET `/v2/phishing/simulations/{simulationId}` | Phishing | `simulationId`* | — |
| `listTrainingCampaigns` | GET `/v2/training/campaigns` | Training | — | `page_after`, `page_size` |
| `getTrainingCampaignEnrollments` | GET `/v2/training/campaigns/enrollments` | Training | — | `user_id`, `campaign_id`, `page_after`, `page_size` |
| `getTrainingCampaign` | GET `/v2/training/campaigns/{campaignId}` | Training | `campaignId`* | — |
| `listUsers` | GET `/v2/users` | Users | — | `page_after`, `page_size` (default 100) |
| `getUser` | GET `/v2/users/{userId}` | Users | `userId`* | — |

\* required

## Goals / Non-goals

**Goals**
- Faithful, discoverable coverage of all 15 Adaptive endpoints as individual MCP tools.
- Same look-and-feel, conventions, and quality bar as the GreyMatter reference.
- Tools generated from `openapi.json` so they stay faithful to the real API surface and
  are regenerable if the API grows.
- A generic GET escape hatch for endpoints not yet covered.
- Robust transport (retry/backoff, clean error mapping) and a fully-mocked test suite.

**Non-goals**
- No write/mutation support (the API has none).
- No `READ_ONLY` flag or mutation-gating (moot — the whole API is read-only).
- No OpCo/`customer_slug` header concept (Adaptive has no multi-tenant header).
- No response reshaping — tools return the API's JSON as-is.

## Architecture

```
src/adaptive_mcp/
  __init__.py            # __version__
  config.py              # env-driven Config (no READ_ONLY)
  errors.py              # AdaptiveAPIError
  client.py              # async httpx REST client (Bearer auth, retry/backoff)
  server.py              # build_server() + main(); stdio + http transports
  tools/
    __init__.py          # register_all()
    _common.py           # drop_none + execute_request() helper
    request.py           # adaptive_request escape hatch (GET-only)
    _generated/
      __init__.py        # GENERATED_MODULES list
      audit_logs.py      # list_audit_logs, get_audit_log
      groups.py          # list_groups, get_group, get_group_members
      phishing.py        # list_phishing_campaigns, get_phishing_campaign,
                         #   list_campaign_simulations, get_simulation, get_phishing_enrollments
      training.py        # list_training_campaigns, get_training_campaign,
                         #   get_training_campaign_enrollments
      users.py           # list_users, get_user
scripts/
  generate_from_openapi.py   # openapi.json -> _generated/* + docs/ENDPOINTS.md
tests/
  fixtures/
  test_config.py
  test_client.py
  test_common.py
  test_request_tool.py
  test_registration.py
  test_generator.py
docs/ENDPOINTS.md
pyproject.toml · README.md · .env.example · .gitignore · LICENSE · .github/workflows/ci.yml
```

### Components

**`config.py`** — Frozen `Config` dataclass loaded once from the environment (with
`.env` support via python-dotenv), `get_config()` singleton + `reset_config_cache()` test
hook, `ConfigError` for bad config. Ports the GreyMatter module verbatim minus
`READ_ONLY` and `CUSTOMER_SLUG`.

| Env var | Required | Default | Notes |
|---|---|---|---|
| `ADAPTIVE_API_KEY` | **yes** | — | Bearer token; `ConfigError` if missing |
| `ADAPTIVE_BASE_URL` | no | `https://api.adaptivesecurity.com` | trailing slash trimmed; must be http(s) |
| `ADAPTIVE_TIMEOUT` | no | `60` | per-request seconds (float) |
| `LOG_LEVEL` | no | `INFO` | upper-cased |
| `MCP_HTTP_HOST` | no | `127.0.0.1` | HTTP transport bind |
| `MCP_HTTP_PORT` | no | `8765` | HTTP transport bind |

**`errors.py`** — `AdaptiveAPIError(status_code, message, body=None)`. (No GraphQL error
class; REST signals failure via status codes.)

**`client.py`** — `AdaptiveClient` wrapping one shared `httpx.AsyncClient` (one connection
pool), built lazily inside the event loop and guarded by a lock. Defaults set once:
`Authorization: Bearer <key>`, `Accept: application/json`, `User-Agent: adaptive-mcp/<ver>`.
Process-wide `get_client()` / `shutdown_client()` singleton helpers (ported from GreyMatter).

Core method:
```python
async def request(self, path: str, *, params: dict | None = None) -> Any
```
- Issues `GET base_url + path` with `params` as the query string.
- **Retry policy ported verbatim from GreyMatter:** retry on `{429, 500, 502, 503, 504}`
  and network errors, up to 3 attempts, exponential backoff with full jitter, honoring a
  capped (`60s`) `Retry-After` header.
- On `>= 400`: parse a JSON error body for a `message`/`error` field (fall back to raw
  text) and raise `AdaptiveAPIError`. On network exhaustion: `AdaptiveAPIError(0, ...)`.
  On non-JSON success body: `AdaptiveAPIError`.
- On success: return the parsed JSON.

`path` already has its path params interpolated by the calling tool (the client stays
unaware of route templates). The escape hatch passes a raw `path` straight through.

**`tools/_common.py`** — `drop_none(params)` (omit unset query args) and
`execute_request(path, params=None)` which calls `get_client().request(...)` after
`drop_none`. (No `coerce_json` — REST query params are scalars/arrays, not JSON-string
input objects. `actions[]` is passed as a list and httpx serializes repeated query params.)

**`tools/_generated/*` (generated)** — One module per OpenAPI tag. Each module exposes
`register(mcp)` and, per operation, an async tool function:
- Path params → required `str` parameters, interpolated into the path template.
- Query params → optional parameters typed from the spec (`str`/`int`/`list[str]`), with
  spec defaults (e.g. `page_size`), collected into a `params` dict.
- Tool `name` = snake_case of `operationId`; `description` = spec `summary` + a generated
  param/usage hint.
- Body calls `execute_request(path, params)`.

Generated files carry a "DO NOT EDIT BY HAND" header and are excluded from lint rules
(matching the reference). All tools are always registered (no read-only gating).

**`tools/request.py`** — `adaptive_request(path: str, params: dict | None = None)`:
GET-only generic tool that calls `execute_request(path, params)`. Documented as the
escape hatch for endpoints without a dedicated tool. (GET-only is inherent — the client
only issues GETs.)

**`tools/__init__.py`** — `register_all(mcp)` iterates `GENERATED_MODULES` calling each
`register(mcp)`, then registers `adaptive_request`.

**`server.py`** — `build_server()` validates config early, configures logging to **stderr**
(stdout is the stdio JSON-RPC channel), constructs `FastMCP(name="adaptive-mcp",
instructions=...)`, and calls `register_all`. `main()` parses `--transport {stdio,http}`
/ `--host` / `--port`, runs the server, and best-effort `shutdown_client()` on exit.
Instructions string describes the 5 domains, cursor pagination, and the escape hatch.

### Generator (`scripts/generate_from_openapi.py`)

Reads `Source Material/openapi.json`, groups operations by tag, and emits:
- one `_generated/<tag>.py` module per tag (slugified filename),
- `_generated/__init__.py` exporting `GENERATED_MODULES`,
- `docs/ENDPOINTS.md` cataloging tool ↔ endpoint mappings.

Mirrors the GreyMatter generator's design: a per-module `_OPS` table holding each
operation's path template + method + ordered param specs, generated function signatures
with `Annotated[... , Field(...)]` typing, and an `OVERRIDES` map for any tool-name or
description tweaks. Generated output must be deterministic, importable, and ruff-clean
(within the per-file ignores). The generator is the source of truth — generated files are
never hand-edited.

## Data flow

```
assistant → MCP tool (e.g. get_user(userId="123"))
  → tool interpolates path "/v2/users/123", builds params dict
  → execute_request(path, params)  [drop_none]
  → AdaptiveClient.request(GET base_url+path?params)  [auth, retry, error mapping]
  → returns parsed JSON  → assistant
```

## Error handling

- Missing/invalid config → `ConfigError`, surfaced by `main()` as a clean message + exit
  code 2 (no traceback).
- `>= 400` responses → `AdaptiveAPIError` with status + extracted message + raw body.
- Transient `429`/`5xx` + network errors → retried (3 attempts, jittered backoff,
  capped `Retry-After`); exhaustion raises `AdaptiveAPIError`.
- Non-JSON success body → `AdaptiveAPIError`.
- `401/403` (bad/expired token) surface immediately as `AdaptiveAPIError` (not retried).

## Testing

Pytest with `pytest-asyncio` (auto mode) and `pytest-httpx`; **all HTTP mocked — no live
calls**, matching the reference.

- `test_config.py` — required key enforced; defaults; bad URL/timeout → `ConfigError`;
  cache reset.
- `test_client.py` — Bearer header sent; success returns JSON; `>=400` → `AdaptiveAPIError`
  with extracted message; retry on 429/503 then success; `Retry-After` honored + capped;
  network error exhaustion; non-JSON body.
- `test_common.py` — `drop_none`; `execute_request` wiring.
- `test_request_tool.py` — `adaptive_request` forwards path/params and returns JSON.
- `test_registration.py` — all 15 generated tools + `adaptive_request` register; names as
  expected.
- `test_generator.py` — generate into a temp dir from a mini OpenAPI fixture; output
  imports cleanly and registers tools.

## Packaging & tooling

`pyproject.toml` mirroring the reference (hatchling build, ruff, pytest config):
- name `adaptive-mcp`, package `adaptive_mcp`, `requires-python >=3.10`, MIT.
- deps: `fastmcp>=2,<3`, `httpx>=0.27,<1`, `pydantic>=2.6,<3`, `python-dotenv>=1,<2`.
- dev: `pytest`, `pytest-asyncio`, `pytest-httpx`, `ruff`.
- script: `adaptive-mcp = adaptive_mcp.server:main`.
- ruff: line-length 100; `_generated/*` exempt from style rules.

Supporting files: `README.md` (quick start, config table, editor integration for Claude
Desktop / Claude Code, tool catalog, example prompts), `.env.example`, `.gitignore`,
`LICENSE` (MIT), `.github/workflows/ci.yml` (lint + test on 3.10–3.12). The
`Source Material/` directory is git-ignored (vendor reference material, not redistributed).

## Open items / defaults chosen

- Package/CLI name: **`adaptive-mcp`** / `adaptive_mcp`.
- Env prefix: **`ADAPTIVE_`**.
- Tool names derived from `operationId` (snake_case).
- Generator reads `Source Material/openapi.json` (path configurable in the script).
