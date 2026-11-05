# Adaptive Security MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python MCP server that exposes the Adaptive Security Awareness Training REST API (v2) to AI assistants as 15 generated tools plus a generic GET escape hatch, modeled on the ReliaQuest GreyMatter MCP Server.

**Architecture:** A small FastMCP server with a layered skeleton — `config` (env-validated settings) → `client` (shared async httpx client with retry/backoff and Bearer auth) → `tools` (one generated module per OpenAPI tag, each a thin async wrapper that builds a path + query params and calls a shared `execute_request` helper) → `server` (wires it together, stdio + http transports). Tools are generated from `Source Material/openapi.json` by `scripts/generate_from_openapi.py`; generated files are committed but never hand-edited.

**Tech Stack:** Python ≥3.10, [FastMCP](https://github.com/jlowin/fastmcp) (`fastmcp>=2,<3`), `httpx`, `pydantic` v2, `python-dotenv`; `uv` for env/deps; `pytest` + `pytest-asyncio` + `pytest-httpx` for tests (all HTTP mocked); `ruff` for lint.

**Reference:** `Source Material/Reliaquest-Greymatter-MCP-Server-main/` is the sibling project this mirrors. The design spec is `docs/superpowers/specs/2026-06-09-adaptive-mcp-server-design.md`.

**Conventions for every task:**
- Run commands from the repo root `C:\Users\kierstong\source\repos\adaptive-mcp-server`.
- `python` is not on PATH; use `uv run ...` for Python commands.
- After a task's tests pass, also run `uv run ruff check .` before committing.

---

### Task 1: Project scaffolding, packaging, and git init

**Files:**
- Create: `pyproject.toml`
- Create: `src/adaptive_mcp/__init__.py`
- Create: `tests/__init__.py` (empty)
- Init: git repository (`.gitignore` and `.env`/`.env.example` already exist)

- [ ] **Step 1: Initialize git**

Run:
```bash
git init
```
Expected: "Initialized empty Git repository". (`.gitignore` already ignores `.env`, `Source Material/`, and Python artifacts.)

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "adaptive-mcp"
version = "0.1.0"
description = "MCP server for the Adaptive Security Awareness Training API"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
license-files = []
authors = [
    { name = "Kierston Grantham" },
]
keywords = ["mcp", "adaptive", "security", "awareness-training", "phishing", "ai-tools", "claude"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Information Technology",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Security",
    "Typing :: Typed",
]
dependencies = [
    "fastmcp>=2.0.0,<3.0",
    "httpx>=0.27.0,<1.0",
    "pydantic>=2.6.0,<3.0",
    "python-dotenv>=1.0.0,<2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0,<9.0",
    "pytest-asyncio>=0.23.0,<2.0",
    "pytest-httpx>=0.30.0,<1.0",
    "ruff>=0.4.0,<1.0",
]

[project.scripts]
adaptive-mcp = "adaptive_mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/adaptive_mcp"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "W"]
ignore = ["E501", "B008"]

[tool.ruff.lint.isort]
known-first-party = ["adaptive_mcp"]

