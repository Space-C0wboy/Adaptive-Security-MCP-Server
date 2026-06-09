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
