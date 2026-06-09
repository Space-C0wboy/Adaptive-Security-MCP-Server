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
        """Close the connection pool and reset to the disconnected state.

        Concurrency-safe: guarded by the same lock as ``connect()`` so racing
        callers can't double-close the underlying client.
        """
        async with self._connect_lock:
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
        if self._client is None:  # pragma: no cover - connect() always sets it
            raise AdaptiveAPIError(0, "Client failed to initialize")

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