[tool.ruff.lint.per-file-ignores]
"src/adaptive_mcp/tools/_generated/*" = ["E", "W", "B", "UP"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src", "."]
```

(`pythonpath = ["src", "."]` lets tests import `adaptive_mcp` from `src/` and load the generator script by path from the repo root.)

- [ ] **Step 3: Create `src/adaptive_mcp/__init__.py`**

```python
"""Adaptive Security Awareness Training MCP server."""

from __future__ import annotations

__version__ = "0.1.0"
```

- [ ] **Step 4: Create empty `tests/__init__.py`**

```python
```

- [ ] **Step 5: Create the virtual environment and install**

Run:
```bash
uv venv
uv pip install -e ".[dev]"
```
Expected: environment created; `adaptive-mcp`, `fastmcp`, `httpx`, `pydantic`, `pytest`, etc. installed without errors.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/adaptive_mcp/__init__.py tests/__init__.py .gitignore .env.example docs/
git commit -m "chore: scaffold adaptive-mcp project (packaging, package skeleton, design docs)"
```

---

### Task 2: Configuration module (`config.py`)

**Files:**
- Create: `src/adaptive_mcp/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import pytest

from adaptive_mcp.config import Config, ConfigError, get_config, reset_config_cache


def _set_env(monkeypatch, **over):
    monkeypatch.delenv("ADAPTIVE_API_KEY", raising=False)
    for k, v in over.items():
        monkeypatch.setenv(k, v)
    reset_config_cache()


def test_requires_api_key(monkeypatch):
    _set_env(monkeypatch)
    with pytest.raises(ConfigError):
        Config.from_env()


def test_defaults(monkeypatch):
    _set_env(monkeypatch, ADAPTIVE_API_KEY="tok")
    cfg = Config.from_env()
    assert cfg.api_key == "tok"
    assert cfg.base_url == "https://api.adaptivesecurity.com"
    assert cfg.timeout == 60.0
    assert cfg.log_level == "INFO"
    assert cfg.http_host == "127.0.0.1"
    assert cfg.http_port == 8765


def test_base_url_trailing_slash_trimmed(monkeypatch):
    _set_env(monkeypatch, ADAPTIVE_API_KEY="tok", ADAPTIVE_BASE_URL="https://x.example/")
    assert Config.from_env().base_url == "https://x.example"


def test_bad_base_url_scheme(monkeypatch):
    _set_env(monkeypatch, ADAPTIVE_API_KEY="tok", ADAPTIVE_BASE_URL="ftp://nope")
    with pytest.raises(ConfigError):
        Config.from_env()


def test_bad_timeout(monkeypatch):
    _set_env(monkeypatch, ADAPTIVE_API_KEY="tok", ADAPTIVE_TIMEOUT="abc")
    with pytest.raises(ConfigError):
        Config.from_env()


def test_get_config_is_cached(monkeypatch):
    _set_env(monkeypatch, ADAPTIVE_API_KEY="tok")
    assert get_config() is get_config()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adaptive_mcp.config'`.

- [ ] **Step 3: Write `src/adaptive_mcp/config.py`**

```python
"""Server configuration, loaded once from the environment.

Everything controlling how the MCP server connects to the Adaptive API and how it
behaves is sourced from environment variables here (with optional ``.env`` support
via python-dotenv for local development). Values are parsed and validated up front
into an immutable ``Config`` dataclass so the rest of the codebase relies on a
single, already-validated source of truth.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load a local .env (if present) into os.environ at import time.
load_dotenv()


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid.

    Distinct from runtime API errors: this signals a setup/deployment problem
    (e.g. a missing API key) that must be fixed before the server can start.
    """


@dataclass(frozen=True)
class Config:
    """Immutable, validated snapshot of the server's runtime configuration."""

    api_key: str  # ADAPTIVE_API_KEY — bearer token (required)
    base_url: str  # ADAPTIVE_BASE_URL — API root, trailing slash trimmed
    timeout: float  # ADAPTIVE_TIMEOUT — per-request timeout in seconds
    log_level: str  # LOG_LEVEL — standard logging level name, upper-cased
    http_host: str  # MCP_HTTP_HOST — bind host for the HTTP transport
    http_port: int  # MCP_HTTP_PORT — bind port for the HTTP transport

    @classmethod
    def from_env(cls) -> Config:
        """Build a ``Config`` by reading and validating environment variables.

        Raises:
            ConfigError: if the API key is missing, the base URL is malformed, or
                a numeric field cannot be parsed. Validation happens here so
                misconfiguration fails fast at startup.
        """
        api_key = os.getenv("ADAPTIVE_API_KEY", "").strip()
        if not api_key:
            raise ConfigError(
                "ADAPTIVE_API_KEY is required. Set it in your environment or .env file."
            )

        base_url = (
            os.getenv("ADAPTIVE_BASE_URL", "https://api.adaptivesecurity.com")
            .strip()
            .rstrip("/")
        )
        if not base_url.startswith(("http://", "https://")):
            raise ConfigError(
                f"ADAPTIVE_BASE_URL must start with http:// or https:// (got {base_url!r})"
            )

        try:
            timeout = float(os.getenv("ADAPTIVE_TIMEOUT", "60"))
        except ValueError as e:
            raise ConfigError(f"ADAPTIVE_TIMEOUT must be a number: {e}") from e

        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        http_host = os.getenv("MCP_HTTP_HOST", "127.0.0.1")
        try:
            http_port = int(os.getenv("MCP_HTTP_PORT", "8765"))
        except ValueError as e:
            raise ConfigError(f"MCP_HTTP_PORT must be an integer: {e}") from e

        return cls(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            log_level=log_level,
            http_host=http_host,
            http_port=http_port,
        )


_config: Config | None = None


def get_config() -> Config:
    """Return the process-wide ``Config``, building it on first use."""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def reset_config_cache() -> None:
    """Clear the cached config so the next ``get_config()`` re-reads the env.

    Intended for tests that tweak environment variables.
    """
    global _config
    _config = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/adaptive_mcp/config.py tests/test_config.py
git commit -m "feat: env-validated Config module"
```

---

### Task 3: Errors module (`errors.py`)

**Files:**
- Create: `src/adaptive_mcp/errors.py`
- Test: `tests/test_errors.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_errors.py
from adaptive_mcp.errors import AdaptiveAPIError


def test_api_error_attributes_and_str():
    err = AdaptiveAPIError(401, "unauthorized", body={"message": "bad token"})
    assert err.status_code == 401
    assert err.message == "unauthorized"
    assert err.body == {"message": "bad token"}
    assert "401" in str(err)
    assert "unauthorized" in str(err)


def test_api_error_body_optional():
    err = AdaptiveAPIError(0, "Network error: boom")
    assert err.body is None
    assert err.status_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adaptive_mcp.errors'`.

- [ ] **Step 3: Write `src/adaptive_mcp/errors.py`**

```python
"""Exception types raised by the Adaptive API client."""

from __future__ import annotations

from typing import Any


class AdaptiveAPIError(RuntimeError):
    """Transport-level or non-2xx HTTP failure talking to the Adaptive API.

    Raised when the connection failed, a request exhausted its retries, the
    server returned a status code outside 2xx, or a success body could not be
    decoded as JSON. The attributes carry enough context to log or display the
    failure and to branch on the status code.

    Args:
        status_code: The HTTP status returned by the server (or a synthetic ``0``
            when no real response was received).
        message: Human-readable description of what went wrong.
        body: The raw response body, when available, for debugging/logging.
    """

    def __init__(self, status_code: int, message: str, body: Any = None):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.body = body
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_errors.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/adaptive_mcp/errors.py tests/test_errors.py
git commit -m "feat: AdaptiveAPIError exception type"
```

---

### Task 4: Async REST client (`client.py`)

**Files:**
- Create: `src/adaptive_mcp/client.py`
- Test: `tests/test_client.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_client.py
import httpx
import pytest

from adaptive_mcp.client import AdaptiveClient, _MAX_RETRY_AFTER_SECONDS, _parse_retry_after
from adaptive_mcp.config import Config
from adaptive_mcp.errors import AdaptiveAPIError


def _cfg(**over):
    base = dict(
        api_key="tok",
        base_url="https://api.example.com",
        timeout=5.0,
        log_level="INFO",
        http_host="127.0.0.1",
        http_port=8765,
    )
    base.update(over)
    return Config(**base)


async def test_get_returns_json_and_sends_bearer(httpx_mock):
    httpx_mock.add_response(json={"data": [], "page": {}})
    client = AdaptiveClient(_cfg())
    out = await client.request("/v2/users", params={"page_size": 10})
    assert out == {"data": [], "page": {}}
    req = httpx_mock.get_request()
    assert req.headers["authorization"] == "Bearer tok"
    assert str(req.url) == "https://api.example.com/v2/users?page_size=10"
    await client.close()


async def test_http_error_raises_with_message(httpx_mock):
    httpx_mock.add_response(status_code=401, json={"message": "unauthorized"})
    client = AdaptiveClient(_cfg())
    with pytest.raises(AdaptiveAPIError) as ei:
        await client.request("/v2/users")
    assert ei.value.status_code == 401
    assert "unauthorized" in ei.value.message
    await client.close()


async def test_retries_on_503_then_succeeds(httpx_mock):
    httpx_mock.add_response(status_code=503)
    httpx_mock.add_response(json={"ok": True})
    client = AdaptiveClient(_cfg())
    out = await client.request("/v2/users")
    assert out == {"ok": True}
    assert len(httpx_mock.get_requests()) == 2
    await client.close()


async def test_retries_on_network_error_then_succeeds(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("boom"))
    httpx_mock.add_response(json={"ok": True})
    client = AdaptiveClient(_cfg())
    out = await client.request("/v2/users")
    assert out == {"ok": True}
    assert len(httpx_mock.get_requests()) == 2
    await client.close()


async def test_raises_after_exhausting_retries_on_5xx(httpx_mock):
    for _ in range(3):
        httpx_mock.add_response(status_code=503)
    client = AdaptiveClient(_cfg())
    with pytest.raises(AdaptiveAPIError):
        await client.request("/v2/users")
    assert len(httpx_mock.get_requests()) == 3
    await client.close()


async def test_non_json_success_body_raises(httpx_mock):
    httpx_mock.add_response(status_code=200, text="not json", headers={"content-type": "text/plain"})
    client = AdaptiveClient(_cfg())
    with pytest.raises(AdaptiveAPIError):
        await client.request("/v2/users")
    await client.close()


def test_parse_retry_after_seconds_and_cap():
    assert _parse_retry_after("2") == 2.0
    assert _parse_retry_after(None) is None
    assert _parse_retry_after("not-a-date") is None
    assert _parse_retry_after("120") == 120.0
    assert _MAX_RETRY_AFTER_SECONDS == 60.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adaptive_mcp.client'`.

- [ ] **Step 3: Write `src/adaptive_mcp/client.py`**

```python
"""Async REST client for the Adaptive API.

This is the network transport layer. The server and the generated tools speak to
Adaptive exclusively through :class:`AdaptiveClient`, so authentication, retry/
backoff, error handling, and connection pooling live in one place.

Every Adaptive operation is an HTTP ``GET`` against the same base URL with a path
and optional query parameters, so the client is deliberately thin — it knows how
to send a GET safely and interpret the result, not anything about specific routes.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from . import __version__
from .config import Config, get_config
from .errors import AdaptiveAPIError

logger = logging.getLogger(__name__)

# 429 (rate limited) plus common 5xx gateway/server errors are transient; a 4xx
# like 400/401/403 is permanent and surfaced immediately.
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_MAX_RETRIES = 3
# Cap on how long we honor a server-provided Retry-After, so a hostile upstream
# can't park the server for hours.
_MAX_RETRY_AFTER_SECONDS = 60.0


def _parse_retry_after(header_value: str | None) -> float | None:
    """Parse an HTTP ``Retry-After`` header into a number of seconds to wait.

    Handles both the integer-seconds form (``Retry-After: 30``) and the
    absolute HTTP-date form. Returns ``None`` if the header is missing or
    unparseable (caller falls back to its own backoff). Never negative.
    """
    if not header_value:
        return None
    value = header_value.strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


class AdaptiveClient:
    """Thin async wrapper over the Adaptive REST API.

    One instance owns one :class:`httpx.AsyncClient` (one connection pool). The
    httpx client is created lazily on first use because it must be constructed
    inside a running event loop.

    Auth: every request sends ``Authorization: Bearer <api_key>`` (set once as a
    default header on the underlying httpx client).
    """

    def __init__(self, config: Config | None = None):
        self._config = config or get_config()
        self._client: httpx.AsyncClient | None = None
        self._connect_lock = asyncio.Lock()

    async def __aenter__(self) -> AdaptiveClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.close()

    async def connect(self) -> None:
        """Create the underlying httpx client if one does not already exist.

        Idempotent and concurrency-safe (double-checked under a lock). Constant
        headers (auth, content negotiation, User-Agent) are set as defaults here.
        """
        async with self._connect_lock:
            if self._client is None:
                self._client = httpx.AsyncClient(
                    timeout=self._config.timeout,
                    headers={
                        "Authorization": f"Bearer {self._config.api_key}",
                        "Accept": "application/json",
                        "User-Agent": f"adaptive-mcp/{__version__}",
                    },
                )

    async def close(self) -> None:
        """Close the connection pool and reset to the disconnected state."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def request(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        """Issue ``GET base_url + path`` with optional query params; return JSON.

        Args:
            path: The path portion of the URL, e.g. ``/v2/users/123``. Path
                parameters are already interpolated by the calling tool.
            params: Optional query parameters. httpx serializes list values as
                repeated query keys.

        Returns:
            The parsed JSON body on success.

        Raises:
            AdaptiveAPIError: on HTTP ``>= 400``, a network failure that exhausts
                all retries, or an undecodable (non-JSON) success body.

        Transient failures (network errors and retryable 429/5xx statuses) are
        retried up to ``_MAX_RETRIES`` times with exponential backoff and full
        jitter. A server ``Retry-After`` takes precedence (capped).
        """
        if self._client is None:
            await self.connect()
        assert self._client is not None

        url = self._config.base_url + path

        next_backoff: float | None = None
        for attempt in range(_MAX_RETRIES):
            if next_backoff is not None:
                logger.warning(
                    "Retry %d/%d — backing off %.2fs", attempt, _MAX_RETRIES - 1, next_backoff
                )
                await asyncio.sleep(next_backoff)
                next_backoff = None

            try:
                response = await self._client.get(url, params=params)
            except httpx.HTTPError as e:
                if attempt == _MAX_RETRIES - 1:
                    raise AdaptiveAPIError(0, f"Network error: {e}") from e
                logger.warning("Network error on attempt %d: %s", attempt + 1, e)
                next_backoff = random.uniform(0, 2**attempt)
                continue

            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES - 1:
                retry_after = _parse_retry_after(response.headers.get("retry-after"))
                next_backoff = (
                    min(retry_after, _MAX_RETRY_AFTER_SECONDS)
                    if retry_after is not None
                    else random.uniform(0, 2**attempt)
                )
                logger.warning("HTTP %d — will retry", response.status_code)
                continue

            if response.status_code >= 400:
                try:
                    body: Any = response.json()
                except ValueError:
                    body = response.text
                message = (
                    body.get("message") or body.get("error") or str(body)
                    if isinstance(body, dict)
                    else str(body)
                )
                raise AdaptiveAPIError(response.status_code, message, body)

            try:
                return response.json()
            except ValueError as e:
                raise AdaptiveAPIError(
                    response.status_code, f"Non-JSON response: {e}", response.text
                ) from e

        raise AdaptiveAPIError(0, "Max retries exceeded")  # pragma: no cover


# Process-wide singleton client plus a lock guarding its creation/teardown.
_client: AdaptiveClient | None = None
_client_lock = asyncio.Lock()


async def get_client() -> AdaptiveClient:
    """Return the process-wide shared client, creating it on first call."""
    global _client
    async with _client_lock:
        if _client is None:
            _client = AdaptiveClient()
            await _client.connect()
    return _client


async def shutdown_client() -> None:
    """Close and discard the shared client, releasing its connection pool."""
    global _client
    async with _client_lock:
        if _client is not None:
            await _client.close()
            _client = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_client.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/adaptive_mcp/client.py tests/test_client.py
git commit -m "feat: async REST client with Bearer auth, retry/backoff"
```

---

### Task 5: Shared tool helper (`tools/_common.py`)

**Files:**
- Create: `src/adaptive_mcp/tools/__init__.py` (temporary stub — replaced in Task 9)
- Create: `src/adaptive_mcp/tools/_common.py`
- Test: `tests/test_common.py`

- [ ] **Step 1: Create the temporary package stub**

Create `src/adaptive_mcp/tools/__init__.py` with exactly:
```python
"""Tool registry for the Adaptive MCP server."""
```
(This is a placeholder so `tools` is importable now; Task 9 replaces it with `register_all`.)

- [ ] **Step 2: Write the failing test**

```python
# tests/test_common.py
import pytest

from adaptive_mcp.tools import _common


def test_drop_none_removes_unset():
    assert _common.drop_none({"a": 1, "b": None, "c": "x"}) == {"a": 1, "c": "x"}


def test_drop_none_empty():
    assert _common.drop_none({}) == {}


async def test_execute_request_forwards_path_and_params(monkeypatch):
    seen = {}

    class FakeClient:
        async def request(self, path, *, params=None):
            seen["path"] = path
            seen["params"] = params
            return {"ok": True}

    async def fake_get_client():
        return FakeClient()

    monkeypatch.setattr(_common, "get_client", fake_get_client)
    out = await _common.execute_request("/v2/users", {"page_size": 10, "page_after": None})
    assert out == {"ok": True}
    assert seen["path"] == "/v2/users"
    # None values are dropped before the request is sent.
    assert seen["params"] == {"page_size": 10}


async def test_execute_request_no_params(monkeypatch):
    seen = {}

    class FakeClient:
        async def request(self, path, *, params=None):
            seen["params"] = params
            return {}

    async def fake_get_client():
        return FakeClient()

    monkeypatch.setattr(_common, "get_client", fake_get_client)
    await _common.execute_request("/v2/users/1")
    assert seen["params"] == {}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_common.py -v`
Expected: FAIL — `AttributeError: module 'adaptive_mcp.tools._common' has no attribute ...` (or import error for `_common`).

- [ ] **Step 4: Write `src/adaptive_mcp/tools/_common.py`**

```python
"""Shared helpers used by every generated Adaptive tool.

The generated domain tools are thin wrappers: each builds its path and a dict of
query parameters, then hands them here to actually run. Centralizing that keeps
the generated code small and puts the one argument-normalization rule in one
place: ``drop_none`` (don't send query params the caller left unset).
"""

from __future__ import annotations

from typing import Any

from ..client import get_client


def drop_none(params: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``params`` with all ``None`` values removed.

    Unset optional query arguments arrive as ``None``; sending them would clutter
    the query string (and could be rejected), so we omit them entirely.
    """
    return {k: v for k, v in params.items() if v is not None}


async def execute_request(
    path: str,
    params: dict[str, Any] | None = None,
) -> Any:
    """Run a GET through the shared client, dropping unset query params.

    Args:
        path: The request path (path parameters already interpolated).
        params: Optional query parameters; ``None`` values are dropped.

    Returns:
        The JSON payload returned by the client.
    """
    client = await get_client()
    cleaned = drop_none(params or {})
    return await client.request(path, params=cleaned)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_common.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add src/adaptive_mcp/tools/__init__.py src/adaptive_mcp/tools/_common.py tests/test_common.py
git commit -m "feat: shared execute_request helper for tools"
```

---

### Task 6: Generic escape-hatch tool (`tools/request.py`)

**Files:**
- Create: `src/adaptive_mcp/tools/request.py`
- Test: `tests/test_request_tool.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_request_tool.py
import adaptive_mcp.tools.request as request_tool
from fastmcp import FastMCP


async def test_adaptive_request_registered_and_forwards(monkeypatch):
    seen = {}

    async def fake_execute_request(path, params=None):
        seen["path"] = path
        seen["params"] = params
        return {"ok": True}

    monkeypatch.setattr(request_tool, "execute_request", fake_execute_request)

    mcp = FastMCP(name="test")
    request_tool.register(mcp)
    tools = await mcp.get_tools()
    assert "adaptive_request" in tools

    out = await tools["adaptive_request"].fn(path="/v2/groups", params={"page_size": 5})
    assert out == {"ok": True}
    assert seen["path"] == "/v2/groups"
    assert seen["params"] == {"page_size": 5}
```

> Note: `mcp.get_tools()` returns a dict of tool name → Tool object; `.fn` is the
> underlying coroutine. If the installed FastMCP version exposes a different
> accessor, adapt the lookup but keep the two assertions (registered + forwards).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_request_tool.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adaptive_mcp.tools.request'`.

- [ ] **Step 3: Write `src/adaptive_mcp/tools/request.py`**

```python
"""The generic ``adaptive_request`` escape-hatch tool.

Not every Adaptive endpoint necessarily has a dedicated generated tool. This
catch-all runs a raw ``GET`` against an arbitrary path so an AI assistant can
reach any read endpoint, including ones added after the tools were generated.
The Adaptive API is entirely read-only, so this is GET-only by construction.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from ._common import execute_request


def register(mcp: FastMCP) -> None:
    """Register the ``adaptive_request`` tool on the FastMCP server."""

    @mcp.tool(
        name="adaptive_request",
        description=(
            "Issue a raw GET request against the Adaptive API for endpoints not "
            "covered by a dedicated tool. Provide the path (e.g. '/v2/users' or "
            "'/v2/users/{id}') and an optional dict of query parameters. The "
            "Adaptive API is read-only, so only GET is supported."
        ),
    )
    async def adaptive_request(
        path: Annotated[
            str,
            Field(description="Request path beginning with '/', e.g. '/v2/phishing/campaigns'."),
        ],
        params: Annotated[
            dict | None,
            Field(default=None, description="Optional query parameters as a JSON object."),
        ] = None,
    ) -> Any:
        return await execute_request(path, params)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_request_tool.py -v`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add src/adaptive_mcp/tools/request.py tests/test_request_tool.py
git commit -m "feat: adaptive_request GET escape-hatch tool"
```

---

### Task 7: OpenAPI tool generator (`scripts/generate_from_openapi.py`)

This task builds the generator and tests its pure helper functions plus a full
generate-into-tmp run from a mini fixture. The generator is NOT run against the
real spec until Task 8.

**Files:**
- Create: `scripts/generate_from_openapi.py`
- Create: `tests/fixtures/mini_openapi.json`
- Test: `tests/test_generator.py`

- [ ] **Step 1: Create the mini fixture `tests/fixtures/mini_openapi.json`**

```json
{
  "openapi": "3.1.0",
  "info": { "title": "Mini", "version": "v2" },
  "servers": [{ "url": "https://api.example.com" }],
  "paths": {
    "/v2/users": {
      "get": {
        "operationId": "listUsers",
        "summary": "List users",
        "tags": ["Users"],
        "parameters": [
          { "name": "page_after", "in": "query", "required": false, "schema": { "type": "string" } },
          { "name": "page_size", "in": "query", "required": false, "schema": { "type": "integer", "default": 100 } }
        ]
      }
    },
    "/v2/users/{userId}": {
      "get": {
        "operationId": "getUser",
        "summary": "Get user details",
        "tags": ["Users"],
        "parameters": [
          { "name": "userId", "in": "path", "required": true, "schema": { "type": "string" } }
        ]
      }
    },
    "/v2/audit-logs": {
      "get": {
        "operationId": "listAuditLogs",
        "summary": "List audit logs",
        "tags": ["Audit Logs"],
        "parameters": [
          { "name": "actions", "in": "query", "required": false, "schema": { "type": "array", "items": { "type": "string" } } }
        ]
      }
    }
  }
}
```

- [ ] **Step 2: Write the failing test `tests/test_generator.py`**

```python
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path("scripts/generate_from_openapi.py")
FIXTURE = Path("tests/fixtures/mini_openapi.json")


def _load_generator():
    spec = importlib.util.spec_from_file_location("gen", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_tool_name_snake_case():
    gen = _load_generator()
    assert gen.tool_name("listUsers") == "list_users"
    assert gen.tool_name("getUser") == "get_user"
    assert gen.tool_name("getGroupMembers") == "get_group_members"
    assert gen.tool_name("getTrainingCampaignEnrollments") == "get_training_campaign_enrollments"


def test_module_name():
    gen = _load_generator()
    assert gen.module_name("Audit Logs") == "audit_logs"
    assert gen.module_name("Phishing") == "phishing"
    name = gen.module_name("123 Weird")
    assert name.isidentifier() and not name[0].isdigit()


def test_py_type_mapping():
    gen = _load_generator()
    assert gen.py_type({"type": "string"}, required=True) == "str"
    assert gen.py_type({"type": "string"}, required=False) == "str | None"
    assert gen.py_type({"type": "integer"}, required=False) == "int | None"
    assert gen.py_type({"type": "boolean"}, required=False) == "bool | None"
    assert gen.py_type({"type": "array"}, required=False) == "list | None"
    assert gen.py_type({}, required=False) == "Any | None"


def test_generate_writes_modules(tmp_path):
    gen = _load_generator()
    out_dir = tmp_path / "_generated"
    docs = tmp_path / "ENDPOINTS.md"
    gen.generate(spec_path=FIXTURE, out_dir=out_dir, endpoints_doc=docs)

    users = (out_dir / "users.py").read_text()
    assert "def register(mcp" in users
    assert 'name="list_users"' in users
    assert 'name="get_user"' in users
    # path param interpolated via f-string, query params forwarded
    assert 'f"/v2/users/{userId}"' in users
    assert '"/v2/users"' in users

    init = (out_dir / "__init__.py").read_text()
    assert "GENERATED_MODULES" in init
    assert "users" in init and "audit_logs" in init

    assert docs.read_text().count("list_users") >= 1


def test_generated_modules_compile(tmp_path):
    gen = _load_generator()
    out_dir = tmp_path / "_generated"
    gen.generate(spec_path=FIXTURE, out_dir=out_dir, endpoints_doc=tmp_path / "E.md")
    for py in out_dir.glob("*.py"):
        compile(py.read_text(), str(py), "exec")


def test_duplicate_operation_id_raises(tmp_path):
    gen = _load_generator()
    spec = {
        "openapi": "3.1.0",
        "info": {"title": "Dup", "version": "v2"},
        "paths": {
            "/a": {"get": {"operationId": "dup", "tags": ["X"], "parameters": []}},
            "/b": {"get": {"operationId": "dup", "tags": ["X"], "parameters": []}},
        },
    }
    p = tmp_path / "dup.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    with pytest.raises(ValueError):
        gen.generate(spec_path=p, out_dir=tmp_path / "_g", endpoints_doc=tmp_path / "E.md")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_generator.py -v`
Expected: FAIL — `FileNotFoundError`/`exec_module` error because the script doesn't exist.

- [ ] **Step 4: Write `scripts/generate_from_openapi.py`**

```python
"""Generate FastMCP tool modules from the Adaptive API OpenAPI spec.

This MCP server exposes the Adaptive REST API to MCP clients as a set of typed
tools. Rather than hand-write a tool per endpoint, we treat the vendor's OpenAPI
document as the source of truth and *generate* one FastMCP tool module per
OpenAPI tag.

What this script produces, given the spec:
  - src/adaptive_mcp/tools/_generated/<tag>.py — one module per OpenAPI tag, each
    exposing a `register(mcp)` that wires up that tag's tools.
  - src/adaptive_mcp/tools/_generated/__init__.py — imports every module and lists
    them in GENERATED_MODULES so the server can register them all in one pass.
  - docs/ENDPOINTS.md — a human-readable catalog of every generated tool.

Usage:
    python scripts/generate_from_openapi.py [SPEC_JSON]

Defaults to "Source Material/openapi.json".

Determinism: the same spec must always yield byte-identical output, so modules and
operations are sorted into a fixed order and files are written with explicit LF
newlines.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DEFAULT_SPEC = Path("Source Material/openapi.json")
DEFAULT_OUT_DIR = Path("src/adaptive_mcp/tools/_generated")
DEFAULT_DOC = Path("docs/ENDPOINTS.md")

_HTTP_METHODS = ("get", "post", "put", "patch", "delete")

# OpenAPI scalar type -> Python annotation. Unknown/absent types -> Any.
_TYPE_MAP = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "array": "list",
}

# Optional per-operation description overrides, keyed by operationId. Only the
# description text is overridden; signatures are always derived from the spec.
OVERRIDES: dict[str, str] = {}


def tool_name(op_id: str) -> str:
    """Convert a camelCase operationId to a snake_case MCP tool name."""
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", op_id)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower()


def module_name(tag: str) -> str:
    """Convert an OpenAPI tag into a valid snake_case module filename stem."""
    s = tag.strip().replace("-", " ").replace("/", " ")
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", s)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    s = re.sub(r"[^a-z0-9_]", "", s.lower())
    s = re.sub(r"_+", "_", s).strip("_")
    if not s or s[0].isdigit():
        s = "mod_" + s
    return s


def py_type(schema: dict, *, required: bool) -> str:
    """Map an OpenAPI parameter schema to a Python annotation string."""
    base = _TYPE_MAP.get((schema or {}).get("type"), "Any")
    return base if required else f"{base} | None"


def _default_literal(schema: dict) -> str:
    """Return the Python literal for a query param's default (``None`` if absent)."""
    if schema and "default" in schema:
        return repr(schema["default"])
    return "None"


def collect(spec: dict) -> dict[str, list[dict]]:
    """Parse every GET operation into normalized per-module op records.

    Returns an ordered dict: module name -> list of op dicts (op_id, method, path,
    summary, path_params, query_params), sorted deterministically.

    Raises:
        ValueError: if two operations share an operationId (would collide on a
            tool name).
    """
    by_module: dict[str, list[dict]] = {}
    seen: set[str] = set()
    for path in sorted(spec.get("paths", {})):
        item = spec["paths"][path]
        for method in _HTTP_METHODS:
            op = item.get(method)
            if not op:
                continue
            op_id = op.get("operationId")
            if not op_id:
                continue
            if op_id in seen:
                raise ValueError(f"Duplicate operationId: {op_id!r}")
            seen.add(op_id)
            tags = op.get("tags") or ["Misc"]
            mod = module_name(tags[0])
            params = op.get("parameters", [])
            path_params = [p for p in params if p.get("in") == "path"]
            query_params = [p for p in params if p.get("in") == "query"]
            by_module.setdefault(mod, []).append(
                {
                    "op_id": op_id,
                    "method": method,
                    "path": path,
                    "summary": op.get("summary", "") or "",
                    "tag": tags[0],
                    "path_params": path_params,
                    "query_params": query_params,
                }
            )
    for ops in by_module.values():
        ops.sort(key=lambda o: tool_name(o["op_id"]))
    return dict(sorted(by_module.items()))


_HEADER = '''"""Adaptive MCP tools for domain: {tag}.

GENERATED by scripts/generate_from_openapi.py — DO NOT EDIT BY HAND.
Any manual change here will be overwritten the next time the generator runs; to
change a tool, edit the generator (or the source OpenAPI spec) and regenerate via:
    python scripts/generate_from_openapi.py

Each generated tool is a thin async wrapper: it accepts typed parameters (path
params interpolated into the URL, query params forwarded as the query string) and
calls `execute_request`, which performs the actual HTTP GET.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from .._common import execute_request


def register(mcp: FastMCP) -> None:
'''


def _path_expr(path: str, path_params: list[dict]) -> str:
    """Return the Python expression for the request path.

    With path params, an f-string literal (the OpenAPI ``{name}`` placeholders are
    already valid f-string fields since param names are Python identifiers); with
    none, a plain string literal.
    """
    if path_params:
        return "f" + json.dumps(path)
    return json.dumps(path)


def _emit_tool(op: dict) -> str:
    """Render the Python source for one FastMCP tool from a collected op record."""
    name = tool_name(op["op_id"])
    summary = op["summary"] or op["op_id"]
    path = op["path"]
    pps = op["path_params"]
    qps = op["query_params"]

    # Description: override if present, else summary + method/path + param hint.
    desc = OVERRIDES.get(op["op_id"]) or summary
    param_names = [p["name"] for p in pps] + [p["name"] for p in qps]
    hint = f" GET {path}."
    if param_names:
        hint += " Params: " + ", ".join(param_names) + "."
    description = json.dumps(desc + hint)

    # Parameters: required path params first (no default), then optional query params.
    lines: list[str] = []
    for p in pps:
        ann = py_type(p.get("schema", {}), required=True)
        pdesc = json.dumps(f"Path param: {p['name']} ({(p.get('schema') or {}).get('type', 'string')})")
        lines.append(
            f"        {p['name']}: Annotated[{ann}, Field(description={pdesc})],"
        )
    for p in qps:
        schema = p.get("schema", {})
        ann = py_type(schema, required=False)
        default = _default_literal(schema)
        pdesc = json.dumps(f"Query param: {p['name']} ({schema.get('type', 'string')})")
        lines.append(
            f"        {p['name']}: Annotated[{ann}, Field(default={default}, description={pdesc})] = {default},"
        )
    params_block = "\n".join(lines)

    # Body: build the path expr and (when there are query params) the params dict.
    path_expr = _path_expr(path, pps)
    if qps:
        pairs = ", ".join(f'"{p["name"]}": {p["name"]}' for p in qps)
        body = f"        return await execute_request({path_expr}, {{{pairs}}})"
    else:
        body = f"        return await execute_request({path_expr})"

    return (
        f'    # {op["op_id"]} ({op["method"].upper()} {path}) — tool name "{name}"\n'
        f'    @mcp.tool(name="{name}", description={description})\n'
        f"    async def {name}(\n"
        f"{params_block}\n"
        f"    ) -> Any:\n"
        f"{body}\n"
    )


def _emit_module(mod: str, ops: list[dict]) -> str:
    """Render a full generated module's source."""
    tag = ops[0]["tag"] if ops else mod
    out = _HEADER.format(tag=tag)
    out += "\n".join(_emit_tool(op) for op in ops)
    return out


def generate(
    *,
    spec_path: Path = DEFAULT_SPEC,
    out_dir: Path = DEFAULT_OUT_DIR,
    endpoints_doc: Path = DEFAULT_DOC,
) -> None:
    """Generate all tool modules, the package __init__, and the docs catalog."""
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    by_module = collect(spec)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for mod, ops in by_module.items():
        (out_dir / f"{mod}.py").write_text(_emit_module(mod, ops), encoding="utf-8", newline="\n")

    # __init__.py importing every module and listing GENERATED_MODULES.
    mods = sorted(by_module)
    init_lines = ['"""Generated Adaptive tool modules. Do not edit by hand."""', "", "from . import ("]
    init_lines += [f"    {m}," for m in mods]
    init_lines += [")", "", "GENERATED_MODULES = ["]
    init_lines += [f"    {m}," for m in mods]
    init_lines += ["]", ""]
    (out_dir / "__init__.py").write_text("\n".join(init_lines), encoding="utf-8", newline="\n")

    # docs/ENDPOINTS.md catalog.
    doc_lines = [
        "# Adaptive MCP — Tool Catalog",
        "",
        "Generated by `scripts/generate_from_openapi.py`. Do not edit by hand.",
        "",
        "| Tool | Method · Path | Domain |",
        "|------|---------------|--------|",
    ]
    for mod in mods:
        for op in by_module[mod]:
            doc_lines.append(
                f"| `{tool_name(op['op_id'])}` | {op['method'].upper()} `{op['path']}` | {op['tag']} |"
            )
    doc_lines.append("")
    Path(endpoints_doc).parent.mkdir(parents=True, exist_ok=True)
    Path(endpoints_doc).write_text("\n".join(doc_lines), encoding="utf-8", newline="\n")


def main(argv: list[str]) -> int:
    spec_path = Path(argv[0]) if argv else DEFAULT_SPEC
    generate(spec_path=spec_path)
    print(f"Generated tools from {spec_path} into {DEFAULT_OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_generator.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_from_openapi.py tests/fixtures/mini_openapi.json tests/test_generator.py
git commit -m "feat: OpenAPI-driven tool generator"
```

---

### Task 8: Generate the real tool modules + tool registry + registration test

**Files:**
- Generate: `src/adaptive_mcp/tools/_generated/*.py` (5 modules + `__init__.py`)
- Generate: `docs/ENDPOINTS.md`
- Replace: `src/adaptive_mcp/tools/__init__.py` (real `register_all`)
- Test: `tests/test_registration.py`

- [ ] **Step 1: Run the generator against the real spec**

Run:
```bash
uv run python scripts/generate_from_openapi.py
```
Expected: prints "Generated tools from Source Material/openapi.json ...". Creates
`src/adaptive_mcp/tools/_generated/audit_logs.py`, `groups.py`, `phishing.py`,
`training.py`, `users.py`, `__init__.py`, and `docs/ENDPOINTS.md`.

- [ ] **Step 2: Verify the generated files compile and import**

Run:
```bash
uv run python -c "from adaptive_mcp.tools._generated import GENERATED_MODULES; print(len(GENERATED_MODULES))"
```
Expected: prints `5`.

- [ ] **Step 3: Write the real `src/adaptive_mcp/tools/__init__.py`**

Replace the stub with:
```python
"""Tool registry for the Adaptive MCP server.

Single entry point that wires every callable tool into the FastMCP server:
1. ``GENERATED_MODULES`` — one module per OpenAPI tag (audit_logs, groups,
   phishing, training, users), each exposing ``register(mcp)``.
2. ``request`` — the generic ``adaptive_request`` GET escape hatch.
"""

from __future__ import annotations

from fastmcp import FastMCP

from . import request
from ._generated import GENERATED_MODULES


def register_all(mcp: FastMCP) -> None:
    """Register every available tool on the given FastMCP server."""
    for module in GENERATED_MODULES:
        module.register(mcp)
    request.register(mcp)
```

- [ ] **Step 4: Write `tests/test_registration.py`**

```python
import pytest
from fastmcp import FastMCP

from adaptive_mcp.tools import register_all

EXPECTED_TOOLS = {
    # Audit Logs
    "list_audit_logs", "get_audit_log",
    # Groups
    "list_groups", "get_group", "get_group_members",
    # Phishing
    "list_phishing_campaigns", "get_phishing_enrollments", "get_phishing_campaign",
    "list_campaign_simulations", "get_simulation",
    # Training
    "list_training_campaigns", "get_training_campaign_enrollments", "get_training_campaign",
    # Users
    "list_users", "get_user",
    # Escape hatch
    "adaptive_request",
}


async def test_all_tools_register():
    mcp = FastMCP(name="test")
    register_all(mcp)
    tools = await mcp.get_tools()
    assert EXPECTED_TOOLS.issubset(set(tools)), EXPECTED_TOOLS - set(tools)
    # 15 generated tools + 1 escape hatch.
    assert len(EXPECTED_TOOLS) == 16


async def test_get_user_builds_path(monkeypatch):
    import adaptive_mcp.tools._common as common

    seen = {}

    class FakeClient:
        async def request(self, path, *, params=None):
            seen["path"] = path
            seen["params"] = params
            return {"id": "abc"}

    async def fake_get_client():
        return FakeClient()

    monkeypatch.setattr(common, "get_client", fake_get_client)

    mcp = FastMCP(name="test")
    register_all(mcp)
    tools = await mcp.get_tools()
    out = await tools["get_user"].fn(userId="abc")
    assert out == {"id": "abc"}
    assert seen["path"] == "/v2/users/abc"
```

- [ ] **Step 5: Run the registration tests**

Run: `uv run pytest tests/test_registration.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Run the full suite + lint**

Run:
```bash
uv run pytest
uv run ruff check .
```
Expected: all tests PASS; ruff reports no errors (generated files are exempt from style rules per `pyproject.toml`).

- [ ] **Step 7: Commit**

```bash
git add src/adaptive_mcp/tools/_generated/ src/adaptive_mcp/tools/__init__.py docs/ENDPOINTS.md tests/test_registration.py
git commit -m "feat: generate 15 Adaptive tools + register_all registry"
```

---

### Task 9: Server entrypoint (`server.py`)

**Files:**
- Create: `src/adaptive_mcp/server.py`
- Test: `tests/test_server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server.py
import pytest

from adaptive_mcp import server
from adaptive_mcp.config import reset_config_cache


async def test_build_server_registers_tools(monkeypatch):
    monkeypatch.setenv("ADAPTIVE_API_KEY", "tok")
    reset_config_cache()
    mcp = server.build_server()
    tools = await mcp.get_tools()
    assert "list_users" in tools
    assert "adaptive_request" in tools


def test_build_server_requires_api_key(monkeypatch):
    monkeypatch.delenv("ADAPTIVE_API_KEY", raising=False)
    reset_config_cache()
    from adaptive_mcp.config import ConfigError

    with pytest.raises(ConfigError):
        server.build_server()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_server.py -v`
Expected: FAIL — `AttributeError: module 'adaptive_mcp.server' has no attribute 'build_server'` (or import error).

- [ ] **Step 3: Write `src/adaptive_mcp/server.py`**

```python
"""Adaptive MCP server — entrypoint.

Wires everything into a runnable Model Context Protocol server exposing the
Adaptive Security Awareness Training API to AI assistants. Intentionally small:
the heavy lifting lives in sibling modules.
"""

from __future__ import annotations

import argparse
import logging
import sys

from fastmcp import FastMCP

from .client import shutdown_client
from .config import ConfigError, get_config
from .tools import register_all


def build_server() -> FastMCP:
    """Construct, configure, and fully populate the FastMCP server.

    Raises:
        ConfigError: from ``get_config()`` if required env settings (e.g. the API
            key) are missing — called first so misconfiguration fails fast.
    """
    config = get_config()  # validates env early

    # Logging MUST go to stderr: under the stdio transport, stdout is the JSON-RPC
    # channel, so any log line there would corrupt the protocol stream.
    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    mcp = FastMCP(
        name="adaptive-mcp",
        instructions=(
            "MCP server for the Adaptive Security Awareness Training API (v2). Tools "
            "are grouped by domain: Audit Logs, Groups, Phishing, Training, and Users. "
            "List endpoints are cursor-paginated — pass `page_after`/`page_size` and "
            "read the returned page cursor. Use `adaptive_request` for any read "
            "endpoint without a dedicated tool. The API is read-only (GET only)."
        ),
    )
    register_all(mcp)
    return mcp


def main() -> int:
    """CLI entrypoint: parse arguments, run the server, and clean up."""
    parser = argparse.ArgumentParser(prog="adaptive-mcp")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    try:
        mcp = build_server()
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 2

    config = get_config()
    try:
        if args.transport == "stdio":
            mcp.run(transport="stdio")
        else:
            mcp.run(
                transport="http",
                host=args.host or config.http_host,
                port=args.port or config.http_port,
            )
    finally:
        import asyncio

        try:
            asyncio.run(shutdown_client())
        except RuntimeError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_server.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full suite + lint**

Run:
```bash
uv run pytest
uv run ruff check .
```
Expected: all PASS; no lint errors.

- [ ] **Step 6: Commit**

```bash
git add src/adaptive_mcp/server.py tests/test_server.py
git commit -m "feat: server entrypoint (stdio + http transports)"
```

---

### Task 10: README, LICENSE, and CI

**Files:**
- Create: `README.md`
- Create: `LICENSE`
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write `LICENSE`**

Use the standard MIT License text, with copyright line:
```
MIT License

Copyright (c) 2026 Kierston Grantham
```
(Full MIT body follows — copy the canonical MIT text from
`Source Material/Reliaquest-Greymatter-MCP-Server-main/LICENSE` and replace the
copyright holder line.)

- [ ] **Step 2: Write `README.md`**

````markdown
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
````

- [ ] **Step 3: Write `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v5
      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}
      - name: Install
        run: uv pip install --system -e ".[dev]"
      - name: Lint
        run: ruff check .
      - name: Test
        run: pytest
```

> Note: CI installs from the committed `_generated/` modules; it does **not**
> regenerate (the `Source Material/` spec is git-ignored and not present in CI).

- [ ] **Step 4: Verify the suite still passes**

Run:
```bash
uv run pytest
uv run ruff check .
```
Expected: all PASS; no lint errors.

- [ ] **Step 5: Commit**

```bash
git add README.md LICENSE .github/workflows/ci.yml
git commit -m "docs: README, LICENSE, and CI workflow"
```

---

### Task 11: Live smoke test against the real API (verification)

This task confirms the server actually works end-to-end against Adaptive using the
key in `.env`. It writes no permanent files and makes only read (`GET`) calls.

**Files:**
- Create (temporary): `scripts/smoke_test.py`

- [ ] **Step 1: Write `scripts/smoke_test.py`**

```python
"""Manual live smoke test — hits the real Adaptive API using .env credentials.

Read-only: lists users and phishing campaigns. Run with `uv run python
scripts/smoke_test.py`. Not part of the automated test suite.
"""

from __future__ import annotations

import asyncio

from adaptive_mcp.client import get_client, shutdown_client


async def main() -> None:
    client = await get_client()
    try:
        users = await client.request("/v2/users", params={"page_size": 2})
        print("users keys:", list(users) if isinstance(users, dict) else type(users))
        campaigns = await client.request("/v2/phishing/campaigns", params={"page_size": 2})
        print("phishing campaigns keys:", list(campaigns) if isinstance(campaigns, dict) else type(campaigns))
        print("SMOKE TEST OK")
    finally:
        await shutdown_client()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run the smoke test**

Run:
```bash
uv run python scripts/smoke_test.py
```
Expected: prints the top-level keys of each response and `SMOKE TEST OK`.

**If it fails:**
- `HTTP 401`/`403` → the token in `.env` is wrong/expired, or the base URL is off.
- `HTTP 404` → a path is wrong; re-check against `Source Material/openapi.json`.
- Network error → connectivity/proxy issue; confirm `https://api.adaptivesecurity.com` is reachable.
Diagnose and fix the root cause (do not paper over it). Re-run until `SMOKE TEST OK`.

- [ ] **Step 3: Confirm the MCP server starts**

Run (let it start, then stop with Ctrl-C):
```bash
uv run adaptive-mcp --transport http --port 8765
```
Expected: starts without a traceback and logs that it is serving on `127.0.0.1:8765`.

- [ ] **Step 4: Remove the smoke-test script and commit nothing secret**

The smoke test is a throwaway. Either delete it or keep it (it contains no secrets —
it reads from `.env`). If keeping:
```bash
git add scripts/smoke_test.py
git commit -m "test: add manual live smoke-test script"
```
Otherwise delete `scripts/smoke_test.py`.

---

## Self-Review

**Spec coverage:**
- Module layout (config/client/errors/server/tools/_generated, scripts, tests, docs) → Tasks 1–10. ✓
- REST client w/ Bearer + ported retry/backoff → Task 4. ✓
- Generated tools (one module per tag; path/query param typing; spec defaults) → Tasks 7–8. ✓
- `adaptive_request` GET escape hatch → Task 6. ✓
- Config w/ `READ_ONLY` dropped, `ADAPTIVE_` prefix → Task 2. ✓
- `AdaptiveAPIError` (no GraphQL error class) → Task 3. ✓
- Generator from `openapi.json` → Task 7; run → Task 8. ✓
- Test suite (config, client, common, request tool, registration, generator, server) → Tasks 2–9. ✓
- Packaging (pyproject, entry point, ruff, deps) → Task 1. ✓
- README/LICENSE/CI/.env.example/.gitignore → Tasks 1, 10 (.env.example & .gitignore already created). ✓
- Live verification with provided key → Task 11. ✓

**Placeholder scan:** All code steps contain full code; the only "copy from reference"
instruction is the canonical MIT License text (Task 10 Step 1), which is a standard,
unambiguous document. No TODO/TBD left in code.

**Type/name consistency:** `AdaptiveAPIError(status_code, message, body)` consistent across
errors/client/tests. `AdaptiveClient.request(path, *, params=None)` consistent across
client/_common/tests. `execute_request(path, params=None)` consistent across
_common/request.py/generated tools/tests. Tool names in `test_registration.py` match the
`tool_name()` transform of each `operationId`. `register(mcp)` (no `read_only` arg) is
consistent across generated modules, `request.py`, and `register_all`.

**Risk note:** The exact FastMCP introspection API (`mcp.get_tools()` → dict, `.fn`
accessor) may vary by installed version. Tasks 6/8/9 tests depend on it; if the installed
`fastmcp` differs, adapt the accessor while preserving each test's assertions.
