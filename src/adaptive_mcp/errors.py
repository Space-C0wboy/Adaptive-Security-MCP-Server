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
