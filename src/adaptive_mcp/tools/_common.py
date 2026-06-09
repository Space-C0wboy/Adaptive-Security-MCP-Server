"""Shared helpers used by every generated Adaptive tool.

The generated domain tools are thin wrappers: each builds its path and a dict of
query parameters, then hands them here to actually run. Centralizing that keeps
the generated code small and puts the argument-normalization rules in one place:

- ``drop_none``  — don't send query params the caller left unset.
- ``coerce_json`` — repair complex arguments (lists/objects) that an MCP client
  serialized as a JSON *string* instead of a real list/dict.

``execute_request`` ties them together and dispatches via the shared client.
"""

from __future__ import annotations

import json
from typing import Any

from ..client import get_client


def drop_none(params: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``params`` with all ``None`` values removed.

    Unset optional query arguments arrive as ``None``; sending them would clutter
    the query string (and could be rejected), so we omit them entirely.
    """
    return {k: v for k, v in params.items() if v is not None}


def coerce_json(value: Any) -> Any:
    """Parse a JSON string that encodes a list or object back into Python.

    MCP clients sometimes serialize complex tool arguments (a list of audit-log
    ``actions``, or the ``adaptive_request`` ``params`` object) as a JSON *string*
    rather than a real list/dict. The transport then rejects them ("Input should
    be a valid list/dictionary"). This recovers them. Plain scalar strings (ids,
    cursors, dates) don't start with ``{``/``[``, so they pass through untouched;
    anything that fails to parse is left as-is.
    """
    if isinstance(value, str):
        stripped = value.lstrip()
        if stripped[:1] in ("{", "["):
            try:
                parsed = json.loads(stripped)
            except (ValueError, TypeError):
                return value
            if isinstance(parsed, (dict, list)):
                return parsed
    return value


async def execute_request(
    path: str,
    params: dict[str, Any] | str | None = None,
) -> Any:
    """Run a GET through the shared client, normalizing query params.

    Args:
        path: The request path (path parameters already interpolated).
        params: Optional query parameters; may arrive as a real dict, or as a
            JSON string the MCP client stringified (which is coerced back). Unset
            (``None``) values inside it are dropped, and any individual value that
            arrived as a JSON-encoded list/object is coerced back to Python.

    Returns:
        The JSON payload returned by the client.
    """
    client = await get_client()
    # The whole params object may have been stringified by the client.
    if isinstance(params, str):
        params = coerce_json(params)
    raw = params if isinstance(params, dict) else {}
    # Drop unset args first, then coerce any survivors that arrived as JSON strings.
    cleaned = {k: coerce_json(v) for k, v in drop_none(raw).items()}
    return await client.request(path, params=cleaned)
