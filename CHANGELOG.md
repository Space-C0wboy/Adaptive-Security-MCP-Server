# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-11-05

### Changed
- Moved to **fastmcp 4** (mcp SDK 2.3). Tool input schemas now carry `additionalProperties: false`, so calls with unexpected arguments are rejected.

### CI
- Workflows run with a read-only token by default; jobs that publish get only the grants they need.
- ruff pinned at 0.17.3 with a `ruff format --check` step; the codebase is formatted.
- The release workflow refuses to publish unless the tag matches the `pyproject.toml` version.
- Dependabot runs weekly with grouped minor/patch updates.

## [0.1.1] - 2026-06-09
### Fixed
- Coerce JSON-string list/object arguments back into real Python values before
  sending. Some MCP clients serialize complex tool arguments — the
  `adaptive_request` `params` object and the `list_audit_logs` `actions` list — as
  a JSON *string*, which the transport rejected ("Input should be a valid
  list/dictionary"). Complex params now also accept a `str` and are coerced via a
  new `coerce_json` helper. Scalar params (ids, cursors, dates) are unaffected.

## [0.1.0] - 2026-06-09
### Added
- Initial release of the Adaptive Security Awareness Training MCP server.
- 15 read-only tools across 5 domains — Audit Logs, Groups, Phishing, Training, and Users —
  generated from the Adaptive OpenAPI specification (v2).
- Generic `adaptive_request` GET escape-hatch tool for endpoints without a dedicated tool.
- Async REST client with Bearer authentication, retry/backoff with full jitter, and a
  capped `Retry-After` honoring policy.
- OpenAPI-driven, deterministic tool generator (`scripts/generate_from_openapi.py`) that
  emits one module per tag plus the `docs/ENDPOINTS.md` catalog; generation is GET-only and
  byte-stable.
- Cursor pagination passthrough (`page_after` / `page_size`) and filter parameters on the
  enrollment and audit-log tools.
- stdio and HTTP transports.
- CI (ruff + pytest on Python 3.10 / 3.11 / 3.12) and PyPI trusted-publishing release
  workflow.
